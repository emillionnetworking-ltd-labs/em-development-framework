# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""The cyclic strategy nodes (framework release layer, <TICKET-ID>).

Five pure `(StrategyState) -> StrategyState` nodes over the StrategyTools seam:
  - archaeologist : read the local code + technical debt on disk
  - consultant    : research industry best-practices + benchmarks (web)
  - synthesizer   : cross findings → competing proposals (detects refine re-entry)
  - critic        : the ruthless anti-patch veto
  - human_review  : render the executive report (the interrupt that freezes around
                    it is wired in the graph, T3)

Nodes never touch disk, sys.exit, or print routing — the compiled graph (T3)
checkpoints + routes. The synthesizer increments refine_count and folds the
critic's must_fix into its criteria when re-entered, which is the engine of the
bounded self-refine (anti-patch) loop.
"""

from typing import Callable

from .strategy_state import StrategyState
from .strategy_tools import StrategyTools

StrategyNodeFn = Callable[[StrategyState], StrategyState]


def _research_queries(s: StrategyState) -> list[str]:
    """Derive the consultant's web queries from the problem + the business criteria."""
    queries = [f"industry best practices: {s.target_context}"]
    queries += [f"benchmark: {c} — {s.target_context}" for c in s.business_criteria]
    return queries


def build_strategy_nodes(tools: StrategyTools) -> dict[str, StrategyNodeFn]:
    """Build the strategy nodes bound to a StrategyTools implementation."""

    def archaeologist_node(s: StrategyState) -> StrategyState:
        s.local_findings = tools.read_local(s.target_context, s.historical_debt)
        return s

    def consultant_node(s: StrategyState) -> StrategyState:
        s.market_findings = tools.research(_research_queries(s))
        return s

    def synthesizer_node(s: StrategyState) -> StrategyState:
        # Re-entry from the critic == a self-refine cycle: count it and feed the
        # critic's must_fix into the synthesis so the refined proposals address the veto.
        if s.critique is not None:
            s.refine_count += 1
            criteria = s.business_criteria + [f"MUST-FIX: {m}" for m in s.critique.must_fix]
        else:
            criteria = s.business_criteria
        s.proposals = tools.synthesize(s.local_findings or "", s.market_findings or "", criteria)
        return s

    def critic_node(s: StrategyState) -> StrategyState:
        s.critique = tools.critique(s.proposals, s.business_criteria)
        return s

    def human_review_node(s: StrategyState) -> StrategyState:
        s.executive_report = tools.render_report(s)
        return s

    return {
        "archaeologist": archaeologist_node,
        "consultant": consultant_node,
        "synthesizer": synthesizer_node,
        "critic": critic_node,
        "human_review": human_review_node,
    }
