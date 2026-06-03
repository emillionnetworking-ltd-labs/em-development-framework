---
version: 1.2.2
category: utility
description: "Show the framework's command map and docs in-chat (reads COMMANDS_REFERENCE.md / README live)."
last_changed: 2026-06-01
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Interface renderer. Reads docs live from disk and renders an interactive help dashboard in chat. Invent nothing — every entry must come from a file read this run.

# Arguments
`$ARGUMENTS` (optional):

- **empty** → render the **Overview dashboard** (the command map + quick links).
- **`architecture`** → render the **Engine X-ray** (the architecture deep-dive).
- **`<skill-or-tool-name>`** (e.g. `verify`, `meta-audit`) → render a **focused card** for just that command.

# Process

## Step 1: Read the canonical sources live (MANDATORY — never paraphrase from memory)

Resolve the framework root (the directory that contains `COMMANDS_REFERENCE.md` — typically `~/projects/em-development-framework`). Then:

- **Overview** (no arg): read `COMMANDS_REFERENCE.md` (full) and the `## Documentation` section of `README.md`.
- **`architecture`**: read `ARCHITECTURE.md` (full).
- **`<name>`**: read `COMMANDS_REFERENCE.md` and extract only the row(s)/section for that command; if it is a lifecycle/utility skill, also read the first ~30 lines of `forge/.playbooks/<name>.md` for its purpose.

If a source file is missing or unreadable, render the rest of the dashboard anyway and show a small inline notice for the affected module — never fail silently, never block the whole view.

## Step 2: Render the dashboard

Compose the output as a sequence of visual **modules** separated by horizontal rules (`---`). Use styled Markdown tables, code spans/blocks for command syntax, and emoji as navigation icons. Aim for the legibility of an app screen, not a wall of prose.

### Overview layout (no argument)

The overview is decisional (answers "¿qué hago AHORA?"), not informative ("¿qué existe?"). Render a 3-card hierarchy filtered by the catalog's `user_invocable: true` flag (<TICKET-ID> framework release layer). The catalog YAML is the SSoT for visibility — entries with `user_invocable: false` (the 11 libs and the 6 lifecycle skills) are hidden from the dashboard but remain in the YAML for machine consumers.

1. **Header block** — a banner-style heading with the framework identity, plus a compact status line:
   - `🧩 em-development-framework` + a one-line tagline.
   - A **health strip**: a hint that live health is one command away (`/meta-audit lifecycle`). Do **not** run the suite or the meta-audit yourself — point to the command; this is a help view, not a CI run.
   - **Quick links**: `ARCHITECTURE.md` · `COMMANDS_REFERENCE.md` · `README.md`.

2. **🚀 START — ¿qué quieres hacer?** — the entry points an operator reaches for first. Render as a styled table (Action · Command):

   | Action | Command |
   |---|---|
   | Drive a ticket through the 6-step lifecycle | `/lifecycle <TICKET-ID>` |
   | Design a strategy (bounded debate + executive report) | `/strategy "<target>"` |
   | Health check / doctor | `python3 forge/tools/em-cli.py doctor` |
   | Install on a new repo | `em-cli init --mode <greenfield\|map>` |

3. **🛠️ UTILITY SKILLS (operator-invocable, anytime)** — load the catalog (`forge/commands.catalog.yml` via `_catalog.load_catalog()` or by re-reading the YAML) and render every entry with `kind: skill` AND `user_invocable: true` AND `category: utility`. De-dup any name that already appears in card 2 (START). Format as Skill · Purpose. Expected post-Wave-40: `/check-pending`, `/sprint-cleanup`, `/classify-deviation`, `/validate-artifact`, `/help-framework`, `/meta-audit`.

4. **⚙️ DIRECT TOOLS (CLIs — para CI o uso avanzado)** — load the catalog and render every entry with `kind: tool` AND `user_invocable: true`. Group by `category` (support · audit · framework). Include the invocation reminder (`python3 forge/tools/<name>.py …`). End with the rule: **libs `_<tool>.py` are import-only, never run directly** (they are `user_invocable: false` in the catalog by design).

5. **Footer — console buttons (next action)** — a row of bracketed, console-style hints pointing to the natural next moves, e.g.:
   ```text
   [ /help-framework architecture ]  ➔  engine X-ray (state flow, lib+shell, anti-drift)
   [ /meta-audit lifecycle ]         ➔  run the framework health check
   [ /help-framework <command> ]     ➔  zoom into one command
   ```

**Important**: this dashboard MUST NOT render entries with `user_invocable: false` (the 11 libs + the 6 lifecycle skills). Operators drive the lifecycle through `/lifecycle <TICKET>` (the engine umbrella), not by typing the individual step-skills — that contract is enforced by both CLAUDE.md operating contract and the test `test_lifecycle_skills_are_engine_driven` in `test_catalog.py`.

### `architecture` layout

Render `ARCHITECTURE.md` as a structured read: a header, then each top-level section as its own module with `---` separators; keep its code blocks intact; finish with a footer button back to the overview (`[ /help-framework ] ➔ command map`). Summarize long prose into tight bullets where it improves scanability, but preserve all section headings and code blocks faithfully.

### `<name>` layout

A single focused **card**: the command name as the header, its category badge (Lifecycle / Utility / Tool), its purpose, how to invoke it, and — for lifecycle skills — its position in the pipeline and its gate. Footer button back to `[ /help-framework ]`.

## Step 3: Quality bar

- **Premium in form, single-source in substance**: beautiful layout, but zero invented content and zero copied-then-stale text — you read the files this run.
- **No `file:line` citations** (anti-rot, P-015) — cite file and symbol names only.
- English output (P-015), even though the operator chats in Spanish.

# Notes

- This skill performs **read + render only**. It never edits files, never runs the test suite or the meta-audit, and never advances any lifecycle state.
- It is intentionally a pure prompt-skill (no Python support tool): the logic is "read the canonical docs and present them," which needs no deterministic CLI.
- Name is `/help-framework` (not `/help`) to avoid colliding with Claude Code's built-in `/help`.

# References

- `COMMANDS_REFERENCE.md` — the command map (primary source).
- `README.md` (`## Documentation`) — the documentation hub.
- `ARCHITECTURE.md` — the engine X-ray (rendered on the `architecture` argument).
