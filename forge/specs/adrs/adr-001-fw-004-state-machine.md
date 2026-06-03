---
id: ADR-001
title: FW-004 Lifecycle State Machine
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---

# ADR-001: FW-004 Lifecycle State Machine

## Context

Before FW-004 (early 2026), the ticket lifecycle was advisory. Each skill (`/enrich-us`, `/plan`, `/develop`, `/verify`, `/commit`, `/update-docs`) checked its own preconditions in prose — phrases like "before proceeding, confirm that the plan is complete". Compliance was operator-honored: nothing prevented a skill from running out of order, and nothing recorded the fact that a step had been completed.

The cost surfaced in two ways:

1. **Skipped steps with no audit trail**. The `audit-check-2026-05-14.md` memo documented multiple instances of `/commit` running without `/verify`, leaving deviation classifications implicit and post-merge surprises in their wake.
2. **No canonical record per ticket**. The state of "what step is this ticket on?" lived only in the operator's head or in scattered records. A new conversation could not pick up cleanly mid-lifecycle.

The framework needed (a) enforcement of the lifecycle order and (b) a single source of truth per ticket — without sacrificing the markdown-first, human-readable character of the rest of `ai-specs/`.

## Decision

Introduce **FW-004**: a code-enforced state machine with six discrete states, backed by a per-ticket YAML state file and a CLI tool that gates every skill.

- **Six states**, in order: `enriched` → `planned` → `developing` → `verified` → `committed` → `documented`.
- **State file location**: `ai-specs/changes/<module>/state/<ticket>.yml`. Gitignored (per-machine), but written deterministically by the tooling and backed up by the SCRUM-472 backup script.
- **Canonical tool**: `ai-specs/tools/state-machine.py` (332 lines). Three subcommands: `check <step> <ticket> <module>` (pre-flight; rc=0 proceed, rc=1 refuse, rc=2 bootstrap), `advance <step> <ticket> <module> --field key=value` (post-step; writes the YAML), `state <ticket> <module>` (read-only inspection).
- **Schema validation at every advance**: the resulting YAML must validate against `ai-specs/schemas/state.schema.yml`. Each step's allowed `--field` keys are whitelisted in `state-machine.py`'s `COMMAND_RULES`.
- **Skill integration**: every lifecycle skill calls `check` as its first action and `advance` as its last action. Refusal at `check` cannot be bypassed in skill prose — the rc=1 surfaces verbatim to the operator.

## Consequences

### Positive

- **Steps cannot be skipped**. `/commit` refuses unless `steps.verify.done == true` and the verdict is not `BLOCKED-*`. `/develop` refuses unless `steps.plan.done == true` and `steps.plan.schema_validated == true`. The gate is mechanical, not aspirational.
- **Single source of truth per ticket**. The state file is the canonical "where is this ticket?" record. A new conversation can read `state.yml`, see `state: developing`, and resume cleanly.
- **Verdict gating**. The `verify` step stores `verdict: PASS | PASS-WITH-DEBT | BLOCKED-RISK | BLOCKED-GAP | BLOCKED-BUILD`. `/commit`'s pre-flight reads it; the BLOCKED-* verdicts halt the lifecycle until the underlying issue is addressed.
- **Audit trail**. Every advance writes a timestamp. The state file is a per-ticket lifecycle log.

### Negative

- **Bootstrap dependency**. Every lifecycle skill carries an extra `python3 ai-specs/tools/state-machine.py check ...` invocation. Cheap (~30ms) but ubiquitous.
- **Gitignored state files**. State files don't survive a clean reclone; backup-and-restore is the only path. Closed operationally by SCRUM-472 (backup-operator-state.sh + RECOVERY.md).
- **Schema migration cost**. Changing `state.schema.yml` requires care: existing state files may fail validation. Mitigated by CI Job 3 (informational, non-blocking) and by versioning the schema reference inside each state file's frontmatter.

### Operational

Every lifecycle ticket since SCRUM-415 has run through FW-004. Production usage observed in SCRUM-463 (first full lifecycle), SCRUM-467/468/469 (Phase 1 substrate hardening), SCRUM-470 (Phase 1 cleanup), SCRUM-471/472/473 (Phase 2). Zero merged tickets bypassed the gate.

## Alternatives Considered

- **Skill prose only (status quo)** — rejected. Empirically failed: the 2026-05-14 audit found multiple bypassed steps. Prose enforcement does not scale beyond perfectly-attentive operators.
- **Server-side state in Jira** — rejected. Depends on Jira availability; cannot gate locally during a `/plan` run; introduces a Jira-down failure mode for what should be a local-first lifecycle.
- **Git-hook-based enforcement** (pre-commit hook checks the state) — rejected. Hooks fire only at commit time, which is too late: by then, the operator has already invested effort in a wrong-order workflow. The check needs to fire at skill entry, not commit entry.
- **Implicit state from records** (derive lifecycle position from the presence/absence of `_backend.md`, `_verify.md`, `_record.md` files) — rejected. Records and plans are written documents; their existence does not imply schema-valid completion. Also: records land at `/update-docs`, after the lifecycle has effectively finished — too late to gate anything.

## References

- `ai-specs/tools/state-machine.py` — canonical implementation (332 lines).
- `ai-specs/tools/init-state.py` — bootstrap helper invoked by `advance enrich-us` on first run.
- `ai-specs/schemas/state.schema.yml` — schema enforced at every advance.
- `ai-specs/changes/STATE-MACHINE.md` — concept doc and design rationale.
- SCRUM-415 — initial FW-004 implementation.
- SCRUM-463 — first production lifecycle gate.
- SCRUM-467 / SCRUM-468 / SCRUM-469 — Phase 1 substrate-hardening tickets, all schema-gated through FW-004.
- SCRUM-470 — Phase 1 cleanup; tested the gate's behaviour under cleanup-ticket conditions.
- SCRUM-471 / SCRUM-472 / SCRUM-473 — Phase 2 tickets; ongoing production usage.
- `~/.claude/commands/<skill>.md` — every lifecycle skill carries the "Pre-flight: State Machine Guard (FW-004 — MANDATORY)" block.
