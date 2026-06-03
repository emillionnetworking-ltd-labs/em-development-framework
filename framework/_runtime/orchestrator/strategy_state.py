# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""StrategyState — the state of the Global Native Strategist graph (framework release layer, <TICKET-ID>).

The strategist is a governance/design engine that PRECEDES the lifecycle: it analyzes
a complex architecture problem, researches market benchmarks, synthesizes competing
proposals, and runs them past a ruthless anti-patch critic in a bounded self-refine
loop — then freezes for a human debate before any tickets are created. This state is
what travels between its four cyclic nodes; it never mutates the lifecycle's state.yml.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")

CouplingRisk = Literal["low", "medium", "high"]
CritiqueVerdict = Literal["STRONG", "WEAK", "COMPLACENT", "INSECURE"]
HumanDecision = Literal["approve", "refine", "abort"]


class Proposal(BaseModel):
    """A competing technical play produced by the Synthesizer."""
    model_config = _STRICT
    name: str
    approach: str                      # the technical move
    tradeoffs: str
    security_posture: str              # how it meets the security business_criteria
    coupling_risk: CouplingRisk


class Critique(BaseModel):
    """The Ruthless Critic's verdict over the proposals (the anti-patch filter)."""
    model_config = _STRICT
    verdict: CritiqueVerdict
    vetoed: list[str] = Field(default_factory=list)    # rejected proposal names
    reasons: list[str] = Field(default_factory=list)
    must_fix: list[str] = Field(default_factory=list)  # what a refine must address


class StrategyState(BaseModel):
    """The strategist graph's state. Inputs are given; the rest is filled by the nodes."""
    model_config = _STRICT

    # --- INPUT (dynamic, per problem) ---
    target_context: str                                # e.g. "<your-product> module-audit subsystem"
    historical_debt: str = ""                          # prior code / half-done notes
    business_criteria: list[str] = Field(default_factory=list)  # security / efficiency / standard…

    # <TICKET-ID> framework release layer (Pilar 1.2 runtime injection): workspace context loaded
    # mechanically from forge.config.yml at session build time. Exposed in each
    # WorkRequest context dict for agents to consume symbolically. Optional +
    # default None for backward-compat with existing strategy session checkpoints.
    workspace: Optional[dict] = None

    # --- WORKING (cyclic) ---
    local_findings: Optional[str] = None               # Archaeologist
    market_findings: Optional[str] = None              # Consultant
    proposals: list[Proposal] = Field(default_factory=list)  # Synthesizer
    critique: Optional[Critique] = None                # Critic
    refine_count: int = 0
    max_refines: int = 3

    # --- OUTPUT (post-critic, for the human gate) ---
    executive_report: Optional[str] = None             # frozen + shown at the interrupt
    human_decision: Optional[HumanDecision] = None
