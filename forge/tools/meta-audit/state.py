# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""meta-audit/state.py — typed state for the framework meta-audit.

LangGraph "centralized State" modeled with Pydantic (no langgraph import).
The auditor's own state obeys the rigidity it checks elsewhere:
`extra="forbid"` means no free-text outside the typed fields. See ADR-009.

Status calibration (operator-mandated, <TICKET-ID>):
  - BROKEN  → genuine determinism breaker (missing/malformed schema; a tool
              error path that exits 0; a success path that exits >0; outbound
              network in a lifecycle tool; state writes without a lock).
  - WARNING → partial hardening gap (some nested schema objects not closed;
              a tool with no explicit success exit relying on fall-through).
  - CLEAN   → no findings.
Rationale: with today's schema state (many unlocked nested objects), treating
every gap as BROKEN would exit 1 on day one and bury the signal. The tool must
be informative, not a wall of red.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PhaseStatus = Literal["CLEAN", "WARNING", "BROKEN"]

# Status severity ranking for monotonic escalation + aggregation.
_RANK: dict[str, int] = {"CLEAN": 0, "WARNING": 1, "BROKEN": 2}


class PhaseAudit(BaseModel):
    """Audit result for a single lifecycle stage.

    The four metrics are tri-state: True (verified), False (verified bad),
    or None (not applicable to this stage / not yet evaluated).
    """

    model_config = ConfigDict(extra="forbid")

    idempotency_safe: Optional[bool] = None
    deterministic_output: Optional[bool] = None
    predictable_exit_code: Optional[bool] = None
    context_isolated: Optional[bool] = None
    status: PhaseStatus = "CLEAN"
    errors: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)

    def _escalate(self, level: PhaseStatus) -> None:
        if _RANK[level] > _RANK[self.status]:
            self.status = level

    def warn(self, message: str) -> None:
        """Record a WARNING-level finding (does not flip a metric to False)."""
        self.errors.append(f"[WARNING] {message}")
        self._escalate("WARNING")

    def broke(self, message: str) -> None:
        """Record a BROKEN-level finding (a genuine determinism breaker)."""
        self.errors.append(f"[BROKEN] {message}")
        self._escalate("BROKEN")


class AuditState(BaseModel):
    """Centralized state threaded through the verification nodes."""

    model_config = ConfigDict(extra="forbid")

    subsystem: str = "lifecycle"
    started_at: str
    framework_root: str
    phases: dict[str, PhaseAudit] = Field(default_factory=dict)

    def worst_status(self) -> PhaseStatus:
        """The most severe status across all phases — drives the conditional edge."""
        worst: PhaseStatus = "CLEAN"
        for audit in self.phases.values():
            if _RANK[audit.status] > _RANK[worst]:
                worst = audit.status
        return worst
