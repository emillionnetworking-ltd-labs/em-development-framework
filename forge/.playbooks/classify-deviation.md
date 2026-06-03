---
version: 1.1.3
category: utility
user-invocable: false  # gov 2026-05-30: invoked as subprocess by /verify Step 3 and /update-docs Part 5; not an operator menu entry.
description: "Classify a /verify deviation (and optionally open a Jira ticket)."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Deviation classifier. Runs the code-enforced decision tree from `workflow-standards.mdc §8`. Cannot self-declare `Accepted-Trivial` — the tree refuses.

# Goal

Run `classify-deviation.py` with the given parameters. The script:
1. Walks the 5-question decision tree (interactive by default).
2. Classifies into one of: `Accepted-Trivial`, `Accepted-Quality`, `Accepted-Risk`, `Deferred`, `Pre-existing`, `Scope-Gap`.
3. For `Accepted-Quality` and `Deferred`: creates a Jira sub-ticket automatically (current sprint / backlog respectively).
4. For `Accepted-Risk`: requires `--risk-description`, `--compensating-controls`, `--residual-risk`, `--user-approved=true`. Creates Jira ticket if residual risk > LOW.
5. For `Scope-Gap`: refuses (exit 1) — the deviation must be implemented or reclassified with justification.
6. Appends the classified deviation to the ticket's `state.yml` `deviations[]` array.
7. Validates the updated state file against `state.schema.yml`.

# Arguments

`$ARGUMENTS` — at minimum:
- `<TICKET>` — the ticket where the deviation occurred (e.g., `<TICKET-ID>`)
- `<MODULE>` — module slug (e.g., `auth`, `framework`)
- `--description "..."` — what deviated (mandatory)

Optional:
- `--step N` or `--step "Step N"` — which plan step
- `--ref "verify#deviation-2"` — anchor into the verify or record document

# Process

## Step 1: Invoke the classifier

Default invocation (interactive — preferred when the user is at the terminal):

```bash
python3 ~/projects/em-development-framework/forge/tools/classify-deviation.py \
    <TICKET> <MODULE> --description "<short description>"
```

The script will ask 5 questions in order; **first YES wins**. Subsequent questions are skipped.

Scripted invocation (for agent automation, e.g., from `/verify` post-processing):

```bash
python3 ~/projects/em-development-framework/forge/tools/classify-deviation.py \
    <TICKET> <MODULE> --description "..." \
    --affects-security=false \
    --reduces-coverage=true \
    --has-justification=false \
    --postponed=false \
    --pre-existing=false
```

For Accepted-Risk (the security path), pass the four required fields:

```bash
python3 ~/projects/em-development-framework/forge/tools/classify-deviation.py \
    <TICKET> <MODULE> --description "..." \
    --affects-security=true \
    --risk-description "..." \
    --compensating-controls "..." \
    --residual-risk HIGH|MEDIUM|LOW|NEGLIGIBLE \
    --user-approved=true
```

## Step 2: Read the result

The script outputs:
- `classification: <category>` on its own line.
- If a Jira ticket was created: `created Jira ticket: SCRUM-NNN`.
- If state.yml was updated: `state.yml updated: <path>` + `validate-artifact: PASS`.

Exit codes:
- **0**: classified + recorded.
- **1**: REFUSE (Scope-Gap, Accepted-Risk without approval, Accepted-Trivial without justification, etc.).
- **2**: fatal error (state file missing, bad args).

## Step 3: When called from `/verify`

`/verify` should iterate through every deviation it detected and invoke this command (or the underlying script directly) for each. The mapping is:

| `/verify` detected | Invocation |
|---|---|
| Test omitted for new file | `--reduces-coverage=true --has-justification=false ...` |
| ForbiddenException → UnauthorizedException kept as Forbidden | `--affects-security=true ...` with full risk fields |
| Renamed variable / equivalent API | `--has-justification=true` (after security/coverage answers are no) |
| Deferred field validation | `--postponed=true` |
| Pre-existing jscpd flag | `--pre-existing=true` |
| Bare missing step with no justification | (all false) → Scope-Gap → refuse |

`/verify` MUST stop and surface the refusal if `classify-deviation` returns exit 1. Do not "skip the deviation" or "downgrade to a warning".

## Step 4: Updating the verify report

After running this command, the verify report's Deviations table should include a row referencing the Jira ticket key (if created) in the `Follow-up` column. The state file's `deviations[]` array is the canonical record; the verify document points back to it.

# Boundaries
- **Trust the tree.** First YES wins. The agent cannot revisit answers to land on a different category.
- **No self-classification of Accepted-Trivial.** The script will refuse if `has-justification` is not explicitly true AND questions 1-2 are not explicitly false.
- **Accepted-Risk requires user approval.** Even when invoked non-interactively by the agent, the `--user-approved=true` flag must be present and reflect actual user authorization. Setting it to true without user input is a violation.
- **Scope-Gap blocks.** Exit 1 means the deviation cannot pass through the lifecycle. Re-classify (with justification) or implement.
- **Don't bypass via `--no-jira` for Accepted-Quality / Deferred.** That flag exists for offline / testing only. In production runs the Jira ticket is the audit trail.
- All output in English.

# Dependencies

- `forge/tools/classify-deviation.py` — the actual classifier.
- `forge/tools/validate-artifact.py` (FW-002) — auto-invoked to validate state.yml post-write.
- `forge/tools/state-machine.py` (FW-004) — state.yml schema + monotonic lifecycle.
- `JIRA_EMAIL` and `JIRA_TOKEN` environment variables (for auto-creation of tickets). Without these, the script appends to state.yml but skips Jira and prints a warning.

# Out of scope (deferred)

- Auto-creation of Jira tickets for Pre-existing and Accepted-Risk (residual > LOW). The script knows the categories but FW-005 MVP only auto-creates for Accepted-Quality and Deferred. Add to the script's `JIRA_RULES` map when extending.
- Wiring `/verify` to invoke this command for each deviation it produces. Currently `/verify` documents the classification process; agent + this command close the loop. A future ticket can hard-wire it.
- Cross-reference enforcement: ensuring every Deviations table row in the verify document maps to a deviation in state.yml. Future ticket.

# References

- `forge/specs/workflow-standards.mdc §8` — Deviation Classification System.
- `forge/.playbooks/verify.md` — Step 3 (Deviation Classification) — currently agent-interpreted, FW-005 makes it code-enforced.
- `.lifecycle/artifacts/STATE-MACHINE.md` (FW-003) — state.yml structure including the `deviations[]` array.
- Architectural audit 2026-05-13 §3 — <TICKET-ID> self-justified Accepted-Trivials.
