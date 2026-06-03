# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Conditional edges for the strategy graph (framework release layer, <TICKET-ID>).

Routing functions are PURE: they read the STRUCTURED StrategyState (the critic's
verdict + the refine budget, the human decision) and return the next node — never
mutate, never touch disk. Mutation stays in the nodes (<TICKET-ID>); the graph owns
routing + checkpointing.

The critic↔synthesizer self-refine loop is bounded by `max_refines`: while the
verdict is a veto AND budget remains the engine loops back to refine; once the
budget is exhausted (or the verdict is STRONG) it escalates to the human review
rather than looping forever.
"""

from langgraph.graph import END

from strategy_state import StrategyState

VETO_VERDICTS = ("WEAK", "COMPLACENT", "INSECURE")


def route_after_critique(state: StrategyState) -> str:
    """critic → synthesizer (refine, while budget remains) | human_review (done)."""
    critique = state.critique
    if critique is None:  # defensive: critic always runs first, so this shouldn't fire
        return "human_review"
    if critique.verdict == "STRONG":
        return "human_review"
    if critique.verdict in VETO_VERDICTS:
        return "synthesizer" if state.refine_count < state.max_refines else "human_review"
    return "human_review"


def route_after_human(state: StrategyState) -> str:
    """human_review → synthesizer (refine) | END (approve/abort)."""
    if state.human_decision == "refine":
        return "synthesizer"
    return END
