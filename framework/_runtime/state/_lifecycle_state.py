# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_lifecycle_state.py — the typed in-memory model of a ticket's lifecycle state.

<TICKET-ID> (steel-foundations refactor #2). `LifecycleState` is a strict-typed
Pydantic MIRROR of `forge/schemas/state.schema.yml`. The orchestrator and the
support-tool libraries hold this in RAM; disk (`state.yml`) stays the single
durable source of truth, and `state.schema.yml` stays the SCHEMA source of truth.

Anti-drift guard (decision A): `_tests/test_lifecycle_state.py` asserts that a
`LifecycleState` round-trips through `state.schema.yml` (dump → validate-artifact
→ PASS) and that the state-enum + per-step field-sets match the schema. Any drift
between this model and the schema turns that test red.

Note: the schema's `allOf`/`if`/`then` state-gating (which fields are required at
which state) is cross-field validation logic — NOT replicated here. The model
mirrors the STRUCTURE; the schema remains the authority for conditional gating.
Each model sets `extra="forbid"`, mirroring the <TICKET-ID>-hardened schema.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")
_STRICT_ALIASED = ConfigDict(extra="forbid", populate_by_name=True)

LifecycleStateEnum = Literal[
    "enriched", "planned", "developing", "verified", "committed", "documented", "closed",
]
Verdict = Literal["PASS", "PASS-WITH-DEBT", "BLOCKED-RISK", "BLOCKED-GAP", "BLOCKED-BUILD"]
DeviationCategory = Literal[
    "Accepted-Trivial", "Accepted-Quality", "Accepted-Risk",
    "Deferred", "Pre-existing", "Scope-Gap",
]
PlanComplianceStatus = Literal["DONE", "DONE-DEVIATED", "PARTIAL", "SKIPPED"]


# ----- per-step models (field-sets mirror state.schema.yml steps + COMMAND_RULES) -----

class StepEnrichUs(BaseModel):
    model_config = _STRICT
    done: bool
    timestamp: Optional[str] = None
    jira_hash: Optional[str] = None


class StepPlan(BaseModel):
    model_config = _STRICT
    done: bool
    timestamp: Optional[str] = None
    path: Optional[str] = None
    schema_validated: Optional[bool] = None


class StepDevelop(BaseModel):
    model_config = _STRICT
    done: bool
    timestamp: Optional[str] = None
    branch: Optional[str] = None
    last_commit: Optional[str] = None
    plan_compliance_summary: Optional[dict[str, PlanComplianceStatus]] = None


class StepVerify(BaseModel):
    model_config = _STRICT
    done: bool
    timestamp: Optional[str] = None
    verdict: Optional[Verdict] = None
    path: Optional[str] = None
    schema_validated: Optional[bool] = None
    deviations_count: Optional[int] = None


class StepCommit(BaseModel):
    model_config = _STRICT
    done: bool
    timestamp: Optional[str] = None
    pr: Optional[int] = None
    merge_commit: Optional[str] = None
    branch_deleted: Optional[bool] = None


class StepUpdateDocs(BaseModel):
    model_config = _STRICT
    done: bool
    timestamp: Optional[str] = None
    record_path: Optional[str] = None
    record_schema_validated: Optional[bool] = None
    ai_specs_commit: Optional[str] = None
    specs_updated: Optional[list[str]] = None


class Steps(BaseModel):
    model_config = _STRICT_ALIASED
    enrich_us: StepEnrichUs = Field(alias="enrich-us")
    plan: StepPlan
    develop: StepDevelop
    verify: StepVerify
    commit: StepCommit
    update_docs: StepUpdateDocs = Field(alias="update-docs")


class Deviation(BaseModel):
    model_config = _STRICT
    category: DeviationCategory
    description: str
    step: Optional[str] = None
    ref: Optional[str] = None
    jira_ticket: Optional[str] = None
    risk_description: Optional[str] = None
    compensating_controls: Optional[str] = None
    residual_risk: Optional[str] = None
    user_approved: Optional[bool] = None


class FollowUp(BaseModel):
    model_config = _STRICT
    title: str
    status: str
    reason: Optional[str] = None
    source_section: Optional[str] = None


class LifecycleState(BaseModel):
    """Typed mirror of a ticket-state.yml (validated by state.schema.yml on disk)."""
    model_config = _STRICT
    ticket: str
    module: str
    sprint: str
    state: LifecycleStateEnum
    steps: Steps
    deviations: Optional[list[Deviation]] = None
    follow_ups: Optional[list[FollowUp]] = None

    @classmethod
    def from_state_dict(cls, data: dict) -> "LifecycleState":
        """Load from a parsed state.yml dict (handles the hyphenated step keys)."""
        return cls.model_validate(data)

    def to_state_dict(self) -> dict:
        """Serialize back to the on-disk shape (hyphenated step keys, no nulls)."""
        return self.model_dump(by_alias=True, exclude_none=True)
