ai-specs/specs/base-standards.mdc

## Operating contract (chat-native, engine-obligatory)

This repo is operated from the VS Code conversational chat. There are two modes, and the
boundary is strict:

### Native freedom — common / ad-hoc work
Q&A, code search, one-off edits, explanations, debugging, exploratory analysis — including
**read-only questions about core modules** (e.g. "how does auth work?", "where is X defined?").
Use native tools directly with normal judgment. No framework ceremony required.

### Framework-obligatory — three work-classes
For **(1) ticket lifecycle**, **(2) strategy design**, and **(3) product audits**, the
Python LangGraph engine is the BACKEND THAT RUNS THE WORK — not the agent's intuition. The
engine owns the checkpoints, the on-disk persistence (state.yml / .strategy-sessions), and
the schema validations. **Pure-prompt / freestyle execution of these three classes is
PROHIBITED.** The agent is the engine's executor: it supplies cognition at the engine's
interrupts and pauses at the human gates — it does not improvise the flow.

### Proactive Interception — Intent Filter & Pre-flight Check
If a user prompt does NOT start with an official slash command (`/`) but explicitly asks to
**execute or mutate** a framework-obligatory work-class — i.e. it targets core product
business logic / modules (`auth`, `users`, `permissions`, …) or an engineering cycle
(`implement`, `refactor`, `fix ticket`, `apply strategy`, `audit`) **with intent to change or
drive it** (not merely ask about it) — the agent **MUST NOT** silently fall back to native
tools or improvisation. It must halt and run the **Intent Warning Protocol**:

1. Warn the operator that a framework-obligatory task was detected without an engine session.
2. Present two explicit options to resolve the block:
   - **[Recommended] Framework Mode** — ask the operator to rephrase using `/strategy`,
     `/lifecycle`, or `/audit` (the engine front door).
   - **[Bypass] Freestyle Mode** — proceed with native tools ONLY if the operator inputs the
     exact phrase: *"Confirmar modo libre"*.

**Read-only questions / explanations about those domains stay in Native freedom** — they do
NOT trigger interception. The filter is about *doing* work on the core, not *asking* about it.
(This is the behavioral layer; <TICKET-ID> adds a `.claude/settings.json` hook as the hard,
tool-level enforcement underneath it.)

### Driving the engine
Route the three work-classes through the unified entrypoint:

```python
python -m framework.cli.run --mode <lifecycle|strategy> ...      # the engine
```

Read **`ai-specs/specs/operation-protocol.mdc`** — the executable source of truth for the
orient → loop → gate protocol and the exit-code contract:

- `0` → done.
- `10` → a `WorkRequest` (cognitive work): do it with native tools (`node` = the phase/op,
  `needs` = what to feed back), then `--resume --feed <fields.json>`.
- `20` → a human / gate stop: surface it to the operator and wait.
- A `WorkRequest` carrying a `gate` (a `HARD_LIMITS` action: push, jira-post, auth-15,
  scope-gap, strategic-choice) → do the prep, STOP for the operator's explicit authorization
  before the gated action (a push needs the exact push phrase).

The chat slash-commands (`/strategy`, `/lifecycle`, `/audit` — wired in framework release layer) are the
front door; each invokes the engine in the background. Never hand-run a lifecycle / strategy
/ audit flow outside the engine.
