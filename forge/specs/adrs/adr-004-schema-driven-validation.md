---
id: ADR-004
title: Schema-Driven Artifact Validation
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---

# ADR-004: Schema-Driven Artifact Validation

## Context

Lifecycle artifacts in this framework are load-bearing for downstream automation:

- `state-machine.py` reads `state.yml` to decide whether the next skill can run.
- `/commit` reads the verify report's `verdict` field to decide whether merging is allowed.
- `/update-docs` reads the verify report's deviation classifications to populate the record without re-classifying.
- `recommend-followups.py` parses record §11 to draft Jira ticket entries.
- Audit tools scan integration-state.md and standards files programmatically.

If these artifacts were free-form markdown, the slightest drift in section names, field naming, or YAML structure would break the consumers. We have already lived through a non-trivial backfill of legacy artifacts (the Sprint 14 cleanup, framework commit `a55fc30`) — drift is empirically expensive once it accumulates.

We needed structural contracts on every lifecycle artifact, enforced at PR time and at lifecycle-step advance time, without sacrificing the markdown-readable character of plans, records, and verify reports.

## Decision

**Every lifecycle artifact has a JSON-schema-validated structural contract.**

- Schemas live in `ai-specs/schemas/*.yml` (YAML for human authoring of the schema itself; JSON-schema draft 2020-12 semantics).
- The validator (`ai-specs/tools/validate-artifact.py`, 335 lines) is two-stage:
  1. **Parse** the markdown artifact into a structured object `{frontmatter, headings, ...}`.
  2. **Validate** that object against the schema referenced in the artifact's frontmatter `schema:` field.
- Schemas exist for: `plan.schema.yml`, `verify.schema.yml`, `record.schema.yml`, `state.schema.yml`, `shadow-decision.schema.yml`, `bypass-log.schema.yml`, and others.
- Each artifact's frontmatter starts with a `schema:` field naming its contract. This makes self-validation possible without external lookup tables.

**Enforcement at three points**:

1. **Skill advance**: `state-machine.py advance plan|verify|update-docs` requires `--field schema_validated=true`. The agent's assertion that `/validate-artifact <path>` returned exit 0.
2. **CI Job 2 (`schema-validate-changes`)**: runs `validate-artifact.py` on every `ai-specs/changes/**/*.md` modified by the PR. Blocking — fails the PR build if any artifact is invalid.
3. **CI Job 3 (`schema-validate-historical`)**: runs `validate-artifact.py` against the FULL `ai-specs/changes/` corpus when schemas change OR on push to main. **Informational** (`continue-on-error: true`) — surfaces drift in legacy artifacts without blocking new work.

## Consequences

### Positive

- **Drift caught at PR time**. Job 2 blocks merges of malformed artifacts; the operator sees a clear error message naming the failing field.
- **Downstream consumers can rely on stable schemas**. `/commit` trusts `verify.verdict` exists; `/update-docs` trusts `verify.deviation_counts.accepted_risk` exists.
- **New artifact types inherit the pattern cheaply**. Adding a new artifact = adding one YAML schema + one frontmatter reference + one CI job line.
- **Historical drift surfaced visibly**. Job 3 reports approximately 30 of 684 legacy artifacts fail current schemas. Non-blocking, but tracked.
- **The schema doubles as documentation**. Anyone writing a new record can read `record.schema.yml` to know what sections are required.

### Negative

- **Schema migrations require care**. Adding a new required field to `record.schema.yml` retroactively invalidates every existing record. Mitigated by: (a) keeping required fields minimal, (b) preferring `additionalProperties: true` so new optional fields don't break legacy artifacts, (c) Job 3 being informational so legacy drift doesn't block velocity.
- **YAML-schema authoring is a niche skill**. The operator/AI must know JSON-schema's gotchas (`$defs`, `oneOf` vs `anyOf`, etc.) when adding a new artifact type. Mitigated by copying from existing schemas.

### Operational

Every Phase 1 and Phase 2 lifecycle artifact has passed schema validation. Zero merges with `schema_validated=false`. Examples:

- SCRUM-467 (CI workflow introduction) — first ticket where Job 2 went live.
- SCRUM-468 / SCRUM-469 — Phase 1 substrate hardening — every plan, verify, record schema-validated.
- SCRUM-470 — Phase 1 cleanup — same.
- SCRUM-471 / SCRUM-472 / SCRUM-473 — Phase 2 — same.

## Alternatives Considered

- **Free-form markdown** (status quo prior to schema introduction) — rejected. Drift inevitable; the Sprint 14 backfill is the documented case study.
- **YAML-only artifacts** (drop markdown) — rejected. Humans prefer markdown for prose-heavy docs (records' "Lessons Learned" section is irreducibly prose).
- **JSON-only artifacts** — rejected for the same reason; worse than YAML for human authoring.
- **Lint-only enforcement** (Markdown lint rules, no schemas) — rejected. Lint catches style; it does not catch structural contracts. A record could lint-pass with an empty `Test Results` section.
- **Schema validation only at commit time (no advance-time check)** — rejected. Catching invalid artifacts at `/commit` is too late; the operator has already spent effort on `/develop` and `/verify`. The advance-time check is cheap and catches problems immediately.

## References

- `ai-specs/schemas/` — schema directory.
  - `plan.schema.yml`, `verify.schema.yml`, `record.schema.yml`, `state.schema.yml`, plus a handful of operational schemas.
- `ai-specs/tools/validate-artifact.py` — canonical validator (335 lines).
- `ai-specs/tools/state-machine.py` — enforces `schema_validated` field at advance time.
- `.github/workflows/ci.yml` — Jobs 2 (PR-time, blocking) and 3 (push-time, informational).
- SCRUM-467 — introduced the CI workflow and the schema-validation jobs.
- SCRUM-469 — added pytest coverage for `validate-artifact.py` (tests in `ai-specs/tools/_tests/test_validate_artifact.py`).
- SCRUM-470 — fixed Bug A (Path object handling in `validate-artifact.py:165`) discovered by the SCRUM-469 tests.
- ADR-001 (`adr-001-fw-004-state-machine.md`) — the state machine that enforces the `schema_validated` flag is itself schema-validated.
