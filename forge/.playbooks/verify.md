---
version: 1.4.3
category: lifecycle
user-invocable: false  # <TICKET-ID>: internal phase playbook executed via /lifecycle interrupts.
description: "Pre-merge quality gate; classify deviations; issue a verdict."
last_changed: 2026-06-01
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Pre-merge quality gate. Refuses to pass incomplete work.

# Goal

Verify that the implementation is complete, correct, and safe BEFORE committing and merging. This command is the quality gate between `/develop` and `/commit`. Nothing merges without passing `/verify`.

# Arguments

$ARGUMENTS

# Process

## Pre-flight: State Machine Guard (FW-004 — MANDATORY)

Before any work, verify lifecycle prerequisites via the state machine:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    check verify <TICKET> <MODULE>
```

- **rc=0** → proceed to Step 1.
- **rc=1** → REFUSE: `steps.develop.done != true`. Run `/develop <TICKET>` first.
- **rc=2** → state file missing. Backtrack to `/enrich-us`.

## Step 1: Gather Context

1. Read the Jira ticket via MCP to understand requirements and acceptance criteria.
2. Locate the implementation plan in `.lifecycle/artifacts/[module]/plans/Sprint [N]/` (determine sprint from Jira; derive module from the code path being modified, e.g., from `<workspace.backend_root>/{module}/` per WorkRequest workspace context).
3. Identify the feature branch and review all changes: `git diff main...HEAD --stat` and `git log main..HEAD --oneline`.
4. Read `forge/specs/integration-state.md` for current module state.

## Step 2: Plan Compliance Check (MANDATORY)

For EVERY step in the implementation plan, verify against the actual code:

1. Read each step from the plan document.
2. For each step, check if it was implemented by reading the actual source files cited in the plan.
3. Classify each step:

| Status | Definition |
|--------|-----------|
| **DONE** | Step fully implemented as planned |
| **DONE-DEVIATED** | Step implemented but differently than planned — requires deviation classification |
| **PARTIAL** | Step partially implemented — requires justification or completion |
| **SKIPPED** | Step not implemented at all — requires justification or completion |

4. Generate the Plan Compliance Report (see output format below).

## Step 3: Deviation Classification (MANDATORY)

For every step classified as DONE-DEVIATED, PARTIAL, or SKIPPED, classify the deviation.

The six categories (Accepted-Trivial, Accepted-Quality, Accepted-Risk, Deferred,
Pre-existing, Scope-Gap), their criteria, and which ones block merge are defined
once in **`workflow-standards.mdc §8` (Deviation Classification System)** and
enforced in code by **`classify-deviation.py`**. This prompt does not restate the
table — invoke the tool (below) and use the category it returns. Blocking
categories: **Accepted-Risk** (without approval) and **Scope-Gap**.

### How to determine the category (code-enforced — do NOT self-classify in prose)

Classification is enforced by `classify-deviation.py`, not by your judgment. You
supply only the **factual** answers to the decision tree (per `workflow-standards.mdc §8`);
the tool computes the category, refuses a `Scope-Gap`, and records the deviation
in `state.yml` under the lifecycle's lock. For **each** deviation, run:

```bash
python3 ~/projects/em-development-framework/forge/tools/classify-deviation.py \
    <TICKET> <MODULE> --description "<what deviated>" --step <N> --ref "verify#deviation-<i>" \
    --affects-security=<true|false> \
    --reduces-coverage=<true|false> \
    --has-justification=<true|false> \
    --postponed=<true|false> \
    --pre-existing=<true|false>
```

- The tool applies the tree (first YES wins) and prints the resulting category — use that in the report; do **not** override it.
- `Scope-Gap` → the tool exits 1 (blocks): implement the step or re-run with corrected answers. You cannot declare `Accepted-Trivial` to make it pass.
- `Accepted-Quality` / `Deferred` → the tool auto-creates the Jira ticket; capture the key it prints.
- `Accepted-Risk` → re-run adding `--risk-description`, `--compensating-controls`, `--residual-risk`, `--user-approved=true` (see below); the tool refuses without explicit approval.

The category criteria (what each category means) live in `workflow-standards.mdc §8`
and in the tool — this prompt does not restate the tree, to keep a single source.

### Accepted-Risk validation

For any deviation classified as Accepted-Risk, you MUST:

1. Describe the specific risk introduced or accepted
2. List compensating controls (if any exist)
3. Assess residual risk (HIGH / MEDIUM / LOW)
4. Present to the user with: "This deviation affects security. Approve to proceed, or I will implement the missing step."
5. **Do NOT proceed past this step without explicit user approval**

## Step 4: New Code Quality Checks (MANDATORY)

> **SSoT migration (<TICKET-ID>, framework release layer)** — the procedural checks formerly listed inline as `4a`–`4e` pseudocode now live as data in [`forge/.checks-registry.yml`](../.checks-registry.yml), governed by [`forge/schemas/checks.schema.yml`](../schemas/checks.schema.yml). They are executed deterministically by `forge/tools/verify-checks.py`. The narrative blocks `4f` / `4f.bis` / `4g` (audit-specific) stay in prose below.

Run the procedural-checks-as-config runner against the current branch:

```bash
python3 forge/tools/verify-checks.py --module <MODULE> --ticket <TICKET>
```

- **Exit 0** → all `block`-severity checks `passed` (or `not-applicable`). Continue to Step 4f if this is an audit-fix ticket, else Step 5.
- **Exit 1** → at least one `block`-severity check `failed` or `skipped-infra`. Verdict becomes **BLOCKED-GAP** unless the operator reclassifies a `skipped-infra` row as a deviation candidate (per Step 3 — graceful degradation: infra failures, e.g. a missing binary or subprocess timeout, do not silently masquerade as `failed`).
- **Exit 2** → registry parse / usage error. STOP — fix the registry and retry.

The runner reads `forge/.checks-registry.yml` and emits a Markdown table to stdout. **Paste the table verbatim into the verify report's "Code Quality Checks" section** (see template under Step 6). Each row carries `id`, `name`, `result` (`passed | failed | skipped-infra | not-applicable`), `severity` (`block | warn`), and a one-line `message`. `warn`-severity failures surface as deviation candidates without escalating the shell verdict.

To inspect the live registry from a shell: `cat forge/.checks-registry.yml` or `python3 forge/tools/validate-artifact.py forge/.checks-registry.yml`.

**Out-of-scope of this runner (kept in prose below)**: `## Step 4f`, `### Step 4f.bis`, `## Step 4g` — audit-specific narrative + judgment. **Also out-of-scope for this Wave**: `plan.md` CI Gate Anticipation table and `develop.md` Pre/Post-Implementation Integrity Check (deferred to a possible Wave 18b if the operator asks).

## Step 4f: Audit Finding Resolution Check (MANDATORY for audit remediation tickets)

If the ticket originates from an audit finding (title contains "Audit Fix", parent is an audit report ticket, or the plan references an audit check ID):

1. **Read the "Instances to Fix" table** from the Jira ticket description (added by `/enrich-us` Step 3). This table is in the ticket's `[enhanced]` section and contains: grep pattern, scope, and a numbered list of instances with file:line. If no table exists, grep the codebase yourself to enumerate all instances.
2. **Extract the grep pattern** from the "Grep pattern used" field in the Instances to Fix table. Document this pattern in the verification report — it will be reused by `/commit` Step 1b and `/audit-check`.
3. **For EVERY instance in the table**, read the actual source file at the cited line and verify the fix was applied:
   - If the instance was fixed → mark as RESOLVED
   - If the instance still shows the old pattern → mark as UNRESOLVED
4. **Re-grep the source directories** using the same pattern to catch any instances that were NOT in the original table (new files added since enrichment, or instances that were missed). Scope:
   - Backend: `<workspace.backend_root>/` (exclude vendored deps + build output + test files per product convention)
   - Frontend: `<workspace.frontend_root>/` (same exclusions)
5. **Generate the Audit Fix Resolution section** in the verification report (this section is MANDATORY for audit tickets — `/commit` Step 1b will check for it):

```
## Audit Finding Resolution

| # | File:Line | Status | Evidence |
|---|-----------|--------|----------|
| 1 | src/auth/login-security.service.ts:61 | RESOLVED | Now uses `ErrorMessages.loginSecurity.ACCOUNT_LOCKED` |
| 2 | src/auth/account.controller.ts:94 | UNRESOLVED | Still has `{ ttl: 900000, limit: 3 }` |
| NEW | src/auth/mfa.controller.ts:33 | UNRESOLVED | New instance not in original table |
```

6. **Check recurrence prevention**: Verify that the Jira ticket (or the implementation) includes a recurrence prevention mechanism (per audit-standards.mdc Section 6.3.2). If none exists, flag as **Accepted-Quality** deviation and note it in the Recurrence Prevention section of the verification report.

7. **Verdict impact**:
   - If ANY instance is UNRESOLVED → verdict is **BLOCKED-GAP** (must fix before proceeding)
   - If ALL instances are RESOLVED and no new instances found → this check passes
   - If recurrence prevention is missing → does NOT block merge, but creates a tech debt ticket

**Why this step exists**: Audit fix tickets were being marked Done after fixing only some instances. This step ensures 100% of instances are verified against live code before the ticket can proceed to `/commit`.

### Step 4f.bis: Coupling rule enforcement (<TICKET-ID>)

If the verification report includes (or will include) an "Audit Finding Resolution" section — i.e. this ticket touches F-resolutions or G-findings — additionally run the §22.3 coupling enforcement:

```bash
python3 forge/tools/audit-coupling-check.py
```

- Exit 0 → no violations. Proceed.
- Exit 1 → ≥1 finding with `disposition ∈ {acknowledged-deferred, open}` AND `severity ∈ {CRITICAL, HIGH}` lacks a matching `pending-improvements.yml` registry entry. **Verdict becomes BLOCKED-GAP** unless the operator approves an explicit reclassification or adds the missing registry entry on this branch (only when the entry would be legitimate per `feedback_no_unsolicited_backlog_mining`).

This step turns `workflow-standards.mdc §22.3` from policy prose into a mechanical gate (codified by <TICKET-ID> §22.7.2).

## Step 4g: Audit Completion Gate (MANDATORY for audit producer tickets)

If this ticket creates new files under `**/audits/**` (i.e. a new audit folder is being committed), run the completion gate:

```bash
python3 forge/tools/audit-completion-check.py <new-audit-folder>
```

- Exit 0 → complete (≥1 phase report + index/summary present).
- Exit 1 → incomplete. **Verdict becomes BLOCKED-GAP** unless the operator explicitly marks the audit as in-progress (in which case it should NOT be merged to main yet — produce the missing artifacts first).
- Exit 2 → parse/usage error (e.g. folder name doesn't match the canonical or legacy convention).

The tool requires ≥1 phase report (`NN-name.md` or legacy `fase-N-name.md`) and `00-index.md` or `00-summary.md` in the audit folder.

This step turns `workflow-standards.mdc §22.4` (completion gate) into a mechanical check (codified by <TICKET-ID> §22.7.1).

## Step 5: Verdict

Based on all checks, issue a verdict:

The verdict is `verify`'s structured output (emitted via the Closing Advance-State as `verdict=`); routing on it is the orchestrator's / state-machine's job, not this prompt's.

| Verdict | Condition | Merge-eligibility |
|---------|-----------|--------|
| **PASS** | All steps DONE or DONE-DEVIATED(Trivial), all checks pass | eligible to advance |
| **PASS-WITH-DEBT** | All steps done but some Accepted-Quality deviations | eligible to advance (tech-debt tickets created) |
| **BLOCKED-RISK** | One or more Accepted-Risk deviations without user approval | blocks — needs risk approval or the missing step |
| **BLOCKED-GAP** | One or more Scope-Gap items | blocks — must implement |
| **BLOCKED-BUILD** | Build or tests failing | blocks — must fix |

## Step 6: Generate Verification Report

Save the report to `.lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_verify.md` (same folder as the plan).

Present summary to the user:

```
## Verification Result: [VERDICT]

### Plan Compliance: X/Y steps complete
[table]

### Deviations: N found
- Trivial: X (no action)
- Quality: X (tech debt tickets created)
- Risk: X (awaiting approval)
- Deferred: X (Jira tickets created)
- Scope gaps: X (must implement)

### Code Quality Checks
- New files with tests: X/Y
- Security pattern violations: X
- Build: PASS/FAIL
- Tests: PASS/FAIL (N passing, N failing)

### Regression Checks
- Blast radius files: X verified
- Mock propagation: X/Y test files updated
- API contract: ALIGNED / N mismatches
- Schema compatibility: OK / N issues
- Export surface: OK / N broken consumers

### Outcome:
[the verdict + any blockers; merge-eligibility follows from the verdict, routed by the orchestrator / state-machine]
```

# Output format

## Plan Compliance Report

Save to `.lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_verify.md`:

```markdown
# Verification Report: [TICKET-ID] [Feature Name]

**Date**: YYYY-MM-DD
**Plan**: [path to plan file]
**Branch**: [branch name]
**Verdict**: PASS | PASS-WITH-DEBT | BLOCKED-RISK | BLOCKED-GAP | BLOCKED-BUILD

## Plan Compliance

| Step | Description | Status | Deviation Category | Notes |
|------|-------------|--------|-------------------|-------|
| 0 | Create feature branch | DONE | — | — |
| 1 | Create DTO | DONE | — | — |
| 2 | Create Service | DONE-DEVIATED | Accepted-Trivial | Used different method name |
| 3 | Write tests | PARTIAL | Accepted-Quality | hash-token.ts missing test → SCRUM-XXX |
| 4 | Update docs | DONE | — | — |

## Deviations

| # | Step | Category | Description | Risk | Action |
|---|------|----------|-------------|------|--------|
| 1 | 2 | Accepted-Trivial | Method renamed for consistency | None | Documented |
| 2 | 3 | Accepted-Quality | Test file not created for utility | Low | SCRUM-XXX created |

## Code Quality Checks

| Check | Result | Details |
|-------|--------|---------|
| New files with tests | 4/5 | hash-token.ts missing |
| Security patterns | 0 violations | — |
| Build | PASS | nest build clean |
| Tests | PASS | 463 passing, 0 failing |
| Integration state | UP TO DATE | — |

## Regression Verification

| Check | Result | Details |
|-------|--------|---------|
| Blast radius files verified | X/Y | [list any unverified] |
| Mock propagation | X/Y test files updated | [list any missing mocks] |
| API contract alignment | ALIGNED / MISMATCHED | [list mismatches if any] |
| Schema backward compatibility | OK / N issues | [list issues if any] |
| Export surface integrity | OK / N broken | [list broken consumers if any] |

## Audit Finding Resolution (MANDATORY for audit remediation tickets — omit for non-audit tickets)

**Audit check ID**: [e.g. CH-02]
**Grep pattern used**: `<exact pattern — from /enrich-us "Instances to Fix" table, or self-derived>`
**Grep scope**: `<workspace.backend_root>/` (per product convention; exclude vendored deps + build output + test files)
**Grep result**: 0 matches | N remaining (list file:line below)

| # | File:Line | Status | Evidence |
|---|-----------|--------|----------|
| 1 | src/auth/example.ts:42 | RESOLVED | Now uses ErrorMessages constant |
| NEW | src/auth/new-file.ts:10 | UNRESOLVED | New instance not in original table |

## Recurrence Prevention (MANDATORY for audit remediation tickets — omit for non-audit tickets)

| Prevention Mechanism | Type | Status |
|---------------------|------|--------|
| ESLint rule `no-hardcoded-errors` | Automated | Recommended / Implemented / N/A |
| Pre-commit hook check | Automated | Recommended / Implemented / N/A |
| Root cause: [why this pattern existed] | — | Documented |

## Accepted-Risk Items (if any)

[Formal risk assessment for each, requiring user approval]

## Tech Debt Tickets Created

| Ticket | Description | Sprint |
|--------|-------------|--------|
| SCRUM-XXX | Add tests for hash-token.ts | Current |
```

## Closing: Advance State (FW-004 — MANDATORY)

After the verify report has been written AND has passed `/validate-artifact` against `verify.schema.yml`, record completion:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    advance verify <TICKET> <MODULE> \
    --field verdict=<PASS|PASS-WITH-DEBT|BLOCKED-RISK|BLOCKED-GAP|BLOCKED-BUILD> \
    --field schema_validated=true \
    --field path=".lifecycle/artifacts/<MODULE>/plans/<sprint>/<TICKET>_verify.md" \
    --field deviations_count=<N>
```

`schema_validated=true` is the agent's assertion that `/validate-artifact <verify>` returned exit 0. If the verdict is `BLOCKED-*`, `/commit` will refuse — that is the intended gate. To unblock, address the underlying issue and re-run `/verify` with the updated verdict.

# Boundaries
- **NEVER skip Step 2** (Plan Compliance). Every step in the plan must be verified against live code.
- **NEVER auto-approve Accepted-Risk** deviations. Always present to user and wait for explicit approval.
- **NEVER let Scope-Gap items pass**. They must be implemented or explicitly reclassified by the user.
- **Read actual source files** for every verification — do not trust git diff alone (it doesn't show what was NOT changed).
- **Create Jira tickets** for Accepted-Quality and Deferred items immediately. Use the Jira MCP or REST API.
- If the plan doesn't exist (ticket was developed without `/plan`), still perform Steps 4-6 (code quality checks).
- All content must be written in **English**.

# References

- `forge/specs/workflow-standards.mdc`: Definition of DONE, branch lifecycle
- `forge/specs/integration-state.md`: Module dependency map
- `lifecycle/specs/backend-standards.mdc`: Coding standards
- `forge/_parked/specs/audit-standards.mdc` (parked per ADR-011): Section 6 — Post-Fix Verification, Risk Acceptance Criteria — referenceable but unmaintained pending audit subsystem unparking
- `.lifecycle/artifacts/[module]/plans/Sprint [N]/`: Implementation plans
