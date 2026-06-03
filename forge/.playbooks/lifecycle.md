---
version: 1.1.2
category: utility
description: "Drive a ticket through the 6-step lifecycle via the LangGraph engine (framework.cli.run --mode lifecycle). The operator front door; reads each phase's playbook at the engine's interrupts. Never freestyle."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

You are the **executor of the Lifecycle Orchestrator**, not a free-styling developer. When the
operator invokes `/lifecycle <ticket>`, you do **NOT** run the 6 phases by improvisation. You
**drive the Python LangGraph engine** (`framework/cli/run.py --mode lifecycle`) — the graph owns
the step gating, the canonical `state.yml` persistence, the checkpoints, and the routing. You
supply cognition at the engine's interrupts, reading each phase's **playbook** for the real
instructions.

**HARD RULE (CLAUDE.md Operating contract):** running a ticket lifecycle as pure-prompt — or
hand-running the step-skills outside the engine — is PROHIBITED. The graph is the backend. The 6
step-skills (`enrich-us`, `plan`, `develop`, `verify`, `commit`, `update-docs`) are now
`user-invocable: false` — they are your **playbooks**, read at the interrupts, not menu commands.

# Arguments
`<ticket>` (e.g. `<TICKET-ID>`) and its module (e.g. `framework`). If absent, ask the operator, or
use `--status` to discover the open ticket/phase.

# Process

## 1. Orient

```
python -m framework.cli.run --status --mode lifecycle --ticket <TICKET> --module <MODULE>
```

## 2. Advance + loop (see `forge/specs/operation-protocol.mdc`)

```
python -m framework.cli.run --mode lifecycle --ticket <TICKET> --module <MODULE> --advance
```

Read the exit code:

- **exit 10 — cognitive `WorkRequest`** (`node` = the phase): **READ the phase playbook
  `forge/.playbooks/<node>.md`** (e.g. `plan.md`) and execute its instructions for THIS phase —
  that is the source of truth for *how* to do the phase. Produce the artifact (plan / code /
  verify report / record), then feed back the `needs` fields:
  `... --resume --feed <fields.json>`.
- **exit 20 — gate** (`gate` ∈ HARD_LIMITS: push / jira-post / auth-15 / scope-gap /
  strategic-choice): do the prep, then STOP for the operator's explicit authorization before the
  gated action (a push needs the exact push phrase). Resume after authorization.
- **exit 0 — done**: the ticket reached `documented`.
- **exit 1 — error**: surface the stderr `{"error": …}` and fix the cause.

Repeat until exit 0. The engine checkpoints the canonical `state.yml` each step, so the lifecycle
is durable + resumable across invocations.

# Boundaries
- **Never** run a phase by improvisation. The engine sequences + gates; the playbook (the
  `.commands/<phase>.md` file) tells you *how*; you do the work + feed the fields.
- Honor the gates: push / jira-post / auth-15 / scope-gap / strategic-choice always wait for the
  operator (NOT-§15 applies to AUTH).
- English-only artifacts; anti-rot P-015.

# References

- `forge/specs/operation-protocol.mdc` — the exit-code loop + the playbook-read rule.
- `CLAUDE.md` — the Operating contract (why the lifecycle is engine-obligatory).
- `framework/cli/run.py` — the entrypoint; `orchestrator/lifecycle_graph.py` — the compiled engine.
- The phase playbooks (`user-invocable: false`): `enrich-us`, `plan`, `develop`, `verify`, `commit`, `update-docs`.
