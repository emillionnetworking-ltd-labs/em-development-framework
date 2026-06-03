---
id: ADR-003
title: NOT-§15 AUTH Change-Control
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---

# ADR-003: NOT-§15 AUTH Change-Control

## Context

The em-ecosystem AUTH domain (`nexacore-api/src/auth/**`, `src/audit/**`, `prisma/schema.prisma`) is the most blast-radius-heavy code in the project. A bug there means data exposure, auth bypass, or audit-trail integrity loss — categories of failure that cannot be rolled back cheaply.

Concurrently, autonomous AI-driven workflows (which this framework exists to support) have an inherent asymmetry: a wrong line of code in a CRUD module is a learning experience; a wrong line in `auth/login-security.service.ts` is an incident.

The framework needed a constitutional rule that:

1. **Prevents** AI from autonomously modifying AUTH paths without explicit operator-authored grounding.
2. **Survives** context truncation and memory loss (i.e. is enforced even when the AI doesn't remember it).
3. **Doesn't kill** legitimate AUTH work — it can still happen, just with a different review path.

## Decision

Adopt the **NOT-§15** policy as a permanent, multi-layer constraint on autonomous AUTH changes.

Layer 1: **policy text** in `ai-specs/specs/workflow-standards.mdc §15` — the canonical written statement, including:

- AUTH-domain paths enumerated: `nexacore-api/src/auth/**`, `nexacore-api/src/audit/**`, `nexacore-api/prisma/schema.prisma`.
- Required workflow: explicit Jira ticket BEFORE work; PRs split if cross-domain (no mixing AUTH with non-AUTH); separate review path per §15.3.3; never `--no-verify` on hooks.

Layer 2: **memory enforcement** via `feedback_auth_change_control` (operator-set permanent memory). The AI reads this on every conversation start; the policy persists across sessions.

Layer 3: **grep audit at every `/verify`**. The skill mandates `git diff --staged --name-only | grep -E "(auth/|audit/|prisma/schema)"` — must return empty. The operator can read this in the verify report.

Layer 4: **CODEOWNERS in em-ecosystem** (post-SCRUM-453). Path-anchored rules ensure GitHub auto-requests operator review on any PR touching AUTH paths. This is the git-level safety net even if Layers 1-3 fail.

## Consequences

### Positive

- **Zero AUTH incidents** introduced by the autonomous workflow across the audited timeframe (2026-04 onward).
- **Constitutional clarity for AI**. The policy is concrete (specific paths) and observable (grep). No interpretive ambiguity.
- **Compatible with iterative AI behaviour**. Re-enrichment can happen freely on a NOT-§15 ticket; only the path-restriction matters.

### Negative

- **Legitimate AUTH improvements require manual operator engagement**. Velocity cost: real but accepted. The operator pays this cost knowingly.
- **Memory-as-primary-enforcement is fragile across actors**. A new contributor (human or AI without `feedback_auth_change_control` loaded) would not know the rule. Layer 4 (CODEOWNERS) is the protective fallback; this ticket (SCRUM-473) is partially motivated by getting framework-side CODEOWNERS in place to mirror em-ecosystem's.

### Operational

Audited compliance across SCRUM-461, SCRUM-462, SCRUM-463, SCRUM-464, SCRUM-465, SCRUM-467, SCRUM-468, SCRUM-469, SCRUM-470, SCRUM-471, SCRUM-472, SCRUM-473: **zero violations**. Every `/verify` report has run the grep and confirmed empty.

A near-violation pattern observed: when audits surface AUTH-adjacent issues (e.g. SCRUM-433's 13 inline error strings in `auth/`), the operator manually authors the Jira ticket BEFORE work begins, threading the NOT-§15 workflow correctly.

## Alternatives Considered

- **No gating** — rejected. The asymmetric blast radius makes this untenable. Even one wrong-line incident in AUTH would cost more than the entire velocity-tax of the gate.
- **Gate by grep only, no CODEOWNERS / memory** — rejected. Relies on the AI being prompted to grep at the right time. Fails under context truncation and across operators.
- **Wider gate** (all `src/**` requires explicit operator ticket) — rejected. Kills productivity for everything non-AUTH. The whole framework exists to make non-AUTH work fast.
- **Narrower gate** (only `auth/` not `audit/` or `prisma/schema.prisma`) — rejected. Audit-trail integrity is part of AUTH's threat model; schema changes can introduce stealth-auth-bypass via field defaults.
- **Time-window override** ("AUTH changes allowed during operator-supervised sessions") — rejected. Hard to define operationally; AI cannot reliably detect supervision.

## References

- `ai-specs/specs/workflow-standards.mdc §15` — canonical policy text.
- `~/.claude/projects/-home-em-admin/memory/feedback_auth_change_control.md` — permanent memory entry codifying the rule for AI sessions.
- `ai-specs/specs/audit-standards.mdc §6.3` — post-fix verification + recurrence prevention (cross-references NOT-§15 for AUTH-class findings).
- SCRUM-453 — introduced em-ecosystem CODEOWNERS (commit `7e21b2a`) for Layer 4 enforcement.
- `~/projects/em-ecosystem/.github/CODEOWNERS` — 35-line file with AUTH-anchored rules under `@emillionnetworking`.
- SCRUM-462, SCRUM-464 — audited NOT-§15 compliance (zero violations).
- ADR-001 (`adr-001-fw-004-state-machine.md`) — lifecycle state machine that surfaces the grep gate at `/verify`.
- ADR-005 (`adr-005-plan-verify-record-trilogy.md`) — verify report is the artifact that records the NOT-§15 grep result per ticket.
