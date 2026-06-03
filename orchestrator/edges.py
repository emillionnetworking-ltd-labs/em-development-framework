# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Conditional edges for the lifecycle graph (framework release layer, <TICKET-ID>).

Routing functions are PURE: they read the STRUCTURED graph state (the verdict,
error, retries) + the typed prereq gate, and return the next node — never prose.
This is the orchestrator owning routing, replacing the human navigation prose
that <TICKET-ID> strips from the prompts.

The develop↔verify self-correction loop is bounded by MAX_RETRIES (the retries
counter is incremented in develop_node on re-entry, not here — edges stay pure).
"""

from typing import Literal

from graph_state import GraphState
from _state_machine import evaluate_prereq

MAX_RETRIES = 3


def route_after_verify(state: GraphState) -> Literal["commit", "develop", "classify", "halt"]:
    if state.error:
        return "halt"
    verdict = state.last_verdict
    if verdict in ("BLOCKED-GAP", "BLOCKED-BUILD"):
        return "develop" if state.retries < MAX_RETRIES else "halt"  # self-correction, bounded
    if verdict == "BLOCKED-RISK":
        return "classify"
    if verdict in ("PASS", "PASS-WITH-DEBT"):
        return "commit" if evaluate_prereq(state.lifecycle, "commit") else "halt"
    return "halt"


def route_after_classify(state: GraphState) -> Literal["commit", "develop", "halt"]:
    if state.error:  # Scope-Gap → back to develop (bounded)
        return "develop" if state.retries < MAX_RETRIES else "halt"
    return "commit" if evaluate_prereq(state.lifecycle, "commit") else "halt"
