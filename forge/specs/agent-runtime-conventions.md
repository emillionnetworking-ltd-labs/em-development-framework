---
version: 1.0.2
title: Agent Runtime Conventions
status: stable
category: spec
last_changed: 2026-06-02
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Agent Runtime Conventions

Single source of truth for the **Claude Code runtime conventions** that agent personas in `forge/.agents/` consume. Agent personas reference these templates **symbolically** instead of hardcoding raw paths — if the runtime convention changes, this file updates and the personas inherit.

This spec exists to close the silent-fossil risk identified by strategy session `agents-architectural-alignment-v1` (framework release layer, <TICKET-ID>): hardcoded runtime paths in agent personas are not audited by `anti-rot` (scans repo paths) nor by `meta-audit framework-modules` (scans Python module boundaries). The convention itself sits in a third-party runtime (Anthropic Claude Code), not under our control.

## Templates

### `PLAN_OUTPUT_DIR_TEMPLATE`

```
.claude/doc/<feature>/
```

Directory where a planning persona writes its implementation plan. The `<feature>` token is the feature/ticket slug supplied by the parent agent at session start. Each persona writes one file under this directory: `backend.md`, `frontend.md`, etc.

Used by: `backend-developer.md`, `frontend-developer.md` (Output format + Rules sections).

### `CONTEXT_SESSION_TEMPLATE`

```
.claude/sessions/context_session_<feature>.md
```

File where the parent agent persists the ticket context that the planning persona reads before authoring its plan. Same `<feature>` token resolution as above.

Used by: `backend-developer.md`, `frontend-developer.md` (Rules section).

## How personas reference these templates

A persona's body MUST refer to a template by name (`${PLAN_OUTPUT_DIR_TEMPLATE}`, `${CONTEXT_SESSION_TEMPLATE}`) rather than by raw path (`.claude/doc/...`, `.claude/sessions/...`). The mechanical gate `test_agent_runtime_paths_via_symbolic_reference` (added in framework release layer) flags any hardcoded `.claude/doc/` or `.claude/sessions/` literal in `forge/.agents/*.md` and fails CI.

The token substitution itself is performed by the parent agent at runtime when invoking the subagent — these symbolic refs are documentation, not interpolation directives. The persona reads the symbolic ref, the parent supplies the concrete path when it calls the subagent.

## When this file changes

If Anthropic changes the Claude Code runtime convention (e.g. `.claude/doc/` becomes `.anthropic/plans/`):

1. Update the template definitions above.
2. Bump `last_changed` ISO date.
3. Run `python3 -m pytest forge/evals/static/test_skill_structure.py -k TestAgentStructure` to confirm no regression (the test scans for hardcoded paths, not for the symbolic refs themselves).
4. No persona file needs editing — they reference symbolically.

## Out of scope

- The runtime convention itself (governed by Anthropic Claude Code, not by this repo).
- Subagent invocation surface (handled by `Agent` tool in the parent's main loop).
- Plan content structure (governed by `forge/.playbooks/plan.md`).
