---
id: ADR-010
title: Parked tools and playbooks (2026-05-30 cross-repo decoupling fallout)
status: accepted
date: 2026-06-01
supersedes: null
superseded_by: null
---

# ADR-010: Parked Tools and Playbooks (2026-05-30)

## Status

**Accepted** (2026-06-01, SCRUM-609 Wave 41, Sprint 22 Housekeeping Ticket C).

## Context

On 2026-05-30 the framework decoupled from its original dogfood product (cross-repo separation SCRUM-572, Wave 8): the governed product's governance data — module trails, product specs, product architecture map — was moved out of this repo into `<your-product>/.lifecycle/`. The framework repo retained only the engine plus its own dogfood (`.lifecycle/artifacts/{framework,orchestrator,ci,backlog}/`).

Several runners and playbooks under `forge/tools/` and `forge/.playbooks/` had been hard-coded against the dogfood product's paths (`nexacore-api/src/auth/`, etc.) when the audit subsystem matured (Waves 17–24). After SCRUM-572 they were inoperative against the new mono-engine layout — their paths no longer existed in this repo, and the audit framework had not been refactored to consume `forge.config.yml` workspace metadata.

Affected surface:

- **Tools** (5 files): `audit/audit-phase-14.py`, `audit/audit-phase-15.py`, `audit/audit-delta.py`, `audit/list-open-findings.py`, the legacy meta-audit lifecycle runner.
- **Playbooks** (3 files): `audit.md`, `audit-check.md`, `check-api-contract.md`.
- **Schemas** (6 files): `charter.schema.yml`, `boundary.schema.yml`, `audit-finding.schema.yml`, `audit-phase-report.schema.yml`, `audit-completion-report.schema.yml`, `stable-baseline.schema.yml`.
- **CI** (1 file): `audit-on-pr-workflow-template.yml`.
- **Tests** (1 file): `_tests/test_audit_completion_framework.py`.

Total: **15 files** under `forge/_parked/` (verified `find forge/_parked -type f | wc -l` returns 15 on 2026-06-01).

The operator faced three options at the time:

1. **Delete** the audit subsystem outright (losing ~6 months of audit-framework R&D and 4 prior Waves of work);
2. **Fix-against-product-paths** (re-couple the engine to the product repo's paths, undoing SCRUM-572's separation);
3. **Quarantine** under `forge/_parked/{tools,playbooks,schemas}/` pending a re-activation decision.

Option 3 was chosen.

## Decision

The 15 affected files were moved to `forge/_parked/` on 2026-05-30. The directory is:

- **Not maintained** — no tests run against it, no anti-rot enforcement, no schema validation.
- **Not shipped** — `.gitattributes` excludes `forge/_parked/**` from the distribution archive (introduced in Wave 38 / SCRUM-606 Sprint 21 Clean Packaging Pipeline).
- **Not imported** — no live module in `forge/`, `framework/`, `orchestrator/`, or `scripts/` imports from `forge/_parked/*`. Verified via `grep -rE "from \._parked|import \._parked|forge._parked"` returning 0 production matches.

The corresponding skills (`/audit`, `/audit-check`, `/check-api-contract`) are similarly absent from the user-facing dashboard (they are not in `forge/.playbooks/`; their parked copies live under `forge/_parked/playbooks/`).

## Consequences

- **Preservation**: the audit framework code, schemas, playbooks, and tests survive a `forge/_parked/` snapshot. A future operator can read them in-place to understand the design rationale, test fixtures, and contract shape.
- **Drift inevitability**: with no maintenance, the parked code will drift from current framework conventions (workspace injection per Wave 31, MCP server per Wave 34, etc.). Reactivation will require a non-trivial refactor — not a simple "unpark + run".
- **Distribution cleanliness**: end-user downloads (em-framework-v0.19.1.tar.gz and onward) do NOT include `forge/_parked/**`. The dev-time surface in the source repo remains visible to contributors but invisible to consumers.
- **Documentation cost**: COMMANDS_REFERENCE.md no longer needs to explain the quarantine in prose — Section "Tools" links to this ADR for the rationale.

## Unparking Criteria

The audit subsystem becomes useful again **only when both** of the following hold:

1. The framework re-engages with a governed product trail at a known path. Typically this means an operator installs the framework into a product repo via `em-cli init --mode map`, which generates `forge.config.yml` with `backend_root`, `frontend_root`, `specs_root` pointing at the product's paths. The framework is then "aware" of the product's structure via the Wave-31 workspace injection mechanism.
2. **AND** someone refactors the parked audit-runners to consume the workspace metadata from `forge.config.yml` (via the typed loader in `forge/tools/_workspace.py` or the equivalent injection layer) instead of hard-coding `nexacore-api/src/`. The required refactor surface:
   - Replace literal product paths with `<workspace.backend_root>` / `<workspace.frontend_root>` symbolic refs.
   - Replace the meta-audit/lifecycle product runner's hard-coded baseline with a `forge.config.yml`-driven baseline.
   - Re-validate against the workspace schema (`forge/schemas/forge-workspace.schema.yml`).
   - Restore CI coverage (add `forge/_parked/_tests/` back to pytest's testpaths and ensure green).

Until both conditions are met, **no work on `forge/_parked/**` is scheduled**.

## Alternatives Considered

### A — Delete the audit subsystem

Rejected. The audit framework represented Waves 14, 17, 18, 19, 20, 23 of effort (group of related tickets); deletion would lose institutional knowledge (decision-tree taxonomies, phase-report schemas, completion-coupling logic) that future product-audit work would need to re-derive.

### B — Fix-against-product-paths

Rejected. The framework had just decoupled from the product repo per SCRUM-572 (cross-repo separation). Re-coupling for audit-machinery's convenience would undo the architectural separation that made the framework distributable. SCRUM-572's value was specifically that the engine be product-agnostic — re-coupling for one subsystem would re-introduce the brittleness the separation eliminated.

### C — Quarantine in-place (this ADR's decision)

Accepted. Quarantine preserves the work, excludes it from distribution (`forge/_parked/**` export-ignored), keeps it off the CI hot path, and documents an explicit unparking checklist for future operators.

### D — Move to a sibling repo (e.g. `em-framework-audit/`)

Rejected on cost-benefit. The 15-file footprint is small enough to live in `forge/_parked/` without burdening the framework repo's clarity. Splitting into a sibling repo would introduce cross-repo coordination cost for zero incremental clarity gain.

## References

- **SCRUM-572** (Wave 8 — Separación Motor-Datos): cross-repo separation that made the audit subsystem inoperative.
- **SCRUM-606** (Wave 38 — Clean Packaging Pipeline): `.gitattributes` excludes `forge/_parked/**` from distribution.
- **SCRUM-609** (Wave 41 — this ADR): codifies the quarantine rationale and unparking criteria.
- **`forge/_parked/`**: the 15-file snapshot (`find forge/_parked -type f` for the inventory).
- **ADR-006**: `forge/tools/` is not a package (the lib + CLI-shell pattern) — relevant context for any future unparking refactor.
- **Wave 31 runtime injection**: the workspace mechanism the audit-runners would need to consume on unparking.
