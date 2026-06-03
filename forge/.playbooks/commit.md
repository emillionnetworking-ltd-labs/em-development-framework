---
version: 1.2.2
category: lifecycle
user-invocable: false  # <TICKET-ID>: internal phase playbook executed via /lifecycle interrupts.
description: "Commit, merge to main, and clean up the feature branch."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Producer of clean commits + PRs aligned with project standards.

# Goal

1. Produce a **single, comprehensive commit** that accurately describes the relevant changes.
2. **Push** the branch and **create (or update) a Pull Request** for review.
3. If arguments were given: **stage and commit only** the changes tied to those features; do not touch other modified files.

# Arguments

**Optional.** `$ARGUMENTS` may contain:

- **Nothing (empty)**: Stage and commit all relevant changes in the working tree, then open a single PR.
- **Feature/ticket identifiers**: e.g. ticket IDs (e.g. `<TICKET-ID>`), branch names, or short feature labels. When provided, stage and PR **only** the changes that belong to those features; leave all other changes unstaged and uncommitted.
- **Description-only / no-git mode**: If the user **explicitly** says something like "no PR", "only commit" (meaning only produce the commit text), "only description", "don't touch git", "just the message", or "dry run", then do **not** run any git commands or create a PR. Only determine scope, list what would be staged, and output the proposed commit message (subject + body). The user can copy and run git commands themselves.

# Process

## Pre-flight: State Machine Guard (FW-004 — MANDATORY)

Before ANY work — including description-only mode — verify the lifecycle state. The gate is enforced by code; description-only mode does NOT bypass it.

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    check commit <TICKET> <MODULE>
```

- **rc=0** → proceed to step 0 (description-only check).
- **rc=1** → REFUSE: one of (a) `steps.verify.done != true`, (b) `steps.verify.schema_validated != true`, (c) `verify.verdict` is `BLOCKED-RISK`, `BLOCKED-GAP`, or `BLOCKED-BUILD`. Surface stderr verbatim — the user must address the blocker before committing. Do not "skip verification" creatively.
- **rc=2** → state file missing. Backtrack to `/enrich-us`.

This is the gate that converts the historical "Verification Gate Check" rule (Step 1) from advisory into mechanical.

## 0. Description-only / no-git mode (check first)

If the user **explicitly** requested no git operations (e.g. "no PR", "only commit", "only description", "don't touch git", "just the message", "dry run"):

- Perform **only** steps 2–4: inspect state, resolve scope (which files/hunks would be staged), and write the full commit message (subject + body).
- **Do not** run `git add`, `git commit`, `git push`, or `gh pr create`. Do not modify the repository in any way.
- Output for the user:
  1. List of files (and hunks, if partial) that would be staged.
  2. The proposed commit message in a copy-pasteable block.
- Then stop; skip steps 5, 6, 7, and 8.

## 1. Verification Gate Check (MANDATORY)

Before proceeding with any git operations, check if a verification report exists:

1. Determine the ticket ID from `$ARGUMENTS` or the current branch name (e.g., `feature/<TICKET-ID>-backend` → `<TICKET-ID>`).
2. Look for a verification report at `.lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_verify.md` (derive module from the code path modified, e.g., from `<workspace.backend_root>/{module}/` per WorkRequest workspace context).
3. **If the report exists**:
   a. Read it and check the verdict (the structured output of verify).
   b. Verdict **PASS** / **PASS-WITH-DEBT** → commit is eligible; proceed to step 2.
   c. Verdict **BLOCKED-RISK** / **BLOCKED-GAP** / **BLOCKED-BUILD** → commit is NOT eligible; do not commit. (`state-machine.py` enforces this gate; routing back to fix the blocker is the orchestrator's / operator's job.)
4. **If no report exists**: verify has not run, so the verdict gate is unmet — commit is not eligible. The state-machine refuses `commit` until `steps.verify.done` + a non-blocking verdict.

## 1b. Audit Fix Validation (MANDATORY for audit remediation tickets)

If the ticket originates from an audit finding (title contains "Audit Fix", or parent is an audit report ticket):

1. **Read the verification report** (`_verify.md`) — it MUST contain an "## Audit Finding Resolution" section (added by `/verify` Step 4e). If this section is missing, STOP: "Verification report is missing the Audit Finding Resolution section. Run `/verify [TICKET-ID]` first."
2. **Confirm 0 UNRESOLVED instances** in the resolution table. If any instance is UNRESOLVED, STOP: "Verification report shows UNRESOLVED audit instances. Run `/verify [TICKET-ID]` and fix all instances before committing."
3. **Obtain the grep pattern** from one of these sources (in priority order):
   a. The **"Grep pattern used"** field in the verification report's Audit Finding Resolution section
   b. The **"Grep pattern used"** field in the Jira ticket's "Instances to Fix" section (added by `/enrich-us` Step 3)
   c. If neither exists, derive the pattern from the audit finding description and document it
4. **Run a final grep** using that exact pattern against the source directories (`<workspace.backend_root>/` and/or `<workspace.frontend_root>/`, excluding vendored deps + build output + test files per product convention). This is the last defense — if grep finds instances that the verify report missed, STOP and report them.
5. **Document the grep result** in the commit body: `Audit grep: <pattern> → 0 matches in src/`

**Why this step exists**: This is the final gate that prevents a ticket from being marked Done while the underlying problem still exists in code. The grep must return 0 matches for the specific pattern that the audit flagged.

## 2. Inspect current state

- Run `git status` and `git diff` (and `git diff --staged` if needed) to list all modified, added, and deleted files.
- Identify the current branch. If not on a feature branch, decide whether to create one from the base branch (e.g. `main` or `develop`) before committing.

## 3. Resolve scope: full commit vs feature-scoped commit

- **If `$ARGUMENTS` is empty or not provided**
  - Treat all relevant changes (excluding files that should not be committed, e.g. `.env`, build artifacts, local config) as the scope for this commit.
  - Stage all of those and proceed to step 4.

- **If `$ARGUMENTS` is provided (e.g. ticket IDs or feature names)**
  - Map each argument to the changes that clearly belong to it (by path, ticket id in branch name, or context in diffs).
  - Stage **only** the files/hunks that belong to those features.
  - Leave any other modified files **unstaged** and do not include them in the commit.
  - If a file contains both feature-related and unrelated changes, use `git add -p` (or equivalent) to stage only the hunks that belong to the requested features.
  - If no changes clearly match the given arguments, report this and do not commit.

## 4. Commit message

- Write the commit message **in English** (per `forge/specs/base-standards.mdc`).
- Make it **descriptive** (per Git Workflow in `backend-standards.mdc` and `frontend-standards.mdc`).
- Structure it so that:
  - **Subject line**: Short, imperative summary (e.g. "Add candidate filters to position list", "Fix validation for application deadline"). Optionally prefix with a scope or ticket id (e.g. `<TICKET-ID>: Add candidate filters`).
  - **Body** (if needed): Bullet points or short paragraphs describing what changed and why (areas touched, new behavior, fixes). Reference ticket IDs here if they apply.
- Do not commit secrets, `.env`, or other sensitive or generated artifacts.

## 5. Commit and push

- Create the commit with the message from step 4.
- Push the current branch to the remote (`git push origin <branch>`). If the branch does not exist on the remote, push with `-u` to set upstream.

## 6. Pull Request

- Use the **GitHub CLI (`gh`)** for all GitHub operations (per `develop.md`).
- Create or update the PR for the current branch:
  - **Title**: Clear, aligned with the commit (e.g. include ticket ID if applicable: `[<TICKET-ID>] Add candidate filters to position list`).
  - **Description**: Summarize the change set, link to the ticket if relevant, and note any testing or follow-ups. If a verification report exists, reference its verdict.
- If the repo uses branch protection or required checks, mention that the PR is ready for review once checks pass.

## 7. Merge to main and cleanup (MANDATORY)

After the PR is created and the build/tests have already passed (verified in `/develop`):

1. **Switch to main and pull latest**: `git checkout main && git pull origin main`
2. **Merge the feature branch**: `git merge <feature-branch>` (should be fast-forward or clean merge since it branched from latest main).
   Alternative for squash-merge via PR: `gh pr merge <PR#> --squash --delete-branch` (always pass `--delete-branch`).
3. **Push main**: `git push origin main` (skip if `gh pr merge` was used — it pushes the squashed commit on main automatically).
4. **Delete local feature branch**: `git branch -d <feature-branch>`
5. **Delete remote feature branch**: `git push origin --delete <feature-branch>` (skip if `gh pr merge --delete-branch` was used).
6. **Verify cleanup actually happened** (MANDATORY). Two checks:
   ```bash
   # 6a. Local: only main remains
   git branch
   # Expected output: * main  (and only main)

   # 6b. Remote: feature branch is gone (HTTP 404 expected)
   gh api "repos/{owner}/{repo}/branches/<feature-branch>" 2>&1 | grep -q "404"
   if [ $? -ne 0 ]; then
     echo "WARN: remote branch still exists, force-deleting"
     gh api -X DELETE "repos/{owner}/{repo}/git/refs/heads/<feature-branch>"
   fi
   ```
   If repo setting `delete_branch_on_merge=true` is enabled (per `workflow-standards.mdc` §2 Required Repository Configuration A), GitHub itself auto-deletes on merge — this verification will always confirm 404. The verification still runs as belt-and-suspenders defence: if the setting is ever disabled, this step catches the orphan immediately.

**Why this is mandatory**: Without this step, feature branches accumulate, `main` becomes stale, and subsequent tickets branch from outdated code — leading to massive merge conflicts and divergent code. The <TICKET-ID> incident (2026-03-11 → 2026-05-08, 25 stale branches accumulated) is the case study referenced in `workflow-standards.mdc` §2.

**If merge to main has conflicts**: This should NOT happen if the branch was created from latest main (as required by `/develop`). If it does happen, it means another change was pushed to main while this ticket was being worked on. Resolve conflicts, verify build still passes, then complete the merge.

## 8. Summary for the user

- Report what was committed (files and scope).
- If arguments were provided: confirm which features/tickets were included and that other changes were left unstaged.
- Provide the PR URL (from `gh` output).
- **Confirm**: merged to main, feature branch deleted (local + remote), currently on `main`.
- **Verification status**: Report whether `/verify` was run and its verdict (PASS / PASS-WITH-DEBT / skipped).

## Closing: Advance State (FW-004 — MANDATORY)

After the PR has been merged to main and the feature branch deleted (local + remote), record completion:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    advance commit <TICKET> <MODULE> \
    --field pr=<PR-number> \
    --field merge_commit=<sha> \
    --field branch_deleted=true
```

`/update-docs` refuses unless `steps.commit.done == true`. In description-only mode (no actual git operations), do NOT advance — the work isn't done; advancing would lie to the state machine.

# References

- `forge/specs/base-standards.mdc`: English-only for commit messages and technical artifacts.
- `lifecycle/specs/backend-standards.mdc` and `lifecycle/specs/frontend-standards.mdc`: Git Workflow (feature branches, descriptive commits, small focused branches).
- `forge/.playbooks/develop.md`: Development process and branch creation.
- `forge/.playbooks/verify.md`: Pre-merge quality gate (must pass before committing).

# Notes

- **Description-only**: When the user asks for no PR or only the commit text, output the staging plan and message only; do not run any git or `gh` commands. Step 7 (merge + cleanup) is also skipped in this mode.
- Do not run destructive git commands (e.g. `git push --force` without explicit user request).
- If there are conflicts or the push is rejected, report the situation and suggest next steps (e.g. pull/rebase then push), but do not force-push unless the user asks.
- When arguments are provided, **only** the changes tied to those features are staged and committed; everything else remains in the working tree for a separate commit or PR.
- **After completing all steps, you must be on `main`** with the feature branch fully deleted. This ensures the next ticket starts from a clean, up-to-date main.
