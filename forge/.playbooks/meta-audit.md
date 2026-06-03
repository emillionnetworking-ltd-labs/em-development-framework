---
version: 1.2.2
category: utility
description: "Dispatch a framework meta-audit (/meta-audit lifecycle | all)."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

You are the framework **meta-audit dispatcher**. Your only job is to select and run the requested meta-audit subsystem runner and surface its report and exit code. You are a thin dispatcher: you do NOT interpret, triage, score, or create tickets — that judgment layer is deliberately deferred (it is the successor to the removed `/re-audit`, to be added once ≥2 runners exist).

The meta-audit is the framework's mechanical self-check: it verifies that a framework subsystem (its tools and schemas) is deterministic, isolated and exit-code-honest enough to be governed by the orchestrator. Each subsystem has its own runner under `forge/tools/meta-audit/<subsystem>.py` (LangGraph State/Nodes/Edges modeled in pure functions).

# Goal

Give the operator an unambiguous, typed handle to choose **which** framework meta-audit runs — removing the ambiguity of conversational selection and the naming overlap with the product `/audit`. The subsystem is the argument, never inferred.

# Arguments

`$ARGUMENTS` — the subsystem to audit. One of:

- `lifecycle` — the ticket-lifecycle subsystem (framework release layer debut, framework release layer BLOCKING).
- `framework-modules` — the module-boundary auditor (framework release layer debut, warn-only). Verifies that each module declared in `forge/.framework-modules.yml` respects its declared `public_exports`, `allowed_imports`, and `network_io_policy`.
- `all` — every runner that exists under `forge/tools/meta-audit/`. Overall exit non-zero if ANY runner returns non-zero.
- (empty) — default to `lifecycle`.
- `audit`, `orchestrator` — reserved for runners not built yet.

Optional pass-through flags forwarded to the runner when supported: `--json`, `--phase <name>`.

# Process

1. Parse `$ARGUMENTS` into `<subsystem>` (+ any pass-through flags). If empty, use `lifecycle`.
2. Resolve the runner:
   - `lifecycle` → `python3 forge/tools/meta-audit/lifecycle.py [flags]`
   - `framework-modules` → `python3 forge/tools/meta-audit/framework_modules.py [flags]`
   - `all` → run **each** existing `forge/tools/meta-audit/*.py` runner in turn (today: `lifecycle.py` + `framework_modules.py`). Report each runner's section; the overall exit is non-zero if ANY runner exits non-zero. With ≥2 live runners, `all` is now operationally meaningful (framework release layer unlocked this).
   - a reserved-but-unbuilt subsystem (`audit`, `orchestrator`) → check whether `forge/tools/meta-audit/<subsystem>.py` exists. If it does not, print `meta-audit: '<subsystem>' runner not built yet` and exit 0 (do NOT error, do NOT improvise an audit).
   - any other value → print the valid subsystem list and exit 2 (usage).
3. Run the resolved command and surface its **stdout report and exit code verbatim**. Do not summarize away or reinterpret the runner's verdict.
4. Stop. Do NOT classify findings, propose follow-ups, or create Jira tickets — the runner's output IS the deliverable. (When the judgment layer is added in a future ticket, it will live here.)

# Boundaries

- **Dispatch-only**: never re-implement audit logic in this skill; always shell out to the runner.
- **Observation-only**: never creates Jira tickets or takes side-effecting actions (per `feedback_no_unsolicited_backlog_mining`).
- **Honor the runner's exit contract**: `0` = CLEAN/WARNING, `1` = a stage is BROKEN, `2` = usage error. Surface it; do not mask it.
- **Subsystem is explicit**: never guess which subsystem the operator meant — if the argument is missing default to `lifecycle`; if it is unrecognized, show the valid list.

# References

- `forge/tools/meta-audit/lifecycle.py` — the lifecycle runner.
- `forge/tools/meta-audit/framework_modules.py` — the framework-modules runner (framework release layer).
- `forge/.framework-modules.yml` — SSoT for the 8 declared modules (framework release layer).
- `forge/schemas/framework-module.schema.yml` — schema governing the SSoT.
- `INSTALL.md` — "Meta-Audit (framework self-check)" section.
- `feedback_no_unsolicited_backlog_mining` — observation-only, no auto-tickets.
