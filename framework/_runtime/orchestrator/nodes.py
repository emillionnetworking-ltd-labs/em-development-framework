# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Lifecycle nodes for the orchestrator (framework release layer, <TICKET-ID> — base nodes).

Each node is a pure `(GraphState) -> GraphState`: it runs the phase WORK (the
LLM/agent + side effects, abstracted behind `WorkLayer` so nodes are testable
with a stub), then applies the typed in-RAM transition via `apply_advance`. Nodes
never touch disk (the compiled graph's StateYamlCheckpointer persists at the
boundary), never `sys.exit`, and never print routing — routing is the graph's job.

Base nodes (this ticket): enrich_us, plan, develop. verify/classify (T3) and
commit/update_docs (T4) follow the same contract.
"""

from typing import Callable, Protocol

from .graph_state import GraphState
from framework._runtime.state._state_machine import apply_advance, evaluate_prereq
from framework._runtime.state._classify_deviation import classify_typed

NodeFn = Callable[[GraphState], GraphState]


class WorkLayer(Protocol):
    """The phase WORK: produces the advance-fields and performs side effects
    (Jira enrichment, writing the plan/code, etc.). Real impl wired later; tests
    inject a stub. Each method returns the dict of fields to advance for its phase
    (validated against COMMAND_RULES.allowed_fields by apply_advance)."""

    def enrich_us(self, state: GraphState) -> dict: ...
    def plan(self, state: GraphState) -> dict: ...
    def develop(self, state: GraphState) -> dict: ...
    def verify(self, state: GraphState) -> dict: ...
    def commit(self, state: GraphState) -> dict: ...
    def update_docs(self, state: GraphState) -> dict: ...


def _step_done(state: GraphState, step_key: str) -> bool:
    steps = state.lifecycle.to_state_dict().get("steps", {})
    return bool(steps.get(step_key, {}).get("done", False))


def _advance(state: GraphState, command: str, fields: dict) -> GraphState:
    state.lifecycle = apply_advance(state.lifecycle, command, fields)
    return state


def build_base_nodes(work: WorkLayer) -> dict[str, NodeFn]:
    """Build the three base nodes bound to a WorkLayer."""

    def enrich_us_node(state: GraphState) -> GraphState:
        # Idempotent / replay-safe: if already enriched, do NOT re-run the side
        # effect (no double Jira create on a checkpoint replay). Node C concern.
        if _step_done(state, "enrich-us"):
            return state
        fields = work.enrich_us(state)
        return _advance(state, "enrich-us", fields)

    def plan_node(state: GraphState) -> GraphState:
        if not evaluate_prereq(state.lifecycle, "plan"):
            state.error = "prereq not met: plan requires enrich-us done"
            return state
        fields = work.plan(state)
        return _advance(state, "plan", fields)

    def develop_node(state: GraphState) -> GraphState:
        # Re-entry (develop already done) = a verify→develop self-correction cycle;
        # count it so the bounded loop (edges.MAX_RETRIES) can halt eventually.
        if _step_done(state, "develop"):
            state.retries += 1
            state.error = None  # clear the prior BLOCKED/scope-gap signal for the retry
        if not evaluate_prereq(state.lifecycle, "develop"):
            state.error = "prereq not met: develop requires plan done + schema_validated"
            return state
        fields = work.develop(state)
        return _advance(state, "develop", fields)

    return {"enrich_us": enrich_us_node, "plan": plan_node, "develop": develop_node}


_VERIFY_FIELDS = ("verdict", "path", "schema_validated", "deviations_count")


def build_control_nodes(work: WorkLayer) -> dict[str, NodeFn]:
    """The control-core nodes (T3): verify + classify."""

    def verify_node(state: GraphState) -> GraphState:
        if not evaluate_prereq(state.lifecycle, "verify"):
            state.error = "prereq not met: verify requires develop done"
            return state
        out = work.verify(state)
        if out.get("artifact_valid") is False:
            state.error = f"verify artifact invalid: {out.get('path')}"
            return state
        state.last_verdict = out.get("verdict")
        state.pending_deviation_inputs = out.get("deviations", []) or []
        fields = {k: out[k] for k in _VERIFY_FIELDS if k in out}
        state.lifecycle = apply_advance(state.lifecycle, "verify", fields)
        return state

    def classify_node(state: GraphState) -> GraphState:
        """Classify each pending deviation input via the enforced classifier.
        Scope-Gap (classify_typed raises) → signal a route back to develop."""
        classified: list = []
        for inp in state.pending_deviation_inputs:
            try:
                dev = classify_typed(inp.get("answers", {}),
                                     description=inp.get("description", ""),
                                     step=inp.get("step"), ref=inp.get("ref"))
            except ValueError:
                state.error = "scope-gap: deviation blocks — route to develop"
                return state
            classified.append(dev)
        state.pending_deviations = classified
        state.pending_deviation_inputs = []
        return state

    return {"verify": verify_node, "classify": classify_node}


def build_closure_nodes(work: WorkLayer) -> dict[str, NodeFn]:
    """The loop-closure nodes (T4): commit + update_docs."""

    def commit_node(state: GraphState) -> GraphState:
        if _step_done(state, "commit"):     # idempotent / replay-safe (no re-merge)
            return state
        if not evaluate_prereq(state.lifecycle, "commit"):
            state.error = "prereq not met: commit requires verify done + PASS verdict"
            return state
        fields = work.commit(state)
        return _advance(state, "commit", fields)

    def update_docs_node(state: GraphState) -> GraphState:
        if not evaluate_prereq(state.lifecycle, "update-docs"):
            state.error = "prereq not met: update-docs requires commit done"
            return state
        fields = work.update_docs(state)
        return _advance(state, "update-docs", fields)  # terminal → state=documented

    return {"commit": commit_node, "update_docs": update_docs_node}


def build_nodes(work: WorkLayer) -> dict[str, NodeFn]:
    """All seven lifecycle nodes (base + control + closure)."""
    return {**build_base_nodes(work), **build_control_nodes(work), **build_closure_nodes(work)}
