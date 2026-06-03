# Commands Reference

The map of everything you can invoke in this framework. There are two kinds of
commands, and they are easy to confuse because some share a name:

- **Skills** — slash commands (`/<name>`) you type to the AI agent. They live in
  `forge/.playbooks/*.md` and are prompts the agent interprets.
- **Tools** — Python CLIs run by path (`python3 forge/tools/<name>.py …`).
  Invoked by you, by skills, or by CI. Deterministic; no LLM involved.

> **Source of truth:** since framework release layer (<TICKET-ID>) the canonical command surface
> lives in [`forge/commands.catalog.yml`](forge/commands.catalog.yml) (machine-readable,
> schema-validated). This document and `/help-framework` are **views** of that
> catalog — a test (`test_catalog.py`) fails CI if they drift. The Web Control
> Plane API reads the catalog directly.

## Invocation model

| You write… | What it is | Who runs it |
|---|---|---|
| `/<name>` | a **skill** (prompt) | the operator (agent interprets) |
| `python3 forge/tools/<name>.py …` | a **tool** (CLI shell) | operator, skills, or CI — by path |
| `import _<name>` | a **library** (pure logic) | code only — **never run directly** |

> **Libraries (`_<tool>.py`) are not commands.** Since the framework release layer refactor, each
> support tool is a thin CLI shell (`<tool>.py`) over an importable library
> (`_<tool>.py`). Run the hyphenated shell; never `python3 _state_machine.py`.
> The underscore modules exist to be `import`-ed (by the shells and the future
> orchestrator). See [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Lifecycle Skills (the 6-step pipeline)

The 6 lifecycle step-skills below are **`user_invocable: false`** in the catalog
(`forge/commands.catalog.yml`). They are **engine-driven phase playbooks** that
the agent reads at `/lifecycle <TICKET-ID>` interrupts — they are NOT typed
directly by the operator. To drive a ticket end-to-end, the operator entry
point is `/lifecycle <TICKET-ID>` (the umbrella). Per CLAUDE.md operating
contract + `forge/specs/operation-protocol.mdc`, each step is gated by
`state-machine.py` (a step refuses until the previous one is done).

Listed here for reference (this is what the engine reads, not what you type):

| Skill | Purpose | When the engine reads it |
|---|---|---|
| `enrich-us` | Enrich a Jira ticket with full technical detail; bootstrap its state file. | Phase 1 interrupt |
| `plan` | Produce a schema-validated implementation plan. | Phase 2 interrupt |
| `develop` | Implement the plan on a feature branch; report plan compliance. | Phase 3 interrupt |
| `verify` | Pre-merge quality gate; classify deviations; issue a verdict. | Phase 4 interrupt |
| `commit` | Commit, merge to main, clean up the branch. | Phase 5 interrupt + push gate |
| `update-docs` | Write the implementation record; update specs; transition Jira to Done. | Phase 6 interrupt |

Enforcement: `test_lifecycle_skills_are_engine_driven` in
`forge/tools/_tests/test_catalog.py` fails CI if any of these regress to
`user_invocable: true` (<TICKET-ID> framework release layer).

## 2. Utility Skills (operator-invoked, any time)

| Skill | Purpose |
|---|---|
| `/check-pending` | Surface eligible entries from the `pending-improvements` registry (observation-only). |
| `/sprint-cleanup` | Find pending-improvements eligible for closure at sprint-end; per-id operator approval required. Closes the loop of the register (<TICKET-ID>). |
| `/classify-deviation` | The single, code-enforced deviation classifier (per `workflow-standards §8`). Driven scripted by `/verify`; runnable standalone (interactive or scripted), and optionally opens a Jira ticket. The taxonomy SSoT lives in `forge/.deviation-taxonomy.yml` (<TICKET-ID>, framework release layer); use `python3 forge/tools/classify-deviation.py --print-taxonomy` to render it. |
| `/validate-artifact` | Validate one framework artifact against its JSON Schema. |
| `/help-framework` | Render this command map + the framework docs as an interactive in-chat dashboard. Reads `COMMANDS_REFERENCE.md` / `README.md` live (`/help-framework architecture` renders `ARCHITECTURE.md`). |
| `/strategy` | Run the Global Native Strategist on a target via the LangGraph engine (`framework.cli.run --mode strategy`): bounded anti-patch debate → human gate → executive report. Drives the engine — never pure-prompt. |
| `/lifecycle` | Operator umbrella: drive a ticket through the 6-step lifecycle via the LangGraph engine (`framework.cli.run --mode lifecycle`). The 6 step-skills (`enrich-us`/`plan`/`develop`/`verify`/`commit`/`update-docs`) are now `user-invocable: false` — hidden from this menu, read by the agent as phase playbooks at the engine's interrupts. |
| `/meta-audit` | Dispatch a framework meta-audit subsystem runner. Read-only mechanical self-check (4 metrics: idempotency / determinism / predictable-exit / isolation). Currently dispatches `lifecycle` only; `audit` / `orchestrator` reserved for future runners. Restored in <TICKET-ID> framework release layer. |

## 3. Tools (Python CLIs, run by path)

**Lifecycle support (CLI shell + importable lib):**

| Tool | Purpose |
|---|---|
| `state-machine.py` | The lifecycle gate: `check` / `advance` / `state`. Logic in `_state_machine.py`. |
| `validate-artifact.py` | Validate a `.md`/`.yml` artifact against its JSON Schema. Logic in `_validate_artifact.py`. |
| `init-state.py` | Bootstrap a ticket `state.yml` from the template. Logic in `_init_state.py`. |
| `classify-deviation.py` | The enforced deviation classifier (scripted from `/verify`, or interactive standalone) + Jira ticket creation. Writes `state.yml` under the shared `_StateLock`. Logic + typed `classify_typed()` in `_classify_deviation.py`. |

**Audit machinery (CI gates only after 2026-05-30 quarantine):**

| Tool | Purpose |
|---|---|
| `audit-completion-check.py` | Post-audit completion invariants (phase reports + index/summary present). |
| `audit-coupling-check.py` | Enforce §22.3 — deferred findings must be coupled to the pending-improvements registry. |

> Product-audit runners and the framework meta-audit product runner were moved to `forge/_parked/` on 2026-05-30 (cross-repo decoupling fallout). See [ADR-010](forge/specs/adrs/adr-010-parked-tools-and-playbooks.md) for the rationale and unparking criteria.

**Framework operations:**

| Tool | Purpose |
|---|---|
| `check-pending-improvements.py` | Report eligibility of the `pending-improvements` registry. |
| `sprint-cleanup.py` | Closer of the pending-improvements register loop. Per-id operator approval. Logic in `_sprint_cleanup.py`; typed model in `_pending_improvements.py` (<TICKET-ID>). |
| `anti_rot_checker.py` | Repo-wide GRD detector — catches broken paths, broken markdown links, file:line refs, and unreachable SHAs. BLOCKING CI gate (<TICKET-ID>). Logic in `_anti_rot_checker.py`. |
| `verify-checks.py` | Procedural checks-as-config runner (<TICKET-ID>, framework release layer). Reads `forge/.checks-registry.yml` (governed by `checks.schema.yml`); emits a ChecksReport with per-row `passed \| failed \| skipped-infra \| not-applicable`. Driven by `verify.md` Step 4. Logic in `_verify_checks.py`. |
| `meta-audit/lifecycle.py` | Mechanical meta-audit of the lifecycle subsystem (4 metrics: idempotency_safe / deterministic_output / predictable_exit_code / context_isolated). Pure-function State+Nodes pipeline; `langgraph` lib not imported. Restored in <TICKET-ID> framework release layer. |
| `meta-audit/framework_modules.py` | Mechanical audit of framework module boundaries (8 modules). 4 nodes: exports drift / import boundary / network I/O policy / cycle detection. AST-based; consumes `forge/.framework-modules.yml` SSoT. Added <TICKET-ID> framework release layer (CI warn-only first cycle). |
| `groundedness-snapshot.py` | Capture / update the groundedness baseline (`--update`). |

**Internal libraries (`import`-only, not commands):** `_state_machine.py`,
`_validate_artifact.py`, `_init_state.py`, `_classify_deviation.py`,
`_lifecycle_state.py` (the shared `LifecycleState` typed model), `_common.py`.

---

## Name-overlap: skill vs tool

Some names exist as **both** a skill and a tool. The skill is the operator/agent
entry point; the tool is the Python CLI it ultimately drives:

| Name | `/<name>` (skill) | `<name>.py` (tool) | `_<name>.py` (lib) |
|---|---|---|---|
| `validate-artifact` | the slash command | the CLI shell | the importable logic |
| `classify-deviation` | the slash command | the CLI shell | the importable logic |
| `meta-audit` | the dispatcher skill | — (runner is `meta-audit/lifecycle.py`) | — |
| `audit` / `audit-check` | the audit skills (product audit) | the `audit-*.py` mechanical runners | — |
| `check-pending` | the skill | `check-pending-improvements.py` | — |

Rule of thumb: **type `/name` to ask the agent; run `python3 …/name.py` to invoke
the CLI directly; never run an `_name.py`.**

See also: [README](README.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [ADRs](forge/specs/adrs/).
