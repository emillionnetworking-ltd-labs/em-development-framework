# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_pending_improvements.py — typed mirror of pending-improvements.schema.yml.

<TICKET-ID> (framework release layer). Strict-typed Pydantic mirror — same pattern as
`_lifecycle_state.py` mirroring `state.schema.yml`. Disk YAML stays the single
durable source; the schema stays the contract authority; this module is the
typed in-memory model the cleanup tool operates on.

Anti-drift guard (decision A): `_tests/test_pending_improvements.py` asserts
that a `PendingRegistry.model_dump()` round-trips through
`pending-improvements.schema.yml` (write → `validate-artifact.py` → PASS).
Any drift between this model and the schema turns the test red.

The schema's `allOf`/`if`/`then` conditional (status=done requires
`resolution_evidence`) is replicated here via `@model_validator(mode='after')`.
Pydantic catches it in RAM; the schema catches it on disk; the round-trip
test ensures both layers stay aligned.
"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


_STRICT = ConfigDict(extra="forbid")


# ----- enum aliases (mirrors schema enums) -----

Status = Literal["waiting", "eligible", "manual-check-due", "done", "withdrawn"]
TriggerType = Literal["auto", "manual"]
ValueEstimate = Literal["low", "medium", "high", "critical"]
EvidenceSourceLiteral = Literal[
    "jira-ticket-done", "operator-approved",
]
# Note: "auto-trigger-failed" was REMOVED in <TICKET-ID> mid-implementation review.
# The existing triggers in pending-improvements.yml signal eligibility, not
# closure. A1 stays in the report (diagnostic) but cannot be a closure source.


# ----- regex patterns (must match the schema) -----

SPRINT_PATTERN = r'^(Sprint [0-9]+|SAT[0-9]+ S[0-9]+|backlog|Wave [0-9]+ - .+)$'
TICKET_PATTERN = r'^[A-Z][A-Z0-9]*-[0-9]+$'
ID_PATTERN = r'^[a-z][a-z0-9-]*$'


# ----- models (one per $def in the schema) -----


class Trigger(BaseModel):
    """Mirrors $defs.entry.properties.trigger."""

    model_config = _STRICT

    type: TriggerType
    check: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=60)
    aspirational: Optional[bool] = None  # <TICKET-ID> framework release layer — Phase-4-deferred infra exemption per ADR-007


class ResolutionEvidence(BaseModel):
    """Populated by `/sprint-cleanup` on transition to status=done.
    Append-only audit trail. Required when status=done (allOf in schema)."""

    model_config = _STRICT

    closed_at: date
    closed_by: EvidenceSourceLiteral
    closed_at_sprint: str = Field(pattern=SPRINT_PATTERN)
    note: Optional[str] = None


class PendingImprovementEntry(BaseModel):
    """Mirrors $defs.entry. Required: id, source, status, trigger.
    <TICKET-ID> adds: sprint, jira_ticket, resolution_evidence (all optional
    except resolution_evidence is required when status=done — enforced via
    `_evidence_required_when_done` model_validator)."""

    model_config = _STRICT

    # required (per schema)
    id: str = Field(pattern=ID_PATTERN)
    source: str = Field(min_length=5)
    status: Status
    trigger: Trigger

    # optional pre-<TICKET-ID>
    last_checked: Optional[date] = None
    next_check: Optional[date] = None
    cost_estimate: Optional[str] = None
    value_estimate: Optional[ValueEstimate] = None
    note: Optional[str] = None
    created_at: Optional[date] = None

    # <TICKET-ID>: sprint-cleanup automation surface
    sprint: Optional[str] = Field(default=None, pattern=SPRINT_PATTERN)
    jira_ticket: Optional[str] = Field(default=None, pattern=TICKET_PATTERN)
    resolution_evidence: Optional[ResolutionEvidence] = None

    @model_validator(mode="after")
    def _evidence_required_when_done(self) -> "PendingImprovementEntry":
        """Mirrors the schema's allOf if status=done then required: resolution_evidence."""
        if self.status == "done" and self.resolution_evidence is None:
            raise ValueError(
                f"entry {self.id!r}: status=done requires resolution_evidence "
                f"(<TICKET-ID> contract; see pending-improvements.schema.yml allOf)"
            )
        return self


class PendingRegistry(BaseModel):
    """Mirrors the top-level YAML shape. Required: version, generated_at, entries."""

    model_config = _STRICT

    version: Literal["1.0"]
    generated_at: date
    entries: list[PendingImprovementEntry]

    # ----- convenience filters for sprint-cleanup -----

    def filter_by_sprint(self, sprint: str) -> list[PendingImprovementEntry]:
        """Return entries with explicit sprint match. Null-sprint entries excluded
        (use `backlog_entries()` for those)."""
        return [e for e in self.entries if e.sprint == sprint]

    def backlog_entries(self) -> list[PendingImprovementEntry]:
        """Return entries with sprint=None (cross-sprint / future-* / audit-meta)."""
        return [e for e in self.entries if e.sprint is None]

    def by_id(self, entry_id: str) -> Optional[PendingImprovementEntry]:
        """Lookup by id."""
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None
