---
id: ADR-011
title: Parked specs (audit-standards + development_guide)
status: accepted
date: 2026-06-01
supersedes: null
superseded_by: null
---

# ADR-011: Parked Specs (audit-standards + development_guide)

## Status

**Accepted** (2026-06-01, SCRUM-613 Wave 45, Sprint 23 Backlog Discipline).

## Context

The 2026-06-01 architectural re-review of `forge/specs/` identified an asymmetry and an orphan:

### audit-standards.mdc (1120 LoC)

The spec describes the **audit subsystem** (11-phase audit framework, audit-phase runners, completion gates). The implementation was parked to `forge/_parked/` on 2026-05-30 per ADR-010 (SCRUM-609 Wave 41) when the cross-repo decoupling (SCRUM-572) rendered product-audit runners inoperative against the new mono-engine layout.

ADR-010 parked the **implementation** (tools + playbooks + schemas) but left the **spec** in `forge/specs/audit-standards.mdc` — shipping with the distribution archive while describing functionality unavailable at runtime. The asymmetry creates citation confusion for contributors reading `forge/specs/` expecting an authoritative spec.

### development_guide.md (239 LoC)

The spec self-declared deprecated in its own header (Wave 32 SCRUM-600 note):

> "Per strategy v2 Proposal D hybrid pattern, product-specific dev guides ultimately belong in the governed product's repo (e.g. em-ecosystem `lifecycle/specs/`) referenced via `<workspace.custom_standards.development>`. The content here is preserved for backward compat with the framework's current dogfood + as a reference template; future operators governing non-em-ecosystem products SHOULD author their own dev guide in their per-project custom_standards."

The file describes PostgreSQL schema setup + Prisma migrations + NestJS-specific module configuration + OAuth providers — product-specific content that no longer belongs in a generic framework distribution. It had 1 external reference in the active codebase (essentially orphan) and shipped to end-users who, per the file's own header, should NOT consume it.

## Decision

**Park both specs to `forge/_parked/specs/` for consistency with ADR-010's parking pattern.**

`forge/_parked/**` is already `export-ignore`d in `.gitattributes` since Wave 38 (SCRUM-606), so the parking removes both specs from the end-user distribution archive while preserving them in the source repository for contributors who need:

- **audit-standards.mdc**: design documentation for unparking the audit subsystem.
- **development_guide.md**: reference template when authoring a per-project `<workspace.custom_standards.development>` guide.

Each parked spec carries a header note pointing to this ADR, so a reader landing on either file immediately understands its parked status and the unparking criteria.

## Consequences

- **Distribution archive shrinks by ~1360 LoC** (audit-standards 1120 + development_guide 239), aligned with the Strategy v4 ship-clean pattern.
- **`forge/specs/` surface now matches the active framework reality** — parked subsystem specs go with their parked implementations.
- **Reference template for `development_guide.md` remains visible** to contributors via `forge/_parked/specs/` (NOT lost). The pattern is "parked, not deleted".
- **Citation confusion eliminated**: contributors reading `forge/specs/` no longer find specs describing functionality unavailable at runtime.
- **Bi-directional drift guard test** (`forge/tools/_tests/test_parked_specs.py`) defends the parking from accidental resurrection without an ADR superseding this one.

## Unparking Criteria

### audit-standards.mdc

Unparks **jointly with the audit subsystem**. Per ADR-010, the audit tools + playbooks + schemas unpark when both:
1. The framework re-engages with a governed product trail at a known path.
2. The audit runners are refactored to consume workspace metadata (`forge.config.yml`) instead of hardcoded product paths.

When ADR-010's unparking fires (separate wave authoring a superseding ADR), `audit-standards.mdc` rejoins `forge/specs/` in the same wave. The two parkings are mechanically coupled.

### development_guide.md

Unparks **only if a future operator chooses to maintain a framework-level product development guide** — a deliberate architectural reversal of the SCRUM-600 / Strategy v2 Proposal D pattern that pushed per-product dev guides into each governed project's `<workspace.custom_standards.development>` slot. This would require a separate ADR superseding ADR-011's deprecation rationale.

## Alternatives Considered

### A — Leave both specs in place

Rejected. Active asymmetry (parked tools + active specs for audit-standards; deprecated-but-shipping for development_guide) creates citation confusion and ships content end-users shouldn't consume per the files' own headers.

### B — Delete both outright

Rejected. **Preservation value is real**:
- `audit-standards.mdc` documents 6 months of audit-framework R&D (decision trees, phase-report schemas, completion-coupling logic, severity criteria) worth keeping for the unparking refactor.
- `development_guide.md` is the **reference template** future contributors will read when authoring their own `<workspace.custom_standards.development>` guide.

Deletion would lose institutional knowledge that has zero offsetting maintenance cost (parked content is unmaintained but referenceable).

### C — Park both (this ADR)

**Accepted.** Symmetric with ADR-010 tools parking; preserves content; cleans distribution; explicit unparking criteria for each.

### D — Move both to the em-ecosystem product repo

Rejected for `audit-standards.mdc`: would re-couple the framework's audit spec to a specific product repo, antithetical to SCRUM-572 cross-repo decoupling.

Considered for `development_guide.md`: the content IS em-ecosystem-specific (PostgreSQL + Prisma + NestJS describe NexaCore's stack). But moving it to em-ecosystem hides the reference template from contributors building non-NexaCore products. **Parking in-source-repo gives contributors easier reference than chasing across repos.**

## References

- **ADR-010** — parallel tools parking pattern (SCRUM-609 Wave 41). This ADR is its spec-layer companion.
- **SCRUM-606** (Wave 38) — established the `forge/_parked/** export-ignore` baseline in `.gitattributes`.
- **SCRUM-572** (Wave 8) — cross-repo decoupling that originally motivated the deprecation of product-specific dev guides.
- **SCRUM-600** (Wave 32) — added the self-deprecation note to `development_guide.md`.
- **§23** — Native freedom vs lifecycle; this wave is correctly framework-obligatory (modifies workflow-standards.mdc + adds new test + adds new ADR).
- **`forge/_parked/specs/`** — the new parking destination subdirectory created by this wave.
- **`forge/tools/_tests/test_parked_specs.py`** — the bi-directional drift guard that defends this parking.
