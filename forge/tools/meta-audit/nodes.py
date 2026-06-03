# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""meta-audit/nodes.py — verification nodes (pure functions: state -> state).

Each node analyses one facet of every lifecycle stage and mutates the shared
AuditState in place (then returns it, LangGraph-node style). No langgraph import.

Mechanical only — no prose parsing. Tools are inspected via the `ast` module;
schemas via YAML structural walk. See ADR-009 + the calibration note in state.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

# Outbound-network stdlib/3rd-party modules. A lifecycle tool importing any of
# these is not context-isolated (it can reach off-box, breaking determinism
# and orchestrator reproducibility).
NETWORK_MODULES = {
    "socket", "http", "urllib", "requests", "httpx",
    "ftplib", "smtplib", "telnetlib",
}

# Tools whose outbound I/O is INHERENT and accepted (not a defect). Keyed by
# framework-root-relative path → reason. Node C reports these as accepted
# (CLEAN, with evidence) instead of WARNING; the orchestrator must still wrap
# such stages as network-aware (side-effecting, replay-safe) nodes — but the
# meta-audit does not flag a known, controlled dependency as a hole (<TICKET-ID>).
ACCEPTED_NETWORK_IO = {
    "forge/tools/classify-deviation.py":
        "Jira REST (deviation-ticket creation + sprint lookup) — inherent to the lifecycle",
    # <TICKET-ID>: the logic (incl. the urllib/Jira client) moved into the lib; the
    # _logic_module resolver routes Node C's scan there, so key the lib explicitly.
    "forge/tools/_classify_deviation.py":
        "Jira REST (deviation-ticket creation + sprint lookup) — inherent to the lifecycle",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _is_const(node: ast.AST | None, value) -> bool:
    return isinstance(node, ast.Constant) and node.value == value


def _is_exit_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "exit":      # sys.exit / os._exit
        return True
    if isinstance(func, ast.Name) and func.id == "exit":             # bare exit()
        return True
    return False


def analyze_exit_codes(source: str) -> dict:
    """Static exit-code contract analysis.

    Returns {'has_success': bool, 'error_path_returns_zero': bool}.
      - has_success: an explicit success signal exists — sys.exit(0),
        `return 0`, or delegation `sys.exit(main())`.
      - error_path_returns_zero: a sys.exit(0) lives inside an `except`
        handler (an error path that masquerades as success). This is the
        BROKEN case.
    """
    tree = ast.parse(source)
    state = {"has_success": False, "error_path_returns_zero": False}

    class V(ast.NodeVisitor):
        def __init__(self) -> None:
            self.handler_depth = 0

        def visit_ExceptHandler(self, node: ast.ExceptHandler):
            self.handler_depth += 1
            self.generic_visit(node)
            self.handler_depth -= 1

        def visit_Call(self, node: ast.Call):
            if _is_exit_call(node):
                arg = node.args[0] if node.args else None
                if _is_const(arg, 0):
                    if self.handler_depth > 0:
                        state["error_path_returns_zero"] = True
                    else:
                        state["has_success"] = True
                elif isinstance(arg, ast.Call):
                    # sys.exit(main()) — success handled inside main()
                    state["has_success"] = True
            self.generic_visit(node)

        def visit_Return(self, node: ast.Return):
            if _is_const(node.value, 0):
                state["has_success"] = True
            self.generic_visit(node)

    V().visit(tree)
    return state


def analyze_network_imports(source: str) -> list[str]:
    """Return the outbound-network module names imported by the source."""
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in NETWORK_MODULES:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in NETWORK_MODULES:
                found.append(node.module)
    return sorted(set(found))


def analyze_schema_hardness(schema_text: str) -> dict:
    """Count GENUINE DATA objects and how many declare additionalProperties: false.

    Returns {'total_objects': int, 'locked': int, 'unlocked': [paths]}.

    Only object schemas reached purely via DATA edges — `properties.<name>` and
    `items` — are counted. We deliberately do NOT descend into, nor count:
      - `$defs` / `definitions` (reusable fragments + section matchers, not data),
      - conditional/combinator machinery (`allOf`/`anyOf`/`oneOf`/`if`/`then`/
        `else`/`not`) — `additionalProperties:false` there is semantically wrong,
      - the ROOT node (often an intentionally-open parse-wrapper, e.g. the
        markdown `{frontmatter, headings}` object in plan/verify/record schemas),
      - the `headings` array.
    This keeps the signal to real free-text-injection surfaces (<TICKET-ID>).
    """
    data = yaml.safe_load(schema_text)
    total = 0
    locked = 0
    unlocked: list[str] = []

    def is_object_schema(node) -> bool:
        return isinstance(node, dict) and (node.get("type") == "object" or "properties" in node)

    def visit(node, path: str, is_root: bool) -> None:
        nonlocal total, locked
        if not isinstance(node, dict):
            return
        # Count this node only if it is a genuine data object (and not the root).
        if is_object_schema(node) and not is_root:
            total += 1
            ap = node.get("additionalProperties")
            # "Locked" = no free-text injection possible: either extras are
            # forbidden (False) OR they are a constrained value-schema (a typed
            # map, e.g. {type: string, enum: [...]}). Only `true` or an absent
            # `additionalProperties` (which defaults to true) is a genuine hole.
            if ap is False or isinstance(ap, dict):
                locked += 1
            else:
                unlocked.append(path or "<root>")
        # Descend ONLY through data edges; skip $defs and combinator/conditional
        # keywords entirely (they are schema machinery, not data shapes).
        props = node.get("properties")
        if isinstance(props, dict):
            for name, sub in props.items():
                if name == "headings":
                    continue  # markdown-headings array — not a data object
                child = f"{path}.properties.{name}" if path else f"properties.{name}"
                visit(sub, child, False)
        items = node.get("items")
        if isinstance(items, dict):
            visit(items, f"{path}.items" if path else "items", False)

    visit(data, "", True)
    return {"total_objects": total, "locked": locked, "unlocked": unlocked}


# --------------------------------------------------------------------------- #
# Nodes — each takes (state, fmap) and returns the mutated state.
# `fmap` is the lifecycle artifact map: phase -> {skill, schemas, tools}.
# --------------------------------------------------------------------------- #

def node_a_cli_robustness(state, fmap):
    """Node A — CLI exit-code honesty of each stage's support tools."""
    root = Path(state.framework_root)
    for phase, audit in state.phases.items():
        tools = fmap[phase].get("tools", [])
        if not tools:
            continue  # leave predictable_exit_code = None (no executable)
        ok = True
        for rel in tools:
            p = root / rel
            if not p.is_file():
                audit.broke(f"Node A: support tool not found: {rel}")
                ok = False
                continue
            res = analyze_exit_codes(_read(p))
            if res["error_path_returns_zero"]:
                audit.broke(f"Node A: {rel} has sys.exit(0) inside an except handler "
                            f"(error path exits 0)")
                ok = False
            elif not res["has_success"]:
                audit.warn(f"Node A: {rel} has no explicit success exit "
                           f"(sys.exit(0)/return 0/sys.exit(main())); relies on fall-through")
            else:
                audit.evidence.append(f"Node A: {rel} exit-code contract OK")
        audit.predictable_exit_code = ok
    return state


def node_b_schema_hardness(state, fmap):
    """Node B — schema rigidity (no free-text injection outside typed fields)."""
    root = Path(state.framework_root)
    for phase, audit in state.phases.items():
        schemas = fmap[phase].get("schemas", [])
        if not schemas:
            continue  # leave deterministic_output = None (no schema artifact)
        ok = True
        for rel in schemas:
            p = root / rel
            if not p.is_file():
                audit.broke(f"Node B: schema not found: {rel}")
                ok = False
                continue
            try:
                res = analyze_schema_hardness(_read(p))
            except yaml.YAMLError as exc:
                audit.broke(f"Node B: schema {rel} is unparseable: {exc}")
                ok = False
                continue
            if res["unlocked"]:
                shown = ", ".join(res["unlocked"][:6])
                more = "" if len(res["unlocked"]) <= 6 else f" (+{len(res['unlocked']) - 6} more)"
                audit.warn(f"Node B: {rel} — {len(res['unlocked'])}/{res['total_objects']} "
                           f"object(s) without additionalProperties:false: {shown}{more}")
            else:
                audit.evidence.append(f"Node B: {rel} fully hardened "
                                      f"({res['locked']}/{res['total_objects']} objects locked)")
        audit.deterministic_output = ok
    return state


def _logic_module(cli_rel: str, root: Path) -> str:
    """Resolve where a tool's LOGIC lives (decision B, <TICKET-ID>).

    Since the steel-foundations refactor, a hyphenated CLI tool `X.py` keeps its
    logic in the importable sibling `_<snake>.py` (ADR-006). Return that lib
    rel-path if it exists on disk, else the CLI path itself (tool not yet split).
    This lets Node C scan the logic-module (flock/network) while Node A scans the
    CLI entrypoint (exit codes) — and it auto-adapts as more tools are split, with
    no per-tool map to maintain.
    """
    p = Path(cli_rel)
    lib = p.with_name("_" + p.stem.replace("-", "_") + ".py")
    return str(lib) if (root / lib).is_file() else cli_rel


def node_c_idempotency_isolation(state, fmap):
    """Node C — idempotency (state writes are locked) + context isolation (no net).

    Scans the LOGIC module (the lib if the tool has been split, else the CLI) so
    the flock + network checks follow the logic, not the thin shell (decision B).
    Node A separately scans the CLI entrypoint for exit codes.
    """
    root = Path(state.framework_root)
    for phase, audit in state.phases.items():
        tools = fmap[phase].get("tools", [])
        if not tools:
            continue
        idempotency = None
        isolated = True
        for cli_rel in tools:
            rel = _logic_module(cli_rel, root)  # the lib if split, else the CLI
            p = root / rel
            if not p.is_file():
                continue  # already flagged by Node A (it scans the CLI entrypoint)
            src = _read(p)
            if Path(rel).stem in ("state-machine", "_state_machine"):
                if "flock" in src:
                    idempotency = True
                    audit.evidence.append(f"Node C: {rel} serializes writes via fcntl.flock (LCK-001)")
                else:
                    idempotency = False
                    audit.broke(f"Node C: {rel} writes state without flock — concurrent/"
                                f"interrupted advance is unsafe")
            net = analyze_network_imports(src)
            if net:
                reason = ACCEPTED_NETWORK_IO.get(rel) or ACCEPTED_NETWORK_IO.get(cli_rel)
                if reason:
                    # Known, accepted I/O — not a hole. Record it (the orchestrator
                    # still wraps this stage as a network-aware, replay-safe node),
                    # but do NOT raise a WARNING (<TICKET-ID> calibration).
                    audit.evidence.append(
                        f"Node C: {rel} outbound I/O ACCEPTED ({reason}); "
                        f"orchestrator wraps as a network-aware node")
                else:
                    # Unexpected network in a lifecycle tool → flag it.
                    isolated = False
                    audit.warn(f"Node C: {rel} imports unexpected outbound-network "
                               f"module(s): {', '.join(net)} — not a pure node; "
                               f"orchestrator must wrap with network-aware semantics")
        audit.idempotency_safe = idempotency
        audit.context_isolated = isolated
    return state


# Edge order — the graph runs these linearly over every phase.
PIPELINE = [node_a_cli_robustness, node_b_schema_hardness, node_c_idempotency_isolation]
