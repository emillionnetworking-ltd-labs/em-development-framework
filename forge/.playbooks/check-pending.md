---
version: 1.1.4
category: utility
user-invocable: false  # gov 2026-05-30: invoked by CI (`Sprint Cleanup: pending candidates`) and pre-flight banner; not an operator menu entry.
description: "Surface eligible entries from the pending-improvements registry (observation-only)."
last_changed: 2026-06-02
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

You are a framework roadmap observer. Run `check-pending-improvements.py` and surface the eligibility report to the operator. Do NOT auto-create Jira tickets or take other side-effect actions; tool + skill are observation-only per `feedback_no_unsolicited_backlog_mining`.

# Goal

Show the operator which entries in `forge/registers/pending-improvements.yml` (<TICKET-ID> / cross-cutting-policies.mdc §4) are currently `eligible` (auto-trigger fired) or `manual-check-due` (next_check date reached). Distinguish call-to-action items from compact waiting list.

# Process

## Step 1: Pre-flight

Confirm the framework registry exists:

```bash
ls -la forge/registers/pending-improvements.yml
```

If missing, surface error and stop. Likely cause: not in framework repo OR <TICKET-ID> not yet merged in this clone.

## Step 2: Run the report

```bash
python3 forge/tools/check-pending-improvements.py --report
```

Capture stdout + the exit code:

- **rc=0** → no eligible OR manual-check-due items. Quiet day. Report the compact summary and stop.
- **rc=1** → ≥1 eligible OR manual-check-due. Display the call-to-action section verbatim. THEN proceed to Step 3.
- **rc=2** → registry parse error / framework root not found. Surface the stderr to the operator.

## Step 3: Operator decision (only if rc=1)

For each ELIGIBLE / MANUAL-CHECK-DUE entry shown, ask the operator briefly:

> Found N eligible / M manual-check-due items. Want me to: (a) propose a ticket for any of them, (b) update last_checked for items you've reviewed, (c) just acknowledge and continue?

**Do NOT take action without explicit operator confirmation.** Specifically:

- Never open Jira tickets autonomously.
- Never modify the registry without `--update-checked` invocation explicitly approved.
- Never reclassify status (waiting/eligible/done/withdrawn) without operator instruction.

## Step 4: If operator chooses --update-checked

Invoke the tool with the operator-provided id + note:

```bash
python3 forge/tools/check-pending-improvements.py \
  --update-checked <id> \
  --note "<one-line audit note from operator>"
```

Confirm the OK output back to the operator.

# Boundaries
- This skill is **utility category** per `test_skill_structure.py` <TICKET-ID> taxonomy.
- This skill **does not** advance the lifecycle state machine (FW-004). It is an out-of-band observation tool.
- Output exits codes 0/1/2 are meaningful — surface them to the operator.
- If the registry is stale (last_checked across the board ≥30 days), surface that as an observation in the report.
- Never auto-create Jira tickets per `feedback_no_unsolicited_backlog_mining`.

# References

- `forge/tools/check-pending-improvements.py` — CLI tool.
- `forge/registers/pending-improvements.yml` — registry data.
- `forge/schemas/pending-improvements.schema.yml` — schema.
- `forge/specs/cross-cutting-policies.mdc §4` — full contract.
- ADR-007 — Phase 4 conditional triggers source for several registry entries.
