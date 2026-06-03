---
id: ADR-012
title: Spec modular split — surgical extraction of esporadic sections
status: accepted
date: 2026-06-02
supersedes: null
superseded_by: null
---

# ADR-012: Spec Modular Split

## Status

**Accepted** (2026-06-02, SCRUM-615 Wave 47, Sprint 23 Backlog Discipline).

## Context

`forge/specs/workflow-standards.mdc` reached 1928 LoC with `alwaysApply: true`, becoming the largest single prompt-injected document in the framework. The 2026-06-02 architectural evaluation (per SCRUM-614 Wave 46 review) identified three concerns:

1. **Token Tax for Cursor users**: each conversation auto-injects ~2000 lines of rules, diluting context budget.
2. **Maintenance friction**: 23 sections at one level of organization, all read-on-every-turn even if topic-specific.
3. **Asymmetric rigor**: skills (`forge/.playbooks/*.md`) had structural tests + version-bump-on-edit; specs did not (closed for frontmatter dimension by Wave 46; this ADR completes via physical modularization).

Original 5-spec aggressive split proposal was REJECTED with modifications because:
- Splitting AUTH §15 = security regression (HARD LIMIT visibility loss)
- "Token Tax" framing over-promised: only Cursor auto-injects `.mdc`; Claude Code reads on demand
- §23 native-freedom is the most-applied decision rule per turn — must stay visible

Modified plan: **surgical split** preserves safety-critical (§15) + high-frequency (§23) + lifecycle-core (§1-10) + versioning (§16-17) + audit-findings (§22) in Core. Only esporadic sections move to modular specs.

## Decision

Extract 5 modular specs from `workflow-standards.mdc`:

| Modular spec | Source sections | Activation trigger |
|---|---|---|
| `satellite-conventions.mdc` | §11 | Operator works on SAT* project; `sat-` module prefix |
| `dependency-health.mdc` | §12 | Edit to `requirements*.txt`, `package.json`, Pipfile |
| `framework-upgrade-playbook.mdc` | §13 | Major version bump (X increment) or VERSION file change |
| `audit-sprint-conventions.mdc` | §14 | `/audit <module>` invoked OR ticket "Audit" prefix |
| `cross-cutting-policies.mdc` | §18-21 | Edit to baseline files, multi-agent state-file ops, Jira workflow, pending-improvements registry ops |

Each modular spec carries:
- Full enterprise frontmatter (matching Wave 46 standard)
- `alwaysApply: false` (read on demand, NOT auto-injected by Cursor)
- Internal section numbering restart at §1 (each modular file is self-contained)
- Header note pointing back to `workflow-standards.mdc §0 Specs Index` as the activation map

`workflow-standards.mdc` is reduced from 1928 → ~991 LoC and bumped to version **3.0.0** (major: structural change). The §0 Specs Index updated to show all 5 modular specs as DONE.

Sections §11-14 + §18-21 in `workflow-standards.mdc` are replaced with one-line stubs pointing at the corresponding modular spec.

## Consequences

- **Token Tax reduction for Cursor**: ~937 LoC removed from auto-injected context. From 1928 LoC alwaysApply → 991 LoC. ~49% reduction per-turn for Cursor users.
- **Claude Code unchanged at runtime**: doesn't auto-inject `.mdc`. The Index pattern (per §0) governs read-on-demand. Modular specs are equally accessible.
- **Maintenance clarity**: each modular spec covers one cohesive topic. Edits no longer touch a monolith. `test_specs_structure.py` extended from 5→10 active specs gives parametric enforcement.
- **Drift guard added**: `test_specs_modular_split.py` ensures (a) all §0 Index references resolve to existing files, (b) workflow-standards.mdc stubs are not orphan content, (c) ACTIVE_SPECS in test_specs_structure.py matches filesystem.
- **Cross-reference cost**: skills + ADRs + integration-state citations of `workflow-standards.mdc §X` for split sections needed updates (Step 6 of develop). Future citations should use modular spec filename + §1.x sub-numbering.
- **ADR contiguity preserved**: ADRs now 001-012 contiguous.

## Unparking Criteria

If the split creates more friction than clarity (e.g. agents fail to lazy-load modular specs, or operators complain about navigation), a reverse-split ADR-013 supersedes this one and merges the 5 modular specs back into `workflow-standards.mdc`. The §0 Index would be retained as an internal table-of-contents in the merged file. Test extensions retired.

No automatic activation criteria — purely operator decision.

## Alternatives Considered

### A — Leave monolith (status quo)

Rejected. 1928 LoC alwaysApply is the largest prompt-injected document in the framework. Token Tax for Cursor + navigation friction for everyone.

### B — Aggressive 5-spec split including AUTH §15 + §23

Rejected per architect evaluation. AUTH §15 lazy-load = security regression (HARD LIMIT visibility loss). §23 native-freedom is the most-applied decision rule per turn — lazy-loading creates judgment ambiguity.

### C — Surgical split preserving safety-critical + high-frequency (this ADR)

**Accepted.** Token Tax reduction where it actually applies (Cursor + esporadic sections) without sacrificing safety-critical visibility.

### D — Move `workflow-standards.mdc` to em-ecosystem product repo

Rejected. The spec is engine-level governance, not product-specific. Cross-repo coupling would re-introduce the brittleness SCRUM-572 eliminated.

## References

- **SCRUM-614** (Wave 46) — authored §0 Specs Index as activation-trigger map; precursor to physical split.
- **SCRUM-615** (this wave) — executed the physical split.
- **2026-06-02 architect evaluation** — identified the modified plan with safety-critical preservation.
- **ADR-010** (parking sweep) + **ADR-011** (parked specs) — parallel patterns of structural surgery on `forge/specs/`.
- **`workflow-standards.mdc §0 Specs Index`** — the activation-trigger map that this ADR mechanically realizes.
- **`forge/tools/_tests/test_specs_modular_split.py`** — drift guard test enforcing this ADR's invariants.
- **5 modular specs**: `forge/specs/{satellite-conventions, dependency-health, framework-upgrade-playbook, audit-sprint-conventions, cross-cutting-policies}.mdc`.
