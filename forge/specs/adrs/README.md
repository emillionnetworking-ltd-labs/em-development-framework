# Architecture Decision Records (ADRs)

## What lives here

This directory is the durable, indexable home for the framework's architectural decisions. Each ADR captures **one** decision — what was chosen, why, what alternatives were considered, and what consequences followed. Decisions land here only after they are operational; ADRs document settled choices, not proposals under debate.

The format follows the canonical Michael Nygard pattern ("Documenting Architecture Decisions", 2011), adapted with explicit frontmatter so ADRs can be machine-indexed alongside the rest of `ai-specs/specs/`.

## Naming convention

- **File pattern**: `adr-NNN-kebab-case-title.md` where `NNN` is a zero-padded 3-digit sequence starting at `001`.
- **One decision per file**. Conflating two decisions in one ADR makes the supersession lifecycle ambiguous.
- **Numbers are append-only**. Once an ADR has been assigned `NNN`, that number is never reused — not even if the ADR is later deprecated or superseded. The number is a permanent identity.

## Frontmatter schema

Every ADR begins with a YAML frontmatter block:

```yaml
---
id: ADR-001
title: FW-004 Lifecycle State Machine
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---
```

Field semantics:

| Field | Type | Meaning |
|---|---|---|
| `id` | string `ADR-NNN` | Stable identity; matches the filename's `NNN`. |
| `title` | string | Short, declarative summary of the decision. |
| `status` | enum | One of `proposed`, `accepted`, `superseded`, `deprecated`. See "Status lifecycle" below. |
| `date` | YYYY-MM-DD | When the decision reached `accepted` (or `proposed` if not yet accepted). Immutable after acceptance. |
| `supersedes` | `ADR-NNN` or `null` | If this ADR replaces a prior one, list its id. |
| `superseded_by` | `ADR-NNN` or `null` | Set when a later ADR replaces this one. |

## Body sections (required H2)

Each ADR has exactly these five H2 headings, in this order:

1. **Context** — the situation, pressures, and constraints that forced the decision.
2. **Decision** — the choice made, stated declaratively. No hedging.
3. **Consequences** — what changed (positive, negative, operational) as a result.
4. **Alternatives Considered** — options that were on the table and why they were rejected.
5. **References** — links to records, commits, skills, files, or external sources that demonstrate the decision in operation.

Additional H3 sub-headings inside these sections are allowed where useful.

## Status lifecycle

```
proposed → accepted → superseded
                  ↘ deprecated
```

- **`proposed`** — written but not yet ratified by the operator. Rare in this framework; most ADRs are written about decisions that are already in production, so they land directly at `accepted`.
- **`accepted`** — ratified and in force. Body is **immutable** from this point on.
- **`superseded`** — a later ADR has replaced this decision. Set `superseded_by: ADR-NNN`. Body remains immutable.
- **`deprecated`** — the decision is no longer relevant (the system component it described was removed) without being replaced by a successor. Body remains immutable.

Status transitions update the frontmatter only. To revise the **content** of a decision, write a new ADR that supersedes the old one — never edit the body of an accepted ADR.

## Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [ADR-001](adr-001-fw-004-state-machine.md) | FW-004 Lifecycle State Machine | accepted | 2026-05-16 |
| [ADR-002](adr-002-dual-original-enhanced-enrichment.md) | Dual `[original]`/`[enhanced]` Enrichment | accepted | 2026-05-16 |
| [ADR-003](adr-003-not-section-15-auth-change-control.md) | NOT-§15 AUTH Change-Control | accepted | 2026-05-16 |
| [ADR-004](adr-004-schema-driven-validation.md) | Schema-Driven Artifact Validation | accepted | 2026-05-16 |
| [ADR-005](adr-005-plan-verify-record-trilogy.md) | Plan + Verify + Record Trilogy | accepted | 2026-05-16 |
| [ADR-006](adr-006-ai-specs-tools-not-a-package.md) | `ai-specs/tools/` Is Not a Python Package | accepted | 2026-05-16 |
| [ADR-007](adr-007-phase-4-entry-decisions.md) | Phase 4 entry decisions (2026-05-16) | accepted | 2026-05-16 |
| [ADR-008](adr-008-scrum-470-narrative-correction.md) | SCRUM-470 narrative correction (F4 archeology resolution) | accepted | 2026-05-17 |

## Adding a new ADR

1. **Pick the next number**: look at the current highest `adr-NNN-*.md`, increment by one, zero-pad to 3 digits.
2. **Copy an existing ADR as a template**: pick one structurally similar (e.g. ADR-001 for an enforcement decision, ADR-002 for a workflow decision).
3. **Commit via the regular lifecycle**: ADRs are framework artifacts; they land via `/enrich-us` → `/plan` → `/develop` → `/verify` → `/commit` → `/update-docs` like any other change. No separate skill required.

When the new ADR supersedes an existing one, update the prior ADR's frontmatter (`status: superseded` + `superseded_by: ADR-NNN`) in the **same commit**. The prior body remains unchanged.
