# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""ClaudeCodeWorkLayer — the real Model-B lifecycle muscle (framework release layer, <TICKET-ID>).

Each phase node pauses via a dynamic `interrupt()` carrying a WorkRequest payload;
the baton surfaces it as exit 10; the agent (Claude Code) does the real work with
native tools (Jira, write plan/code/verify, git) and resumes via Command(resume=fields).

The work layer is a CONDUIT, not a brain: it performs NO side-effects (those are the
agent's during the exit-10 pause) and returns exactly the advance-fields the agent
injects. `interrupt()` is the first statement of every method, so LangGraph re-running
the node on resume is side-effect-free.
"""

from langgraph.types import interrupt

from framework._runtime.orchestrator.strategy_state import Proposal, Critique  # orchestrator on sys.path via framework.cli
from framework.cli._protocol import PHASE_GATES

# The return contract per phase: the advance-fields the agent must feed back. Hyphen
# keys match the lifecycle command names (apply_advance), not the method names.
PHASE_NEEDS = {
    "enrich-us": ["jira_hash"],
    "plan": ["path", "schema_validated"],
    "develop": ["branch"],
    "verify": ["verdict", "path", "schema_validated", "deviations_count", "deviations"],
    "commit": ["merge_commit", "branch_deleted"],
    "update-docs": ["record_path", "record_schema_validated"],
}


def _ask(state, phase: str) -> dict:
    """Pause the graph and hand the agent the work; returns the injected fields.
    Gated phases (commit→push, enrich-us→jira-post) carry the hard-limit so the
    baton surfaces it and the agent pauses for the operator (see operation-protocol)."""
    return interrupt({
        "phase": phase,
        "ticket": state.lifecycle.ticket,
        "module": state.module,
        "needs": PHASE_NEEDS[phase],
        "gate": PHASE_GATES.get(phase),
        "context": {
            "state": state.lifecycle.to_state_dict().get("state"),
            "retries": state.retries,
            "last_verdict": state.last_verdict,
        },
    })


class ClaudeCodeWorkLayer:
    """Satisfies orchestrator.nodes.WorkLayer by delegating each phase to the agent."""

    def enrich_us(self, state) -> dict:
        return _ask(state, "enrich-us")

    def plan(self, state) -> dict:
        return _ask(state, "plan")

    def develop(self, state) -> dict:
        return _ask(state, "develop")

    def verify(self, state) -> dict:
        return _ask(state, "verify")

    def commit(self, state) -> dict:
        return _ask(state, "commit")

    def update_docs(self, state) -> dict:
        return _ask(state, "update-docs")


# ---- Strategy muscle (framework release layer, <TICKET-ID>) ----

def _to_proposals(feed) -> list:
    """Reconstitute the agent's injected feed to typed Proposals."""
    return [p if isinstance(p, Proposal) else Proposal(**p) for p in (feed or [])]


def _to_critique(feed) -> Critique:
    """Reconstitute the agent's injected feed to a typed Critique."""
    return feed if isinstance(feed, Critique) else Critique(**(feed or {}))


class ClaudeCodeStrategyTools:
    """Satisfies orchestrator.strategy_tools.StrategyTools by delegating each cognitive
    op to the agent via a dynamic interrupt. read_local/research/render_report return
    strings; synthesize/critique reconstitute the injected feed to Pydantic types
    (the only delta vs ClaudeCodeWorkLayer, which returns plain dicts)."""

    def read_local(self, target: str, debt: str) -> str:
        return interrupt({"phase": "read_local", "needs": ["findings"],
                          "context": {"target": target, "debt": debt}})

    def research(self, queries: list) -> str:
        return interrupt({"phase": "research", "needs": ["findings"],
                          "context": {"queries": queries}})

    def synthesize(self, local: str, market: str, criteria: list) -> list:
        return _to_proposals(interrupt({
            "phase": "synthesize", "needs": ["proposals"],
            "context": {"local": local, "market": market, "criteria": criteria}}))

    def critique(self, proposals: list, criteria: list) -> Critique:
        return _to_critique(interrupt({
            "phase": "critique", "needs": ["critique"],
            "context": {"proposals": [p.model_dump() for p in proposals], "criteria": criteria}}))

    def render_report(self, state) -> str:
        return interrupt({"phase": "render_report", "needs": ["report"],
                          "context": {"target": state.target_context,
                                      "refine_count": state.refine_count,
                                      "verdict": state.critique.verdict if state.critique else None}})
