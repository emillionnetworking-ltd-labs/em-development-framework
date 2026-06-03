---
id: ADR-005
title: Plan + Verify + Record Trilogy
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---

# ADR-005: Plan + Verify + Record Trilogy

## Context

Each ticket in this framework produces durable artifacts that have to answer three distinct questions:

1. **Before code lands**: what are we going to build, and how?
2. **At the moment merging is considered**: did we actually build it, and is it safe to merge?
3. **After merging**: what really happened, and what should anyone reading this later know?

A single per-ticket document cannot answer all three without one of two failure modes:

- **The plan rots into a record**. The pre-merge gate is lost; you cannot reconstruct what the verdict was, why the verdict was reached, or what classifications were applied to deviations.
- **The record overwrites the plan**. Lost: the pre-build contract, the rationale for what was scoped in vs out, the architectural snapshot at planning time.

We needed three artifacts, each frozen at a specific lifecycle phase, with explicit references between them so downstream consumers can replay the full ticket history.

## Decision

**Every ticket produces exactly three artifacts**, each frozen at a specific phase, each schema-validated, each linked to the others:

### Plan (`<ticket>_<scope>.md` under `plans/<sprint>/`)

- **Written during**: `/plan`.
- **Frozen at**: `/develop` start (status transitions from `draft` to `frozen` in frontmatter).
- **Purpose**: pre-build contract. Captures: codebase state snapshot, regression impact analysis, step-by-step implementation, acceptance criteria, definition of done.
- **Schema**: `plan.schema.yml`.

### Verify (`<ticket>_verify.md` under the same `plans/<sprint>/`)

- **Written during**: `/verify`.
- **Frozen at**: `/commit` start.
- **Purpose**: pre-merge gate. Captures: per-step plan compliance status (DONE / DONE-DEVIATED / PARTIAL / SKIPPED), deviation classifications (Accepted-Trivial / Accepted-Quality / Accepted-Risk / Deferred / Pre-existing / Scope-Gap), code-quality check results, regression verification, verdict (PASS / PASS-WITH-DEBT / BLOCKED-RISK / BLOCKED-GAP / BLOCKED-BUILD).
- **Schema**: `verify.schema.yml`.

### Record (`<ticket>_<scope>.md` under `records/<sprint>/`)

- **Written during**: `/update-docs`.
- **Frozen at**: lifecycle close (state `documented`).
- **Purpose**: post-merge truth. Captures: actual commits, test results, deviations resolved (classifications imported from verify), bugs found, documentation updates, lessons learned, recommended follow-ups, rollback playbook.
- **Schema**: `record.schema.yml`.

**Cross-references are mandatory**: plan references its predecessor in `last_completed_ticket`; verify references the plan in `plan_path`; record references both plan and verify in `plan_path` and `verify_path`.

**Deviation classifications happen once**, in the verify report. The record imports them — does not re-classify. This rule is codified in `/update-docs` Part 5 Step 13.

## Consequences

### Positive

- **Each artifact answers a single question**. Plan = forward design. Verify = pre-merge gate. Record = post-merge truth. No conflation.
- **Audit replay is possible**. Reading plan → verify → record reconstructs the entire ticket lifecycle: what was planned, what gate it passed (or didn't), what actually happened post-merge.
- **Classifications are traceable**. A deviation classified `Accepted-Quality` in `/verify` shows up in `/update-docs` under the same classification, with a follow-up column for any tech-debt Jira ticket created.
- **Phase-specific freezing** prevents retroactive rewriting. The plan cannot be edited after `/develop` starts; the verify cannot be edited after `/commit` starts. This makes the artifacts a forensic record, not a moving target.

### Negative

- **3× the writing per ticket**. The plan is the heaviest (codebase verification, impact analysis); the verify is medium (gate); the record is lighter (deviations imported). Total per-ticket prose load is non-trivial.
- **Some content duplicates across docs**. Specifically the deviation table appears in both verify (with classifications) and record (with follow-up status). Mitigated by `/update-docs` rule: import from verify, do not re-classify.
- **Three documents per ticket means three places drift can hide**. If the plan says "10 files" and the verify says "11 files" and the record says "12 files", which is true? Mitigated by schema validation + the lifecycle order: each successive artifact reads the prior one as ground truth.

### Operational

Every lifecycle ticket since SCRUM-415 has produced all three. The record template explicitly cites the verify path in `verify_path` frontmatter and imports classifications from §5. SCRUM-470 → SCRUM-471 → SCRUM-472 → SCRUM-473 (this ticket) demonstrate the import flow operating cleanly.

The audit memo `audit-check-2026-05-14.md` documented compliance with the trilogy across the audited timeframe. No tickets were merged without all three.

## Alternatives Considered

- **One document that evolves through the lifecycle** (plan content gets overwritten by verify content gets overwritten by record content) — rejected. Pre-merge gate cannot be reconstructed; deviations have no place to be classified once the artifact is "the record".
- **Plan + Record only, no Verify** — rejected. Where does the verdict live? Where do deviation classifications happen? Implicit pre-merge gating means the gate is invisible.
- **Two documents: a "checked-in spec" (plan + verify combined) + a "post-mortem" (record)** — rejected. Combining plan and verify into one doc means verify edits would touch the plan body, breaking the freeze rule and the schema constraint.
- **Five documents** (split verify into "deviation-class.md" + "regression.md", and record into "implementation.md" + "lessons.md") — rejected. Overhead exceeds benefit; the existing three-section structure inside each artifact handles the sub-concerns well.
- **No artifacts; rely on git history + Jira** — rejected. Git history shows code changes, not rationale or deviations. Jira shows tickets but not technical detail. The artifacts are the bridge.

## References

- `~/.claude/commands/plan.md` — skill that produces the plan; template defines 16 backend sections.
- `~/.claude/commands/verify.md` — skill that produces the verify report; template defines the verdict ladder.
- `~/.claude/commands/update-docs.md` — skill that produces the record; Part 5 mandates importing classifications from verify.
- `ai-specs/schemas/plan.schema.yml` / `verify.schema.yml` / `record.schema.yml` — structural contracts (see ADR-004).
- SCRUM-415 — established the trilogy pattern.
- Recent examples of all three documents per ticket: SCRUM-470 (Phase 1 cleanup), SCRUM-471 (evals harness), SCRUM-472 (backup + DR).
- ADR-001 (`adr-001-fw-004-state-machine.md`) — state machine that gates each lifecycle phase, ensuring each artifact is produced before the next phase advances.
- ADR-004 (`adr-004-schema-driven-validation.md`) — every artifact is schema-validated.
