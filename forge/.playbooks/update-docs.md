---
version: 2.2.3
category: lifecycle
user-invocable: false  # <TICKET-ID>: internal phase playbook executed via /lifecycle interrupts.
description: "Write the implementation record; update specs; transition Jira to Done."
last_changed: 2026-06-02
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Writer of the implementation record + spec updates post-merge.

# Goal

Create a post-implementation record that documents what actually happened during development, and update any technical documentation (data-model.md, api-spec.yml, standards files) that changed.

# Arguments

$ARGUMENTS

# Process

## Pre-flight: State Machine Guard (FW-004 — MANDATORY)

Before any work, verify lifecycle prerequisites via the state machine:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    check update-docs <TICKET> <MODULE>
```

- **rc=0** → proceed to Part 1.
- **rc=1** → REFUSE: `steps.commit.done != true`. Run `/commit <TICKET>` first.
- **rc=2** → state file missing. Backtrack to `/enrich-us`.

## Part 1: Create Implementation Record

1. Identify the ticket from `$ARGUMENTS` (e.g. `<TICKET-ID>`). If it's a Jira ticket, fetch it via MCP to get the current state.
2. Locate the original plan in `.lifecycle/artifacts/[module]/plans/Sprint [N]/` (e.g. `auth/plans/internal cycle/SCRUM-42_backend.md`). Determine the ticket's sprint from Jira and derive the module from the code path modified (e.g., from `<workspace.backend_root>/{module}/` per WorkRequest workspace context) to locate the correct subfolder.
3. Inspect the implementation: review git log, changed files, test results, and any open issues.
4. Create the record document following the template below.
5. Save to `.lifecycle/artifacts/[module]/records/Sprint [N]/[jira_id]_[scope].md` where scope is `backend`, `frontend`, or `fullstack`. Use the same module and sprint subfolder as the plan.

### ⚠️ Directriz de Gobernanza Anti-Rot: Registro de SHAs (GRD-002a)

- **Regla de Oro:** NUNCA escribas en la documentación o en los records de tickets el SHA local de un commit que se encuentra en una rama de feature antes del merge.
- **El Motivo:** Al realizar un *Squash Merge* en GitHub, todos esos commits locales se destruyen y se unifican en un único ID de commit en `main`. El ID original se vuelve inalcanzable (*unreachable*), rompiendo el Anti-Rot Checker en el siguiente ciclo.
- **Procedimiento Correcto:**
  1. Documenta la historia de manera temporal usando placeholders (ej. `<WAVE_COMMIT>`).
  2. Una vez fusionado el PR en `main`, haz un `git pull` local.
  3. Recupera el SHA definitivo generado por GitHub en `main` y reemplaza el placeholder en tu commit de actualización de documentación.
- **Regla anti-propagación multi-generacional (validada operativamente 3 generaciones consecutivas Waves 15→16→17→18):** al citar o referenciar un record de ticket anterior en un nuevo record (p.ej. "este Wave dehasheó `XXXXXXX` en el record SCRUM-NNN"), debes **limpiar o des-hashear los SHAs locales pre-squash del documento citado** ANTES de quotearlos. Cada generación de record que arrastre un SHA del anterior se vuelve un nuevo nodo unreachable; el Anti-Rot Checker la detectará en cascada y romperá el siguiente ciclo de CI por herencia. **Sustituye el literal por una frase narrativa** (p.ej. "la SHA pre-squash de SCRUM-NNN") o por el merge_commit canónico de `main` (que SÍ es reachable). El cite-by-narrative corta la cadena.
- **Subtype 3 (framework release layer extension — capturado por CI cuando promovimos el meta-audit a BLOCKING):** NUNCA cites los SHAs cortos pre-squash **de tu propio branch** en el record que estás escribiendo, ni siquiera cuando narres qué commits absorbió el squash. Ejemplo: el record de <TICKET-ID> citó "2 commits absorbed" con sus SHAs literales del feature branch, que se volvieron unreachable post-squash. **Remedio**: en lugar de "squash merged commits con sus SHAs literales", usa **únicamente narrativa + merge_commit** (p.ej. "squash merged 2 cleanup commits; merge_commit visible en origin/main history"). El merge_commit SÍ es reachable por Anti-Rot Checker. Esta regla corta la generación de nodos unreachable de raíz — los commits originales del feature branch quedan dangling tras la squash y NO deben citarse jamás.
- **Subtype 4 (framework release layer META-recurrence — framework release layer codification):** Cuando narres un incidente GRD-002a previo en una sección lessons-learned (p.ej. "Wave N record cited Wave (N-1) SHA"), **la propia descripción del incidente debe dehashear el SHA ofensivo también**. Usa paráfrasis narrativa ("the Wave-(N-1) feature-branch pre-squash SHA") o cita el merge_commit reachable. NUNCA reproduzcas el SHA literal — describir la violación reproduce la violación. framework release layer capturó este pattern: el record <TICKET-ID> documentó el incidente Wave-24 GRD-002a citando el SHA Wave-24 4 veces, lo cual el groundedness baseline gate detectó como NEW violation en el CI de framework release layer. Sexta recurrencia consecutiva (Waves 18+21+22+24+25+26) atribuida a este subtype. **Remedio mecánico (framework release layer piggyback)**: instalar el hook `forge/tools/hooks/pre-commit-grd002a.py` vía `python3 forge/tools/em-cli.py install-hook --hook=pre-commit-grd002a` — el hook escanea el staged diff por SHAs no-reachable desde origin/main y bloquea el commit local antes de que llegue al PR-CI cycle. Cierra TANTO el subtype 4 (lessons-learned narrative) COMO el docs-only direct-to-main gap (framework release layer root cause) en una sola mitigación.

## Part 2: Update Integration State (MANDATORY)

6. Review all code changes made during implementation and determine if any of the following changed:
   - New NestJS modules added or existing modules modified (imports, exports, providers)
   - New guards added or existing guard dependencies changed
   - New controller guard chains (`@UseGuards()`) added or modified
   - New services injected into controllers or other services
   - New permissions seeded or role assignments changed
   - New test mock requirements introduced
7. Update `forge/specs/integration-state.md` with all changes identified above:
   - Module Registry table: add/update module entries
   - Guard Dependency Map: add/update guard entries
   - Controller Guard Chains: add/update controller entries
   - Permissions Registry: add/update permissions if changed
   - Test Mock Requirements: add/update mock entries
   - Service Dependency Chains: add/update chains
   - Changelog: add a new row with date, ticket ID, and summary of changes

## Part 3: Update Technical Documentation

8. Review all code changes made during implementation.
9. Update technical documentation as needed, following `forge/specs/documentation-standards.mdc`:
   - Data model changes → Update `forge/specs/data-model.md`
   - API endpoint changes → Update `forge/specs/api-spec.yml`
   - Standards/libraries/config changes → Update relevant `*-standards.mdc` files
   - Architecture changes → Update relevant architecture documentation
10. All documentation must be written in English.

## Part 4: Jira Ticket Update (if deviations exist)

11. If the implementation deviated from the original plan, update the Jira ticket description via MCP to reflect the actual state. The Jira ticket must always reflect the current truth.

## Part 5: Deviation Resolution (MANDATORY)

12. After writing the implementation record, review Section 5 (Deviations from Plan) and Section 7 (Bugs Found).
13. **If `/verify` was already run**: import the deviation classifications from the verification report (`[jira_id]_verify.md`). Do NOT reclassify — use the already-approved classifications. If `/verify` was not run (legacy flow), classify now using the criteria below.
14. Classify each remaining deviation and bug. The six categories
    (Accepted-Trivial, Accepted-Quality, Accepted-Risk, Deferred, Pre-existing,
    Scope-Gap), their criteria, and their required actions are defined once in
    **`workflow-standards.mdc §8` (Deviation Classification System)** and enforced
    in code by **`classify-deviation.py`** — this prompt does not restate the
    table or the decision tree. In the normal flow `/verify` already classified
    via the tool (step 13): import those classifications and do NOT reclassify.
    Only when `/verify` was skipped (legacy flow) do you classify now, by running
    `classify-deviation.py` per §8. Ticket-creation outcomes per category
    (Accepted-Quality / Deferred / Pre-existing → Jira ticket; Scope-Gap →
    blocks; Accepted-Risk → see below) are handled in steps 15–18.

### Accepted-Risk requirements

Any deviation classified as Accepted-Risk MUST include in the record:

1. **Risk description**: What specific risk is introduced or accepted
2. **Compensating controls**: What existing mechanisms reduce the risk
3. **Residual risk level**: HIGH / MEDIUM / LOW / NEGLIGIBLE
4. **User approval**: Reference to `/verify` approval or explicit approval in this session
5. **Follow-up**: Jira ticket if residual risk > LOW

15. For each deviation classified as **Accepted-Quality**, **Deferred**, or **Pre-existing**:
    a. Create a Jira ticket via MCP with: summary, context (which ticket exposed it), trade-off rationale, affected files.
    b. Assign to the correct sprint (current sprint for Accepted-Quality and Pre-existing, backlog for Deferred unless urgent).
    c. Add the ticket ID to the record's Deviations table in the "Follow-up" column.

16. For **Scope-Gap** items: alert the user and do NOT proceed until the gap is resolved (either fixed or explicitly reclassified by user with justification).

17. For **Accepted-Risk** items without prior `/verify` approval: present the risk assessment to the user and wait for explicit approval before finalizing the record.

18. Present a summary table to the user:

```
| Deviation | Category | Risk | Action Taken |
|-----------|----------|------|-------------|
| Example: used TOTP class instead of authenticator | Accepted-Trivial | None | Documented |
| Example: hash-token.ts missing test | Accepted-Quality | Low | Created SCRUM-XXX |
| Example: kept 403 for unverified accounts | Accepted-Risk | HIGH | User approved — SCRUM-XXX for remediation |
| Example: validation field stripping deferred | Deferred | — | Created <TICKET-ID> |
| Example: 13 pre-existing test failures | Pre-existing | — | Created SCRUM-XXX |
```

If there are zero deviations and zero bugs: "No deviations — implementation followed the plan exactly. No follow-up needed."

## Part 6: Commit ai-specs changes (MANDATORY)

The `/commit` command operates on the `em-ecosystem-code` repo, NOT on `ai-specs`. Without this step, plans, records, and spec updates accumulate in `ai-specs` working tree and never reach the remote — exactly the kind of drift that the internal cycle backfill (commit `a55fc30`) had to clean up. Treat this as the closing handshake of the lifecycle.

### Steps

19. **Identify the files to stage** based on what was created or modified in Parts 1-3 of this run:
    - `.lifecycle/artifacts/[module]/records/Sprint [N]/[jira_id]_[scope].md` — the new record (Part 1)
    - `.lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_[scope].md` — the original plan, if not already committed
    - `.lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_verify.md` — the verify report, if not already committed
    - `forge/specs/integration-state.md` — if Part 2 modified it
    - `forge/specs/data-model.md`, `forge/specs/api-spec.yml`, `forge/specs/*.mdc` — any specs touched in Part 3

20. **Stage explicitly** (do NOT `git add -A` or `git add .`): list each file by name in the `git add` command. This keeps the commit scoped and avoids picking up unrelated work-in-progress that may exist in `forge/` from other sessions.

    ```bash
    cd ai-specs && git add \
      ".lifecycle/artifacts/[module]/records/Sprint [N]/[jira_id]_[scope].md" \
      ".lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_[scope].md" \
      ".lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_verify.md" \
      forge/specs/integration-state.md
      # … add other touched specs files as needed
    ```

21. **Verify the staging matches expectations**: run `git diff --staged --name-only` and confirm only the files identified in step 19 are staged. If anything unexpected appears, unstage it (`git restore --staged <file>`) and report to the user.

22. **Confirm the working tree state was clean for these files BEFORE this run**: if any of the staged files had pre-existing uncommitted changes from another session (i.e. they were modified before `/develop` started for this ticket), STOP and alert the user — do not absorb someone else's work into this commit.

23. **Commit** to ai-specs `main` (no feature branch — ai-specs convention is direct-to-main for docs) with a message in this format:

    ```
    docs([TICKET-ID]): plan, verify, record + spec updates

    Closes the documentation lifecycle for [TICKET-ID] ([Feature Name]).
    Code shipped in em-ecosystem PR #[N] / commit [hash].

    Artifacts:
    - changes/[module]/plans/Sprint [N]/[jira_id]_[scope].md (plan)
    - changes/[module]/plans/Sprint [N]/[jira_id]_verify.md (verify, verdict: [PASS|PASS-WITH-DEBT])
    - changes/[module]/records/Sprint [N]/[jira_id]_[scope].md (record)

    Specs updated: [list, e.g. integration-state.md, api-spec.yml]

    Refs: [TICKET-ID]
    ${CLAUDE_ATTRIBUTION_LINE:-}
    ```

    Operator-set attribution: if `$CLAUDE_ATTRIBUTION_LINE` is exported in the
    shell (e.g. `Co-Authored-By: <agent-id>`), it lands in the commit; otherwise
    the line stays empty. Hardcoded model names + emails are prohibited
    (<TICKET-ID>). The agent never decides attribution.

24. **Push** to `origin/main`:

    ```bash
    git push origin main
    ```

    If the push is rejected (origin advanced because another session pushed concurrently): `git pull --rebase origin main`, resolve any conflicts (extremely rare for plans/records since each ticket has its own files), then retry the push. **Never force-push** — if rebase has irreconcilable conflicts, stop and report.

25. **Report** the result in the final summary (alongside the deviation table from step 18):

    ```
    ## ai-specs sync
    - Commit: [hash] on main
    - Push: [success | retried after pull-rebase | failed — see error]
    - Files: [N artifacts + M spec updates]
    ```

### When to skip Part 6

- **Dry-run / description-only mode**: if the user explicitly invoked `/update-docs` with "no commit", "dry run", "description only", or similar wording, skip Part 6 entirely and tell the user "ai-specs commit skipped per request — files staged for review."
- **No ai-specs changes at all** (extremely rare — implies no record, no spec updates): Part 6 is a no-op, report "No ai-specs changes to commit — record was not created."
- **Working tree already had unrelated dirty files**: stage only the ones from step 19, leave the rest alone, and note this in the summary.

# Output format

Markdown document at the path `.lifecycle/artifacts/[module]/records/Sprint [N]/[jira_id]_[scope].md` containing the implementation record.
Follow this template:

## Implementation Record Template Structure

### 1. **Header**
- Title: `# Implementation Record: [TICKET-ID] [Feature Name]`

### 2. **Summary**
- What was implemented (1-2 sentences)
- Scope: `backend`, `frontend`, or `fullstack`
- Branch name: `feature/[ticket-id]-[scope]`
- Implementation date(s)

### 3. **Plan Reference**
- Link to original plan: `.lifecycle/artifacts/[module]/plans/Sprint [N]/[ticket-id]_[scope].md`
- Plan was followed: Yes / Partially / No (with explanation)

### 4. **Commits**
List all commits related to this ticket:

| Hash | Message | Key Files Changed |
|------|---------|-------------------|
| (historical commit, pre-rename) | <TICKET-ID>: Add rate limiting middleware | `src/common/guards/throttle.guard.ts`, `src/app.module.ts` |

### 5. **Deviations from Plan**
Document any changes from the original plan:

| Step | Planned | Actual | Reason | Category | Follow-up |
|------|---------|--------|--------|----------|-----------|
| Step 3 | Use `express-rate-limit` | Used `@nestjs/throttler` | Better NestJS integration | Accepted-Trivial | — |
| Step 5 | Create test for helper | Not created | Time constraint | Accepted-Quality | SCRUM-XXX |
| Step 7 | Sanitize validation fields | Deferred — breaks frontend UX | Trade-off needs frontend input | Deferred | <TICKET-ID> |

Category values: `Accepted-Trivial`, `Accepted-Quality`, `Accepted-Risk`, `Deferred`, `Pre-existing`, `Scope-Gap`.
Follow-up values: `—` (no action), `SCRUM-XXX` (Jira ticket), or `BLOCKED` (must resolve before commit).

If no deviations: "Implementation followed the plan exactly."

### 6. **Test Results**
- Overall coverage: `XX%`
- Unit tests: `XX passed / XX failed`
- Integration tests: `XX passed / XX failed`
- Manual verification: List of scenarios tested and results
- Any tests skipped and reason

### 7. **Bugs Found**
Issues discovered during implementation:

| Bug | Severity | Status | Resolution |
|-----|----------|--------|------------|
| Race condition in token refresh | HIGH | Fixed | Added mutex lock in `auth.service.ts` |
| Missing index on `audit_logs.userId` | MEDIUM | Deferred to <TICKET-ID> | Performance acceptable for now |

If no bugs: "No bugs found during implementation."

### 8. **Documentation Updates**
List all documentation files updated as part of this implementation:

| File | Changes Made |
|------|-------------|
| `forge/specs/api-spec.yml` | Added 3 new endpoints under `/auth/` tag |
| `forge/specs/data-model.md` | Added `AuditLog` entity definition |

### 9. **Audit Finding Verification** (MANDATORY for audit remediation tickets — omit for non-audit tickets)

If this ticket remediates an audit finding, include:

```
- **Audit check ID**: [e.g. CH-02]
- **Grep pattern used**: `<pattern>`
- **Grep result**: 0 matches in `<workspace.backend_root>/` (excluding vendored deps + build output + test files per product convention)
- **All instances resolved**: Yes (N/N fixed)
- **Recurrence prevention**: [mechanism — e.g., "ESLint rule X", "already covered by /verify Step 4b security patterns check", or "No automated prevention feasible — documented"]
- **Root cause**: [why this pattern existed]
- **SLA status**: Completed within SLA / Overdue by N days (reference: [severity] → [SLA from audit-standards.mdc 6.3.1])
```

This section satisfies audit-standards.mdc Section 6.3 (Post-Fix Verification) and Section 6.3.2 (Recurrence Prevention). Without it, the next audit may flag the same finding as REGRESSED.

### 10. **Lessons Learned**
Brief insights for future implementations:
- What went well
- What was harder than expected
- Recommendations for similar tickets

### 11. **Recommended Follow-ups** (FW-303 — OPTIONAL but RECOMMENDED)

Items discovered during implementation that should become NEW Jira tickets but are out of the current ticket's scope. Without this section, follow-ups die in the doc and never get tracked (audit 2026-05-13 §2 explicit gap).

**Format** — one bullet per follow-up, all fields on a single line:

```
- **<short summary, imperative>** (priority=<LOW|MEDIUM|HIGH|CRITICAL>, module=<module-slug>, type=<bug|tech-debt|feature|test|doc>) — <one-line rationale of why this is needed and what triggered the discovery>.
```

Example:

```
- **Add E2E test for OAuth state URL-encoding** (priority=HIGH, module=auth, type=test) — current unit tests mock the encode step; an E2E found a real edge case with `+` chars that unit tests miss.
- **Refactor TokenService to extract refresh-rotation logic** (priority=MEDIUM, module=auth, type=tech-debt) — refresh logic is now duplicated across login + refresh + admin endpoints; extract once when next touched.
```

Omit the section entirely if there are no follow-ups (do not write "None" — absence is the signal).

The bullets are intentionally human-readable; the operator decides which become Jira tickets and creates them via the standard Mode C path.

### 12. **Rollback Playbook** (<TICKET-ID> / Phase 2 — RECOMMENDED for all tickets; MANDATORY for AUTH per `workflow-standards.mdc §15.3.3`)

Concrete procedure to undo this change in production without leaving partial state. AI-generated commits are often denser than hand-written ones and may touch non-obvious files; an explicit rollback recipe reduces "how do we undo this at 2 a.m." friction.

#### 12.1 Trigger conditions

Brief list of symptoms that should trigger rollback. Examples:

- `p95 latency > 500ms on POST /auth/login`
- `error rate on POST /sessions > 1%`
- `regression in passkey-login E2E spec under jest CI`

Omit this sub-section if the change is purely additive AND has no production-runtime effect (e.g. docs-only commit).

#### 12.2 Rollback steps (in execution order)

1. **Revert commit**: `git revert <merge-sha>` to a hotfix branch, then merge.
2. **Migration handling**:
   - If a Prisma migration ran: run the corresponding `down` migration OR explain why the change is forward-only (backward-compatible per `workflow-standards.mdc §9` Breaking Change Checklist) and no DB action is needed.
   - If new schema columns were added with NOT NULL + default: the revert is automatic; note any data migration that should NOT be reverted.
3. **Cache/state cleanup**: list Redis keys, in-memory caches, or external state to invalidate. Examples: token deny-list entries, OAuth state-store entries, password-breach cache.
4. **External provider state**: list any OAuth registrations, third-party webhooks, or external dependencies created by this change that need teardown.
5. **Verification**: command(s) to confirm rollback succeeded (smoke test endpoint, healthcheck URL, log line to look for).

#### 12.3 Estimated rollback time

SLA estimate broken down by happy-path vs migration-back. Example:

- Happy path (revert only): ~2 minutes (CI + deploy).
- Migration `down` required: +8 minutes (manual DB ops + verification).

#### 12.4 Known risks of rollback

If rollback itself has risks (loses customer data, leaves clients in inconsistent state, breaks a downstream integration that has already started consuming the new shape), state them. Otherwise write **"None"** explicitly — absence of this sub-section is ambiguous; the explicit "None" is the signal.

#### When to omit this section

- Docs-only commits (no production code change).
- Test-only commits (no runtime effect).

For ANY commit touching `workflow-standards.mdc §15.1` paths (AUTH domain), §12 is MANDATORY and the §15.3.3 review path applies.

## Part 7: Transition Jira ticket to Done (workflow-standards §20 — MANDATORY)

Added in `/update-docs` v2.0.0 (<TICKET-ID>). Codifies `cross-cutting-policies.mdc §3 Done-not-Closed`: AI-driven workflows terminate at Jira `Done`; `Closed` is operator-only.

### Steps

26. **Fetch transitions** for the ticket:

    ```bash
    curl -s -u "$JIRA_EMAIL:$JIRA_TOKEN" \
      "$JIRA_BASE_URL/rest/api/3/issue/<TICKET>/transitions"
    ```

27. **Pick the transition** whose `to.name == "Done"`. **NEVER** pick a transition mapping to `Closed`, `Cancelled`, `Won't Do`, or any other non-Done terminal (per §20.4 forbidden transitions).

28. **POST the transition**:

    ```bash
    curl -s -u "$JIRA_EMAIL:$JIRA_TOKEN" -X POST \
      -H "Content-Type: application/json" \
      --data '{"transition": {"id": "<found-id>"}}' \
      "$JIRA_BASE_URL/rest/api/3/issue/<TICKET>/transitions"
    ```

29. **Failure is non-fatal**: if the REST call returns non-2xx, log to stderr + continue. The state-machine `documented` advance still proceeds. Operator may transition manually as a fallback (UI or `gh`/`curl` re-run). Failure modes that should NOT block: network outage on Jira, transient 502, JIRA_TOKEN expired (operator-side concern).

### Skip conditions

- **Dry-run / description-only mode**: same skip rule as Part 6.
- **JIRA_BASE_URL or JIRA_TOKEN missing in env**: log warning + skip. Without credentials we cannot transition; operator handles manually.

### Report in final summary

```
## Jira transition
- Target: Done
- Result: success | failed (non-fatal: <reason>) | skipped (no credentials)
```

## Closing: Advance State (FW-004 — MANDATORY)

After Parts 1-7 are complete (record written + integration-state updated + tech docs updated + Jira updated + deviations resolved + ai-specs commit pushed + Jira transitioned to Done), record completion in the lifecycle state file:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    advance update-docs <TICKET> <MODULE> \
    --field record_path=".lifecycle/artifacts/<MODULE>/records/<sprint>/<TICKET>_<scope>.md" \
    --field record_schema_validated=true \
    --field ai_specs_commit=<sha> \
    --field specs_updated="[integration-state.md, api-spec.yml]"
```

`record_schema_validated=true` is the agent's assertion that `/validate-artifact <record>` returned exit 0. This is the final advance for the ticket lifecycle — the state file now reads `state: documented`. Optionally the user can later mark `state: closed` once all follow-up tickets land.

# Boundaries
- **Do NOT modify the original plan** in `changes/[module]/plans/Sprint [N]/` — plans are frozen after development starts
- Records should be **concise** — do not repeat the plan content, only document deltas and outcomes
- If the implementation deviated from the plan, the **Jira ticket** must be updated to reflect the actual state
- All content must be written in **English**

# References

- `forge/specs/documentation-standards.mdc`: Documentation conventions
- `forge/specs/base-standards.mdc`: Core development rules
- `forge/specs/workflow-standards.mdc`: JIT planning, sequential tickets, integration integrity
- `forge/specs/integration-state.md`: Living module dependency map (MUST be updated)
- `README.md`: Changes Directory Convention
