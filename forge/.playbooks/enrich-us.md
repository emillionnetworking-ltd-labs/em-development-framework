---
version: 1.2.3
category: lifecycle
user-invocable: false  # <TICKET-ID>: internal phase playbook executed via /lifecycle interrupts.
description: "Enrich a Jira ticket with full technical detail; bootstrap its state file."
last_changed: 2026-06-01
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Enricher of Jira user stories to full technical detail. Zero ambiguity, zero missing fields.

`enrich-us` is the first lifecycle phase: it bootstraps the ticket's state file and enriches the Jira ticket. Phase ordering is enforced by `state-machine.py` (the gate), not narrated here.

# Goal

Analyze a Jira ticket and enhance it with all the technical detail needed for a developer to complete it without asking questions. For audit remediation tickets, enumerate every single instance of the problem in the live codebase.

# Arguments

$ARGUMENTS

# Process

## Pre-flight: State Machine Guard (FW-004 — MANDATORY)

Before any work, verify lifecycle prerequisites via the state machine. The gate is enforced by code (`state-machine.py`), not by your interpretation of this instruction. Refusal cannot be bypassed.

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    check enrich-us <TICKET> <MODULE>
```

- **rc=0** → proceed.
- **rc=1** → REFUSE (no prereq for `/enrich-us`, so this should never fire — investigate).
- **rc=2** → state file missing. Expected on first run; the Closing step bootstraps it via `init-state.py`.

`<MODULE>` derivation: from the ticket's code path (e.g., from `<workspace.backend_root>/{module}/` per WorkRequest workspace context). Framework-reinforcement tickets without app code → `framework`. Unclear → `backlog`.

## Step 1: Gather Ticket Context

1. Use Jira MCP to get the ticket details (ticket id/number, keywords, or status indicators like "the one in progress").
2. Identify the ticket type: feature, bug, refactoring, audit remediation, or documentation.
3. Understand the problem described in the ticket.

## Step 2: Technical Completeness Check

Decide whether the User Story is completely detailed according to best practices. A complete story includes:
- Full description of the functionality
- Comprehensive list of fields to be updated
- Structure and URLs of necessary endpoints
- Files to be modified (per architecture and standards)
- Steps required for the task to be considered complete
- How to update relevant documentation or create unit tests
- Non-functional requirements (security, performance, etc.)

## Step 3: Audit Fix Instance Enumeration (MANDATORY for audit remediation tickets)

If the ticket originates from an audit finding (title contains "Audit Fix", parent is an audit report ticket, or description references an audit check ID), you MUST:

1. **Identify the pattern to fix** from the ticket description (e.g., "inline error strings", "magic numbers", "missing a11y attributes", "duplicated function").
2. **Define the grep pattern** explicitly. Document the exact regex or search term you will use, so it is reproducible.
3. **Grep the source directories** for ALL instances of the problem. Scope (paths from WorkRequest workspace):
   - Backend: `<workspace.backend_root>/` (exclude vendored deps + build output + test files per product convention)
   - Frontend: `<workspace.frontend_root>/` (same exclusions)
   - Use the actual source files — NEVER rely on ticket descriptions, audit reports, or memory.
4. **List every instance** with exact `file:line` references in the enhanced ticket description under an "## Instances to Fix" section:
   ```
   ## Instances to Fix

   **Grep pattern used**: `<exact pattern>`
   **Grep scope**: `<workspace.backend_root>/` (per product convention; exclude vendored deps + build output + test files)
   **Total instances**: N

   | # | File | Line | Current Code | Required Fix |
   |---|------|------|-------------|-------------|
   | 1 | src/auth/login-security.service.ts | 61 | `'Account locked...'` | Extract to ErrorMessages constant |
   | 2 | src/auth/account.controller.ts | 94 | `{ ttl: 900000, limit: 3 }` | Extract to named constant |
   ```
5. **The instance list IS the acceptance criteria.** The ticket is NOT done until every row in the table is fixed. This table becomes the verification checklist for `/verify` and `/commit`.
6. **If grepping reveals the issue is already fully fixed** (0 instances found), note this with evidence (the grep command and its empty output) and recommend closing the ticket. Do NOT close it automatically — let the user decide.
7. **Recurrence prevention** (ISO 27001 Cl.10.2): Add a "## Recurrence Prevention" section recommending how to prevent this pattern from reappearing. Examples:
   - ESLint custom rule to flag the pattern
   - Pre-commit hook check
   - CI pipeline gate
   - Code review checklist item
   - If no automated prevention is feasible, document why.
8. **SLA deadline** (per audit-standards.mdc Section 6.3.1): Add a "## SLA" line to the enhanced ticket with the calculated deadline:
   - Look up the ticket severity (from the audit report or Jira priority)
   - Apply the SLA table below to determine the deadline
   - Add to the ticket: `**SLA**: [severity] → [deadline description] (due by [date or sprint name])`

**Why this step exists**: Without enumerating every instance upfront, developers fix only the instances they remember or that are cited in the audit report, leaving others behind. This has caused tickets to be marked Done with incomplete fixes.

## Step 4: Enhance the Story

If the user story lacks the technical and specific detail necessary to allow the developer to be fully autonomous when completing it, provide an improved story that is clearer, more specific, and more concise in line with product best practices described in Step 2. Use the technical context you will find in @documentation. Return it in markdown format.

## Step 5: Update Jira

Update ticket in Jira, adding the new content after the old one and marking each section with the h2 tags [original] and [enhanced]. Apply proper formatting to make it readable and visually clear, using appropriate text types (lists, code snippets...).

## Step 6: Transition Status

If the ticket status was "To refine", move the task to the "Pending refinement validation" column.

# Remediation SLAs (for audit fix tickets)

When enriching audit fix tickets, note the expected remediation deadline based on severity:

| Severity | SLA | Reference |
|----------|-----|-----------|
| CRITICAL | Immediate — blocks current sprint | OWASP SAMM L3 |
| HIGH | Within current sprint | SOC 2 CC7.4 |
| MEDIUM | Within current sprint (or next if sprint is >80% complete) | ISO 27001 Cl.10.2 |
| LOW | Backlog — schedule within 2 sprints | Best practice |

## Closing: Advance State (FW-004 — MANDATORY)

After enriching the Jira ticket and confirming completeness, record completion in the lifecycle state file. This step BOOTSTRAPS the state file on first run.

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    advance enrich-us <TICKET> <MODULE> \
    --sprint "<sprint name>" \
    [--field jira_hash=<sha-of-enriched-jira-description>]
```

- `--sprint` is REQUIRED when the state file does not yet exist (the helper invokes `init-state.py` to create it).
- `--field jira_hash` is optional but recommended for drift detection.
- Subsequent invocations (e.g., re-enriching) update the existing state file in place.

Do not mark `enrich-us` done until this succeeds. The state file is the canonical record that enrichment happened; `state-machine.py` gates later phases on it.


# References

- `lifecycle/specs/backend-standards.mdc`: Architecture and coding standards
- `lifecycle/specs/frontend-standards.mdc`: Frontend architecture
- `forge/_parked/specs/audit-standards.mdc` (parked per ADR-011): Audit framework, severity classification, evidence requirements — referenceable but unmaintained pending audit subsystem unparking
- `forge/specs/integration-state.md`: Module dependency map
- `.lifecycle/artifacts/STATE-MACHINE.md`: Lifecycle state machine concept doc (FW-003).