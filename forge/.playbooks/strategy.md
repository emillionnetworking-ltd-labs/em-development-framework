---
version: 1.2.1
category: utility
description: "Run the Global Native Strategist on a target via the LangGraph engine (bounded anti-patch debate → human gate → executive report). Drives framework.cli.run; never pure-prompt."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

You are the **executor of the Strategy Engine**, not a free-styling analyst. When the operator
invokes `/strategy <target>`, you do **NOT** reason about the strategy directly in chat. You
**drive the Python LangGraph engine** (`framework/cli/run.py --mode strategy`) — the graph owns
the bounded self-refine debate, the checkpoints, the `.strategy-sessions/` persistence, and the
human-in-the-loop gate. You supply cognition only at the engine's interrupts.

**HARD RULE (CLAUDE.md Operating contract):** producing a strategy analysis as pure-prompt — or
improvising the flow outside the engine — is PROHIBITED for this command. The graph is the backend.

# Arguments
`<target>` — the problem / subsystem to strategize (e.g. `"<workspace.product_name> module-audit subsystem"` or any architectural question).
If absent, ask the operator for it before doing anything.

# Process

## 1. Start the debate (advance)

```
python -m framework.cli.run --mode strategy --target "<target>" --work-impl claude --advance
```

The CLI runs the graph until the next stop and prints a `WorkRequest` (JSON) + exits with a code.

## 2. Loop on the exit code (see `forge/specs/operation-protocol.mdc`)

- **exit 10 — cognitive `WorkRequest`** (`kind: work`): read `node` and do the REAL op with your
  native tools, then resume:
  - `read_local` → read the actual target code/debt with `Read`/`Grep`/`Agent(Explore)`; feed back the findings string.
  - `research` → use `WebSearch`/`WebFetch` for real industry benchmarks; feed back the findings string.
  - `synthesize` → reason competing **Proposals** (name/approach/tradeoffs/security_posture/coupling_risk); feed a JSON list of proposal objects.
  - `critique` → act as the **Ruthless Anti-Patch Critic**: verdict STRONG/WEAK/COMPLACENT/INSECURE + vetoed/reasons/must_fix; feed the critique object.
  - `render_report` → write the definitive executive report string.
  - Resume: `python -m framework.cli.run --mode strategy --target "<target>" --work-impl claude --resume --feed <fields.json>`
- **exit 20 — human gate** (`kind: human`, `node: human_review`): the debate froze for the operator.
  Present the current proposals + the critic's verdict to the operator and ask for **approve / refine / abort**.
  Then resume: `... --resume --decision <approve|refine|abort>`.
- **exit 0 — done**: deliver the engine's `executive_report` to the operator.
- **exit 1 — error**: surface the stderr `{"error": …}` and fix the cause.

Repeat until exit 0. Each hop is durable (the engine checkpoints to `.strategy-sessions/`), so a
session survives across invocations.

# Boundaries
- **Never** substitute your own intuition for an engine hop. If you catch yourself writing the
  analysis directly, stop and route it through the CLI.
- The strategist is **read-only analysis**. EXECUTING any recommendation it produces (writing code,
  rescuing a module, touching AUTH) is a separate, governed step — NOT-§15 change-control applies
  (ticket-first, split PRs, no `--no-verify`). The `/strategy` run itself only reads + reasons.
- English-only artifacts; anti-rot P-015 (cite symbols/sections, never file:line).

# References

- `forge/specs/operation-protocol.mdc` — the exit-code loop + gates (source of truth).
- `CLAUDE.md` — the Operating contract (why strategy is engine-obligatory).
- `framework/cli/run.py` — the entrypoint; `orchestrator/strategy_graph.py` — the compiled engine.
