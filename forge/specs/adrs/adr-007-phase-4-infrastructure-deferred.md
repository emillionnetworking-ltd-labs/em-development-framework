---
id: ADR-007
title: Phase 4 infrastructure deferred (telemetry + OPA + multi-agent coordination)
status: accepted
date: 2026-06-01
supersedes: null
superseded_by: null
---

# ADR-007: Phase 4 Infrastructure Deferred

## Status

**Accepted** (2026-06-01, SCRUM-611 Wave 43, Sprint 23 Backlog Discipline). Authored retroactively to close the ADR numbering gap (existing ADRs: 001-006, 008, 009, 010; ADR-007 slot was empty).

## Context

The framework's planned evolution includes a **Phase 4** of infrastructure additions designed to scale governance beyond the single-operator pattern:

- **§4.1 Multi-agent coordination** — `_StateLock`-equivalent semantics across distinct agent identities, save_state tmp+rename atomicity, telemetry hooks for sub-agent spawning patterns.
- **§4.2 Telemetry collection (OTel-style)** — a `forge/tools/telemetry-summary.py` aggregator over `forge/telemetry/*.jsonl` event files, enabling load characterization and AI self-diagnosis dashboards.
- **§4.3 OPA-based policy enforcement** — open-policy-agent bundles for runtime gate checks (extending the static schema-validation layer to dynamic action-level policies).

When `pending-improvements.yml` was created (SCRUM-481, 2026-05-17), multiple entries cited "ADR-007 §4.x" as their gating source:

- `phase-4-2-otel` (cites §4.2)
- `phase-4-3-opa` (cites §4.3)
- `future-a-stress-test` (depends on Phase 4 telemetry tooling)
- `g15-telemetry-retention-policy` (depends on Phase 4 telemetry tooling)

But the ADR was **never authored**. The references hung against an empty slot, creating two problems:

1. **Citation gap**: future readers (auditors, operators, agents) following the source link found a 404.
2. **Mechanical drift**: the AUTO triggers for `phase-4-2-otel`, `future-a-stress-test`, `g15-telemetry-retention-policy` reference filesystem paths under `forge/telemetry/` and `forge/tools/telemetry-summary.py` — paths that **don't exist** because the underlying tooling was never built. The triggers were silently DEAD (`python3 -c` exits rc=1 on FileNotFoundError; framework reads as "not eligible" forever).

The 2026-06-01 architectural re-review of `forge/registers/` (the analysis that produced SCRUM-611) surfaced both problems. This ADR addresses problem #1 directly; problem #2 is addressed via the new `aspirational: true` trigger flag (introduced in the same wave).

## Decision

**Document the Phase 4 deferral as an explicit architectural decision.** The framework is NOT actively building Phase 4 infrastructure as of 2026-06-01. Activation is conditioned on operator-driven events:

- **§4.1 multi-agent**: activates when a second contributor will join framework work within 30 days (operator explicit decision — see `phase-4-3-opa` trigger).
- **§4.2 telemetry**: activates when traffic / event volume justifies (e.g., >1000 events/day averaged over 30 days — see `phase-4-2-otel` trigger).
- **§4.3 OPA**: activates jointly with §4.1 or §4.2; depends on the surface needing dynamic policy enforcement beyond what static schemas provide.

Until activation:

- The aspirational entries in `pending-improvements.yml` carry `trigger.aspirational: true` (schema field introduced in SCRUM-611 Wave 43).
- The bi-directional trigger health guard (`test_pending_improvements_triggers.py`, also from SCRUM-611) exempts aspirational entries from existence checks.
- No CI gate, no test, no skill depends on Phase 4 tooling.

When activation later occurs (operator-driven), a **superseding ADR** flips:

1. `superseded_by: ADR-NNN` on this ADR.
2. `aspirational: false` on the relevant `pending-improvements.yml` entries.
3. Path renames in the trigger commands to point at the now-built tooling.

## Consequences

- **Citation gap closed**: every existing reference to "ADR-007 §4.x" in `pending-improvements.yml` (and any future doc) lands on real content.
- **Mechanical exemption**: aspirational entries are now explicitly machine-distinguishable from near-term-actionable entries. The trigger-health guard reports zero false positives.
- **Audit trail discipline**: the ADR numbering gap (001-006, 008, 009, 010) is closed without renumbering — which would have broken every existing citation.
- **Operator clarity**: a contributor reading `pending-improvements.yml` sees the aspirational flag + the linked ADR, immediately understanding why those entries don't fire and what would change that.
- **No tooling work shipped here**: this ADR commits the framework to NOT building Phase 4 infrastructure preemptively. It does not pre-commit to building it later either — that's a separate operator decision.

## Unparking Criteria (Activation Conditions)

The aspirational entries flip to active status when:

### For §4.2 telemetry (`phase-4-2-otel`, `future-a-stress-test`, `g15-telemetry-retention-policy`):

Both must hold:
1. Operator decides Phase 4 telemetry is justified (typically driven by load or multi-agent activation).
2. `forge/tools/telemetry-summary.py` and `forge/telemetry/*.jsonl` event collection are built (separate wave) — at which point the existing trigger commands resolve correctly and `aspirational: true` is removed.

### For §4.3 OPA (`phase-4-3-opa`):

Operator decides a second contributor will join framework work within 30 days, OR a specific surface requires dynamic policy enforcement beyond static schema validation. Currently a `manual` trigger; activation is non-mechanical.

### For §4.1 multi-agent:

Currently no dedicated `pending-improvements.yml` entry; if a future entry is needed (e.g. for a specific multi-agent coordination feature), it inherits this ADR's deferral status until activation conditions are met.

## Alternatives Considered

### A — Withdraw all Phase-4-dependent entries

Rejected. Withdrawal would erase the operator's intent to monitor Phase 4 activation conditions. The entries are valid latent watchpoints — they just need an explicit aspirational marker rather than removal.

### B — Renumber ADRs to close the gap (ADR-007 = current ADR-008, etc.)

Rejected. Renumbering breaks every existing reference. `phase-4-2-otel` cites ADR-007 by number; renumbering invalidates that cite. The cost of touching every cross-reference across `pending-improvements.yml`, `workflow-standards.mdc`, integration-state.md, etc., for a cosmetic gap fix is much higher than just authoring the missing ADR.

### C — Author ADR-007 retroactively (this ADR)

**Accepted.** Documents the deferral that was implicit, restores audit-trail confidence, and gives the new `aspirational: true` flag a citable home.

### D — Leave the gap permanent + accept dead triggers

Rejected. Silent trigger death is exactly the kind of governance drift the framework is trying to prevent (per §23 native-freedom vs lifecycle: aspirational entries violate trigger #2 "new test that gates CI" only insofar as nobody guards them; the new test in SCRUM-611 closes that loop).

## References

- **SCRUM-481** — original creation of `pending-improvements.yml` that introduced the empty ADR-007 references.
- **SCRUM-611** (this wave) — codified the retroactive ADR + the `aspirational` schema field + the bi-directional trigger guard.
- **ADR-010** — parallel retroactive ADR pattern (parking sweep). Both ADRs close governance gaps without renumbering.
- **§23** (`workflow-standards.mdc`) — Native freedom vs lifecycle policy; classifies this kind of policy ADR as framework-obligatory.
- **`pending-improvements.yml`** entries: `phase-4-2-otel`, `phase-4-3-opa`, `future-a-stress-test`, `g15-telemetry-retention-policy` — the entries cited above.
- **`forge/tools/_tests/test_pending_improvements_triggers.py`** — the mechanical guard that this ADR pairs with.
