# forge Schemas

> **Status**: framework release layer / FW-001 introduction. framework release layer / FW-002 (`/validate-artifact`, <TICKET-ID>) added the enforcer. Schemas are the contract — the validator is the gate.

JSON Schema (Draft 2020-12) definitions in YAML for the framework's machine-readable artifacts.

## Quick start (using the validator)

```bash
# Validate any artifact (auto-detects schema from frontmatter or path):
python3 forge/tools/validate-artifact.py path/to/artifact.md

# Override schema explicitly:
python3 forge/tools/validate-artifact.py path/to/file.yml \
    --schema forge/schemas/bypass-log.schema.yml

# JSON output for tooling:
python3 forge/tools/validate-artifact.py path/to/file.md --json
```

Exit codes: `0` = PASS, `1` = FAIL (schema errors), `2` = ERROR (parse/locate problem).

The slash command `/validate-artifact <file>` wraps the same script and is auto-discovered via the `~/.claude/commands` symlink.

## Why this exists

Per the architectural audit 2026-05-13, the framework enforces very little because its rules are markdown prompts the agent interprets freely. Schemas convert "MANDATORY" sections from advisory text into validatable structure. Each artifact declares its schema in the frontmatter; `/validate-artifact <file>` parses + validates and refuses to pass if required structure is missing.

## Schema stable identifier vs filesystem path (<TICKET-ID> / <TICKET-ID>)

Artifact frontmatter declares the schema using a **stable symbolic identifier**:

```yaml
schema: ai-specs/schemas/plan.schema.yml
```

The actual filesystem path is `forge/schemas/plan.schema.yml` (the engine directory was renamed in <TICKET-ID> from `ai-specs/` to `forge/`). The validator (`forge/tools/_validate_artifact.py`) translates `ai-specs/schemas/X` → `forge/schemas/X` transparently. This is **intentional design**, not drift:

- The 4 lifecycle schemas (plan, verify, record, freeze-status) declare `const: ai-specs/schemas/X.schema.yml` — this is the stable identifier contract.
- The `$id` URIs in 10 schemas use `https://ai-specs.em/schemas/X` — JSON Schema convention says `$id` is identifier-stable, independent of filesystem location.
- 234+ existing artifacts in `.lifecycle/artifacts/` use the stable identifier in their frontmatter and continue to validate correctly via the aliasing.

The drift guard test `forge/tools/_tests/test_schemas_path_aliasing.py` (<TICKET-ID> framework release layer) defends this design pattern from being accidentally undone.

## Schemas

| File | Validates | Used by |
|---|---|---|
| [plan.schema.yml](plan.schema.yml) | `.lifecycle/artifacts/[module]/plans/<sprint-or-wave>/SCRUM-XX_[scope].md` | `/plan`, `/develop`, `/verify` |
| [verify.schema.yml](verify.schema.yml) | `.lifecycle/artifacts/[module]/plans/<sprint-or-wave>/SCRUM-XX_verify.md` | `/verify`, `/commit` |
| [record.schema.yml](record.schema.yml) | `.lifecycle/artifacts/[module]/records/<sprint-or-wave>/SCRUM-XX_[scope].md` | `/update-docs` |
| [state.schema.yml](state.schema.yml) | `.lifecycle/artifacts/[module]/state/SCRUM-XX.yml` | All 6 lifecycle commands (FW-004) |

## Artifact format

Each `.md` artifact has YAML frontmatter + markdown body:

```markdown
---
schema: ai-specs/schemas/verify.schema.yml   # stable identifier (see section above)
ticket: <TICKET-ID>
sprint: internal cycle
scope: backend
module: auth
date: 2026-05-12
verdict: PASS
is_audit_fix: false
---

# Verification Report: <TICKET-ID> ...

## Plan Compliance
...

## Deviations
...
```

`state.schema.yml` is the exception — it validates `.yml` files directly (no markdown body).

## How validation works (two-stage)

JSON Schema validates **data**, not markdown documents. The pipeline:

```
parse markdown
  ├── extract YAML frontmatter ──► JSON object
  └── extract headings (level + text) ──► array of {level, text}
                                          │
                                          ▼
                                    parsed payload
                                          │
                                          ▼
                                    JSON Schema validator
                                          │
                                          ▼
                                    PASS / FAIL with errors
```

**Parser contract** (input to validator):
```json
{
  "frontmatter": { ... },
  "headings": [
    { "level": 1, "text": "Backend Implementation Plan: <TICKET-ID> ..." },
    { "level": 2, "text": "2. Codebase State Snapshot" },
    { "level": 2, "text": "3. Regression Impact Analysis" },
    ...
  ]
}
```

Section names match loosely: schema patterns accept `^[N\\.\\s]*<SectionName>$` so both `## 2. Codebase State Snapshot` and `## Codebase State Snapshot` validate.

## Design decisions

### Frontmatter validated strictly; section content not validated

Schemas validate that required **sections exist** (by H2 heading match), not what's **inside** them. Content checks (e.g., "Codebase State Snapshot must list ≥1 file") are out of scope for FW-001. FW-002's validator can be extended for content checks later, or use Phase 12 (Spec-Code Drift) audit.

### Conditional sections expressed via `if/then`

Some sections are only required under conditions (e.g., `Audit Finding Resolution` only if `is_audit_fix: true`, `Module-Level Planning` only when planning a new module). These use JSON Schema's `if/then/else`.

### No cross-artifact validation

Schemas validate one file at a time. Cross-artifact checks (e.g., record's `Plan Reference` field points to an existing plan file) are FW-002's responsibility. Schemas only specify the local shape.

### Schemas are self-contained (no `$ref` to common.schema)

For MVP simplicity. If duplication grows (sprint pattern, ticket regex, etc.), refactor to `common.schema.yml` later.

## Conventions

- All schemas declare `$schema: https://json-schema.org/draft/2020-12/schema`
- All schemas declare `$id: https://ai-specs.em/schemas/<name>.schema.yml` (stable identifier per <TICKET-ID> — see the "Schema stable identifier vs filesystem path" section)
- Section patterns use anchored regex: `'^(\d+\.\s+)?<Section Name>$'`
- Enums use kebab-case for multi-word values
- YAML anchors (`&name`) + aliases (`*name`) used for repeated section-match blocks

## Out of scope for FW-001 (deferred to later tickets)

- `/validate-artifact` command implementation → FW-002
- Migrating existing artifacts to add frontmatter → separate ticket
- Cross-artifact validation (plan ↔ verify ↔ record ↔ state) → FW-002 or beyond
- Content-level validation (e.g., "Deviations table has ≥1 row if status=DONE-DEVIATED") → FW-002 extension
- Schema for `module-charter.md`, `module-boundary.md`, etc. → framework release layer / capa 2

## References

- Architectural audit 2026-05-13: `~/.claude/projects/-home-em-admin/memory/project_ai_specs_audit_2026_05_13.md`
- Master plan §6.1 piece 1 (Schemas) — this ticket
- Existing playbooks in `forge/.playbooks/{plan,verify,update-docs}.md` define the section lists encoded here
- **<TICKET-ID>** (the `ai-specs → forge` rename + stable-identifier preservation) — context for the schema identifier convention
- **<TICKET-ID> / framework release layer** — added this README's "Schema stable identifier vs filesystem path" section + the drift guard test
- JSON Schema Draft 2020-12 spec: https://json-schema.org/draft/2020-12/release-notes
