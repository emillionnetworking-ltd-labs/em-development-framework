# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Session assembly + the step loop — the baton's engine.

Builds the right compiled graph (lifecycle | strategy) with its durable
checkpointer + thread, drives it one hop per invocation via `stream` (resumable),
and exposes the helpers run.py uses to classify the stop and build the WorkRequest.
All orchestration lives here; run.py stays a thin arg-parser → exit-code mapper.
"""

import re
from typing import Optional

import yaml

# orchestrator brains (on sys.path via framework.cli.__init__)
from framework._runtime.orchestrator.graph_state import GraphState
from framework._runtime.orchestrator.strategy_state import StrategyState
from framework._runtime.orchestrator.lifecycle_graph import build_graph
from framework._runtime.orchestrator.strategy_graph import build_strategy_graph
from framework._runtime.orchestrator.checkpointer import StateYamlCheckpointer
from framework._runtime.orchestrator.strategy_checkpointer import StrategySnapshotSaver
from framework._runtime.state._state_machine import load_state_typed, state_path
from pathlib import Path

from langgraph.types import Command

from framework.cli import repo_root
from framework.cli._protocol import WorkRequest, classify_stop, exit_code_for, EXIT_WORK
from framework.cli._stubs import WORK_IMPLS, STRATEGY_IMPLS


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "session"


def _load_workspace_config(root: str) -> Optional[dict]:
    """<TICKET-ID> framework release layer (Pilar 1.2 runtime injection): load forge.config.yml from
    repo root if present. Returns dict on success, None if file absent or
    unparseable (fail-open — motor remains workable without workspace context;
    personas/agents detect None workspace + surface remediation)."""
    config_path = Path(root) / "forge.config.yml"
    if not config_path.is_file():
        return None
    try:
        with config_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except (yaml.YAMLError, OSError):
        return None


# ---- session builders ----

def _resolve_paths(root: str, output_dir_cli: Optional[str] = None):
    """Resolve (checkpoints_dir, sessions_dir) per the 5-level precedence.

    Inputs: CLI ``--output-dir`` value (or None), env var,
    ``forge.config.yml::output_dir`` (or None / sentinel), default.

    Legacy-mode trigger: when forge.config.yml exists at the repo root AND
    its ``output_dir`` is ``.`` or unset AND no CLI/env/ctor override, use
    repo-relative paths (operator dogfood backwards-compat).
    """
    from framework.api import (
        resolve_output_dir, is_legacy_mode,
        _legacy_paths_for_repo,
        CHECKPOINTS_SUBDIR, SESSIONS_SUBDIR,
    )
    config_path = Path(root) / "forge.config.yml"
    config_file_exists = config_path.is_file()
    config_file_value: Optional[str] = None
    if config_file_exists:
        try:
            with config_path.open(encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            config_file_value = cfg.get("output_dir") if isinstance(cfg, dict) else None
        except (yaml.YAMLError, OSError):
            config_file_value = None
    if is_legacy_mode(
        cli_value=output_dir_cli,
        ctor_value=None,
        config_file_value=config_file_value,
        config_file_exists=config_file_exists,
    ):
        return _legacy_paths_for_repo(Path(root))
    output_dir = resolve_output_dir(
        cli_value=output_dir_cli,
        config_file_value=config_file_value,
        config_file_exists=config_file_exists,
    )
    return output_dir / CHECKPOINTS_SUBDIR, output_dir / SESSIONS_SUBDIR


def build_lifecycle_session(ticket: str, module: str, *, work_impl: str = "stub",
                            checkpoints_dir=None, root: Optional[str] = None,
                            output_dir: Optional[str] = None):
    root = root or str(repo_root())
    work = WORK_IMPLS[work_impl]()
    if checkpoints_dir is None:
        checkpoints_dir, _ = _resolve_paths(root, output_dir)
    cp = StateYamlCheckpointer(checkpoints_dir=checkpoints_dir, root=root)
    app = build_graph(work, checkpointer=cp)
    config = {"configurable": {"thread_id": ticket}}
    initial = GraphState.from_disk(module, ticket, root)
    # Pilar 1.2 — workspace context injection from forge.config.yml
    initial.workspace = _load_workspace_config(root)
    return app, config, initial


def build_strategy_session(target: str, *, work_impl: str = "stub", sessions_dir=None,
                          root: Optional[str] = None,
                          output_dir: Optional[str] = None):
    root = root or str(repo_root())
    tools = STRATEGY_IMPLS[work_impl]()
    if sessions_dir is None:
        _, sessions_dir = _resolve_paths(root, output_dir)
    saver = StrategySnapshotSaver(sessions_dir=sessions_dir)
    app = build_strategy_graph(tools, checkpointer=saver)
    config = {"configurable": {"thread_id": slug(target)}}
    # Pilar 1.2 — workspace context injection from forge.config.yml
    workspace = _load_workspace_config(root)
    initial = StrategyState(target_context=target, business_criteria=["security", "determinism"],
                            workspace=workspace)
    return app, config, initial


# ---- the step loop ----

def _drain(stream):
    """Drain a graph stream, capturing the dynamic interrupt() payload if one fires.

    A dynamic interrupt surfaces as a `{"__interrupt__": (Interrupt(value=...),)}` chunk
    (it is NOT exposed on the stopped StateSnapshot), so it must be caught here."""
    interrupt_value = None
    for chunk in stream:
        if isinstance(chunk, dict) and "__interrupt__" in chunk:
            payloads = chunk["__interrupt__"]
            if payloads:
                interrupt_value = payloads[0].value
    return interrupt_value


def run_until_stop(app, config, initial):
    """Stream to the next interrupt or END. Returns (snapshot, interrupt_value|None)."""
    iv = _drain(app.stream(initial, config))
    return app.get_state(config), iv


def resume(app, config, *, feed=None, decision=None):
    """Resume a frozen graph. Returns (snapshot, interrupt_value|None).

    Disambiguated by CALLER INTENT, not by node name (a dynamic interrupt can fire
    inside a node that is also a static-gate node, e.g. render_report inside
    human_review):
      - `decision` given  → a static human gate: inject `human_decision`, resume null.
      - otherwise         → a dynamic interrupt: resume the node via Command(resume=feed)
                            (re-runs the node; the interrupt() call returns `feed`)."""
    if decision is not None:
        app.update_state(config, {"human_decision": decision})
        iv = _drain(app.stream(None, config))
    else:
        iv = _drain(app.stream(Command(resume=feed if feed is not None else {}), config))
    return app.get_state(config), iv


def _context_slice(values: dict, mode: str) -> dict:
    """A small serializable slice of the stopped state for the agent."""
    if mode == "lifecycle":
        lc = values.get("lifecycle")
        ctx = {"error": values.get("error"), "retries": values.get("retries"),
               "last_verdict": values.get("last_verdict")}
        if lc is not None:
            sd = lc.to_state_dict()
            ctx["ticket"] = sd.get("ticket")
            ctx["state"] = sd.get("state")
        return ctx
    crit = values.get("critique")
    return {"target_context": values.get("target_context"),
            "refine_count": values.get("refine_count"),
            "verdict": getattr(crit, "verdict", None),
            "must_fix": getattr(crit, "must_fix", None)}


def build_request(snap, mode: str, thread_id: str, interrupt_value=None):
    """Return (WorkRequest|None, exit_code) for a stopped graph snapshot.

    A captured dynamic-interrupt payload (cognitive work) takes priority and is
    described by its own fields; otherwise fall back to the static done/human/work
    classification from the snapshot's pending `next`.

    <TICKET-ID> framework release layer (Pilar 1.2 runtime injection): merge `workspace` from the
    state values into the context dict so any agent reading the WorkRequest JSON
    receives the workspace symbolically (no textual instruction needed).
    """
    workspace = snap.values.get("workspace") if isinstance(snap.values, dict) else None
    if interrupt_value:
        payload = interrupt_value
        context = dict(payload.get("context", {}))
        if workspace is not None and "workspace" not in context:
            context["workspace"] = workspace
        req = WorkRequest(kind="work", mode=mode, thread_id=thread_id,
                          node=payload.get("phase", ""), needs=payload.get("needs", []),
                          context=context, gate=payload.get("gate"))
        return req, EXIT_WORK
    stop = classify_stop(snap.next)
    code = exit_code_for(stop)
    if stop == "done":
        return None, code
    node = snap.next[0] if snap.next else ""
    context = _context_slice(snap.values, mode)
    if workspace is not None and "workspace" not in context:
        context["workspace"] = workspace
    req = WorkRequest(kind="human" if stop == "human" else "work", mode=mode,
                      thread_id=thread_id, node=node, needs=[],
                      context=context)
    return req, code


def lifecycle_status(ticket: str, module: str, root: Optional[str] = None) -> Optional[dict]:
    root = root or str(repo_root())
    lc = load_state_typed(state_path(Path(root), module, ticket))
    if lc is None:
        return None
    sd = lc.to_state_dict()
    done = [k for k, v in sd.get("steps", {}).items() if v.get("done")]
    return {"ticket": sd.get("ticket"), "state": sd.get("state"), "steps_done": done}
