---
version: 1.2.2
category: lifecycle
user-invocable: false  # <TICKET-ID>: internal phase playbook executed via /lifecycle interrupts.
description: "Implement the plan on a feature branch; report plan compliance."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Executor of a frozen plan on a feature branch. Backend (NestJS) and frontend (Next.js 14) scopes; reports plan compliance.

# Goal

Implement the ticket following its plan, with automatic scope detection.

# Arguments

$ARGUMENTS

# Process

## Pre-flight: State Machine Guard (FW-004 — MANDATORY)

Before any work, verify lifecycle prerequisites via the state machine. Enforced by code (`state-machine.py`), not interpretation.

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    check develop <TICKET> <MODULE>
```

- **rc=0** → proceed to Step 0 (scope detection).
- **rc=1** → REFUSE: either `steps.plan.done != true` OR `steps.plan.schema_validated != true`. Run `/plan <TICKET>` first and ensure the plan validates against `plan.schema.yml`.
- **rc=2** → state file missing. Run `/enrich-us` then `/plan` first.

## Step 0: Scope Detection (MANDATORY)

1. Read the Jira ticket via MCP (summary, description, labels, components).
2. Determine scope using these signals:
   - Ticket mentions "API", "endpoint", "service", "guard", "Prisma", "NestJS", "middleware", "DTO" → **backend**
   - Ticket mentions "UI", "component", "page", "Figma", "dashboard", "Next.js", "TailwindCSS", "route" → **frontend**
   - Ticket mentions both backend and frontend work → **fullstack**
   - If ambiguous, ask the user.
3. Announce the detected scope before proceeding: `Detected scope: [backend|frontend|fullstack]`

---

## Backend Process (scope = backend or fullstack)

### Workspace Context
Read the ticket and identify the work surface via the WorkRequest `workspace` context (mechanically injected per framework release layer). Product-specific architecture (monolith vs satellite, framework choice, data-access pattern) is declared in `<workspace.custom_standards.backend>`. Adapt the implementation flow to whatever architecture pattern that file documents.

### Steps

1. Understand the problem described in the ticket
2. Search the codebase for relevant files. Reference `<workspace.data_model_path>` for entity definitions, `<workspace.api_spec_path>` for API endpoints, and `<workspace.custom_standards.backend>` for coding standards + architectural patterns.
3. **Pre-Implementation Integrity Check (MANDATORY)** — Before writing ANY code:
   a. Read `forge/specs/integration-state.md` to understand current module dependencies, guard chains, and service injections.
   b. Verify the implementation plan (in `.lifecycle/artifacts/[module]/plans/Sprint [N]/`) against the ACTUAL codebase state. Determine the ticket's sprint from Jira and derive the module from the code path being modified (e.g., from `<workspace.backend_root>/{module}/`) to locate the correct subfolder. If signatures or dependency chains have changed since the plan was written, note the discrepancies and adapt.
   c. For any controller that will use `@UseGuards()`, verify ALL guard constructor dependencies using the Guard Dependency Map in `integration-state.md`. Ensure the module imports all required dependency modules (e.g., `AuditModule` for `RolesGuard`).
   d. For any new module, list ALL imports needed (including transitive dependencies from guards).
   e. If this ticket is part of a sequence (e.g., layers 1→8), confirm the previous ticket is fully implemented, tested, and committed before proceeding (see `forge/specs/workflow-standards.mdc`).
   f. **Regression Impact Review (MANDATORY)** — Read the plan's "Regression Impact Analysis" section (added by `/plan` Step 4). This section lists:
      - All files in the blast radius (files that import/reference classes being modified)
      - Breaking changes identified (constructor/method/export signature changes)
      - Test files requiring mock updates
      - API contract impact (if endpoints change)
      Use this as a mandatory checklist during implementation. Every file listed in "Test files requiring updates" MUST be updated before the ticket is considered complete.
   g. **Audit remediation tickets** (title contains "Audit Fix" or parent is an audit report ticket): Read the Jira ticket's "Instances to Fix" table (added by `/enrich-us`). This table is the acceptance criteria — treat each row as a checklist item. During implementation, work through EVERY row sequentially and fix it. After fixing all rows, re-grep using the "Grep pattern used" field from the same table to confirm 0 remaining instances. If the table doesn't exist, grep the codebase yourself to enumerate all instances before starting.
4. **Create a feature branch from latest `main` (MANDATORY)**:
   a. `git checkout main && git pull origin main` — ensure you start from the latest main.
   b. `git checkout -b feature/[ticket-id]-backend` (e.g., `feature/<TICKET-ID>-backend`).
   c. **NEVER branch from another feature branch.** If you are currently on a feature branch, switch to `main` first.
   d. If the branch already exists, verify it was created from latest `main`. If not, delete it and recreate.
5. Implement the necessary changes to solve the ticket, following the order of the different tasks and making sure you accomplish all of them in order, like writing and running tests to verify the solution, updating documentation, etc.
6. Ensure code passes linting and type checking
7. If working on a satellite/external-integration, ensure the auth + data-fetching integration with the core product is implemented per `<workspace.custom_standards.backend>` conventions. Test that the satellite correctly handles core-product API errors (per product's error-handling contract).
8. **Post-Implementation Integrity Check (MANDATORY)** — Before committing:
   a. `nest build` must compile clean (catches DI type errors).
   b. `jest --maxWorkers=1 --forceExit` must pass ALL test suites (catches mock mismatches).
   c. Backend startup test: `nest start` must not crash with dependency resolution errors.
   d. Update `forge/specs/integration-state.md` with any new modules, guards, services, or cross-module dependencies added by this ticket.
   e. **Regression verification (MANDATORY)**:
      - **Blast radius test files**: For every test file listed in the plan's "Regression Impact Analysis → Test files requiring updates", verify it was updated and passes. If any test file was missed, update it now.
      - **Import integrity**: For every file in the blast radius that imports from modified classes, verify the import still resolves (no removed exports, no changed signatures without consumer updates).
      - **API contract check**: If any endpoint was modified (route, method, DTO, guards, response), run `/check-api-contract` mentally or via the command and verify `api-spec.yml` was updated. If not → flag as Scope-Gap.
      - **Mock propagation audit**: Grep for all test files that reference each modified class name. Verify every one has updated mocks matching the current signature. Pattern (adapt to product): `grep -r "ClassName" --include="*.<test-ext>" <workspace.backend_root>/`
   f. **Audit remediation tickets**: Re-grep the source directories for the original problem pattern (from the Jira ticket's "Grep pattern used" field). If grep returns >0 matches, you have missed instances — fix them before proceeding. Document the grep result: `Audit check [Check-ID] verified: grep '<pattern>' → 0 matches in src/`
9. **Plan Compliance Tracking (MANDATORY)** — After implementation, before handing off:
   a. Read the original plan from `.lifecycle/artifacts/[module]/plans/Sprint [N]/`.
   b. For each step in the plan, verify whether it was implemented, deviated, or skipped.
   c. Generate a brief Plan Compliance Summary and present it to the user:
   ```
   ## Plan Compliance Summary
   | Step | Description | Status | Notes |
   |------|-------------|--------|-------|
   | 1 | Create DTO | DONE | — |
   | 2 | Create Service | DONE-DEVIATED | Used different approach (see below) |
   | 3 | Write tests | PARTIAL | 2/3 files tested |
   ```
   d. For any DONE-DEVIATED, PARTIAL, or SKIPPED steps, briefly note the reason.
   e. Deviation classification is NOT done in this phase — `develop` reports the facts; the verify phase classifies them.
   f. Emit the Plan Compliance Summary as the develop output.
10. Stage only the files affected by the ticket, and leave any other file changed out of the commit. `develop` does not commit; committing is a downstream phase.
    - **NEVER commit fixes for other tickets on this feature branch.** If you discover pre-existing bugs or test failures from previous tickets, they must be fixed on a separate branch from main (e.g., `fix/SCRUM-XX-description`), merged to main first, then this branch rebased on the updated main.
11. `develop` does not push or open a PR — that is a downstream phase's responsibility.

The `develop` phase emits its structured state (`steps.develop.done == true` + the branch + Plan Compliance Summary) via the Closing Advance-State; routing to the next phase is decided by the orchestrator (or, for manual invocation, gated by `state-machine.py`).

---

## Frontend Process (scope = frontend or fullstack)

### Workspace Awareness

Before starting implementation, determine the work surface via `<workspace.*>`:

- **Core-product frontend module**: You are adding pages/components to the governed frontend at `<workspace.frontend_root>`. Follow the project structure declared in `<workspace.custom_standards.frontend>`. Reference `<workspace.data_model_path>` + `<workspace.api_spec_path>`. Use the existing client/state-management/route-guard patterns documented in the frontend standards spec.
- **Satellite frontend app**: You are building an independent frontend that integrates with the core product. Implement auth + API client integration per the product's auth contract (declared in custom_standards). Reuse theming/UI conventions per product standards.

### Steps

1. **Create a feature branch from latest `main` (MANDATORY)**:
   - `git checkout main && git pull origin main`
   - `git checkout -b feature/[ticket-id]-frontend` (e.g., `feature/<TICKET-ID>-frontend`)
   - **NEVER branch from another feature branch.** If you are currently on a feature branch, switch to `main` first.
2. Analyze the Figma design from the provided Figma URL using the MCP, and the ticket specs.
3. Consider the workspace context per `<workspace.custom_standards.frontend>` (see Workspace Awareness above). Generate a short implementation plan including:
   - Component tree (from atoms → molecules → organisms → page)
   - File/folder structure
4. Then **write the code** for:
   - React components
   - Styles (following project styling conventions: Tailwind, CSS Modules, Styled Components, etc.)
   - Reusable UI elements (buttons, inputs, cards, modals, etc.)
   - Avoid redundant filterDate
5. **Commit hygiene**: Stage only the files affected by this ticket. **NEVER commit fixes for other tickets on this feature branch.** If you discover pre-existing bugs or test failures from previous tickets, they must be fixed on a separate branch from main (e.g., `fix/SCRUM-XX-description`), merged to main first, then this branch rebased on the updated main.

### Libraries

⚠️ Do **NOT** introduce new dependencies unless:
- It is strictly necessary for the UI implementation, and
- You justify the installation in a one-sentence explanation
- Ensure that the interface meets the product requirements.

If the project already has a UI library (e.g., Shadcn, Radix, Material UI, Bootstrap), check the available components **before** writing new ones.

### Architecture & best practices

- Use component-driven architecture (Atomic Design or similar)
- Extract shared/reusable UI elements into a `/shared` or `/ui` folder when appropriate
- Maintain clean separation between **layout components** and **UI components**

---

## Fullstack Process (scope = fullstack)

When scope = fullstack:
1. Run **Backend Process** first (steps 1-10)
2. Then run **Frontend Process** (steps 2-5) on the **SAME feature branch**
   - Branch name: `feature/[ticket-id]-fullstack` (e.g., `feature/<TICKET-ID>-fullstack`)
3. Single commit covering both backend and frontend changes
4. Single PR

---

## Feedback Loop

When receiving user feedback or corrections:

1. **Understand the feedback**: Carefully review and internalize the user's input, identifying any misunderstandings, preferences, or knowledge gaps.

2. **Extract learnings**: Determine what specific insights, patterns, or best practices were revealed. Consider if existing rules need clarification or if new conventions should be documented.

3. **Review relevant rules**: Check the engineering standards (`forge/specs/*-standards.mdc`) to identify which rules relate to the feedback and could be improved.

4. **Propose rule updates** (if applicable):
   - Clearly state which rule(s) should be updated
   - Quote the specific sections that would change
   - Present the exact proposed changes
   - Explain why the change is needed and how it addresses the feedback
   - For foundational rules, briefly assess potential impacts on related rules or documents
   - **Explicitly state: "I will await your review and approval before making any changes to the rule(s)."**

5. **Await approval**: Do NOT modify any rule files until the user explicitly approves the proposed changes.

6. **Apply approved changes**: Once approved, update the rule file(s) exactly as agreed and confirm completion.

## Closing: Advance State (FW-004 — MANDATORY)

After the feature branch is created, code implemented, build/tests passing, and the Plan Compliance Summary produced, record completion:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    advance develop <TICKET> <MODULE> \
    --field branch="feature/<TICKET>-<scope>" \
    --field last_commit=<sha>
```

Optionally pass `--field plan_compliance_summary=...` if your runtime supports complex YAML values; otherwise edit `state.yml` manually for that field. `/verify` refuses unless `steps.develop.done == true`.

# References

- `lifecycle/specs/backend-standards.mdc`: NestJS architecture, SOLID, testing, security
- `lifecycle/specs/frontend-standards.mdc`: Next.js 14, TailwindCSS, component patterns
- `forge/specs/workflow-standards.mdc`: JIT planning, sequential tickets, integration integrity
- `forge/specs/integration-state.md`: Living module dependency map
- `forge/specs/data-model.md`: Entity definitions
- `forge/specs/api-spec.yml`: API endpoints
- `forge/specs/ui-design-system.md`: Visual design source of truth
