# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Deterministic stub work layers for T1 — the SEAM T2/T3 replace.

T1 de-risks the baton with the same stub behavior the orchestrator tests use, but
re-housed here as importable fixtures (the test dirs are not packages). The
`WORK_IMPLS` / `STRATEGY_IMPLS` registries are the exact plug-point where T2/T3
register the real `ClaudeCodeWorkLayer` / `ClaudeCodeStrategyTools`.
"""

from framework._runtime.orchestrator.strategy_state import Proposal, Critique  # orchestrator on sys.path via framework.cli


class StubWorkLayer:
    """Satisfies orchestrator.nodes.WorkLayer with canned advance-fields (no side effects)."""

    def enrich_us(self, state) -> dict:
        return {"jira_hash": "stub"}

    def plan(self, state) -> dict:
        return {"path": "stub-plan.md", "schema_validated": True}

    def develop(self, state) -> dict:
        return {"branch": f"feature/{state.lifecycle.ticket}-backend"}

    def verify(self, state) -> dict:
        return {"verdict": "PASS", "path": "stub-verify.md",
                "schema_validated": True, "deviations_count": 0, "deviations": []}

    def commit(self, state) -> dict:
        return {"merge_commit": "stub123", "branch_deleted": True}

    def update_docs(self, state) -> dict:
        return {"record_path": "stub-record.md",
                "record_schema_validated": True, "ai_specs_commit": "stub456"}


class StubStrategyTools:
    """Satisfies orchestrator.strategy_tools.StrategyTools: veto once, then accept."""

    def __init__(self):
        self._critic_calls = 0

    def read_local(self, target, debt):
        return f"local<{target}>"

    def research(self, queries):
        return f"market<{len(queries)} queries>"

    def synthesize(self, local, market, criteria):
        return [Proposal(name="stub-play", approach="a", tradeoffs="t",
                         security_posture="s", coupling_risk="low")]

    def critique(self, proposals, criteria):
        self._critic_calls += 1
        verdict = "STRONG" if self._critic_calls > 1 else "WEAK"
        return Critique(verdict=verdict, must_fix=[] if verdict == "STRONG" else ["fix"])

    def render_report(self, state):
        verdict = state.critique.verdict if state.critique else "N/A"
        return (f"# Strategy Report\nTarget: {state.target_context}\n"
                f"Refine cycles: {state.refine_count}\nVerdict: {verdict}")


from framework.cli._work import ClaudeCodeWorkLayer, ClaudeCodeStrategyTools  # real Model-B muscle (T2/T3)

WORK_IMPLS = {"stub": StubWorkLayer, "claude": ClaudeCodeWorkLayer}
STRATEGY_IMPLS = {"stub": StubStrategyTools, "claude": ClaudeCodeStrategyTools}
