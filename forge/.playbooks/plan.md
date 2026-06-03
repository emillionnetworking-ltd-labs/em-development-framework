---
version: 1.3.2
category: lifecycle
user-invocable: false  # <TICKET-ID>: internal phase playbook executed via /lifecycle interrupts.
description: "Produce a schema-validated implementation plan from an enriched ticket."
last_changed: 2026-05-30
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Role

Author of the implementation plan from an enriched ticket. NestJS + Next.js 14 modular architecture awareness.

# Goal

Create a detailed implementation plan for a Jira ticket, with automatic scope detection.

# Arguments

$ARGUMENTS

# Process

## Pre-flight: State Machine Guard (FW-004 — MANDATORY)

Before any work, verify lifecycle prerequisites via the state machine. Enforced by code (`state-machine.py`), not by your interpretation.

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    check plan <TICKET> <MODULE>
```

- **rc=0** → proceed to Step 0 (scope detection).
- **rc=1** → REFUSE: `steps.enrich-us.done` is not `true`. Run `/enrich-us <TICKET>` first.
- **rc=2** → state file missing. Run `/enrich-us <TICKET>` first.

`<MODULE>` derivation: from the ticket's code path. Framework-reinforcement tickets → `framework`. Unclear → `backlog`.

## Step 0: Scope Detection (MANDATORY)

1. Read the Jira ticket via MCP (summary, description, labels, components).
2. Determine scope using these signals:
   - Ticket mentions "API", "endpoint", "service", "guard", "Prisma", "NestJS", "middleware", "DTO" → **backend**
   - Ticket mentions "UI", "component", "page", "Figma", "dashboard", "Next.js", "TailwindCSS", "route" → **frontend**
   - Ticket mentions both backend and frontend work → **fullstack**
   - If ambiguous, ask the user.
3. Announce the detected scope before proceeding: `Detected scope: [backend|frontend|fullstack]`

## Backend Planning (scope = backend or fullstack)

1. Adopt the role of `forge/.agents/backend-developer.md`
2. Analyze the Jira ticket using the MCP. If the mention is a local file, then avoid using MCP
3. **Codebase State Verification (MANDATORY)** — Before writing ANY plan:
   a. Read `forge/specs/integration-state.md` to understand current module dependencies, guard chains, and service injections.
   b. **READ the ACTUAL source files** that will be affected (controllers, modules, guards, services). Do NOT rely on `integration-state.md` alone, enrichment documents, previous plans, or conversation memory for codebase state. These sources may describe a planned or future state that hasn't been implemented yet.
   c. For every service/class this plan will modify, **READ its constructor** and record the exact current dependencies (name, count, order). If the plan says "add as Nth constructor dep", N must match reality.
   d. For every method the plan references (e.g., "add deny call in `logoutAll()`"), **verify the method exists** in the current code. If it doesn't, remove it from the plan.
   e. For any controller that will use `@UseGuards()`, verify ALL guard constructor dependencies using the Guard Dependency Map in `integration-state.md` cross-referenced with live code.
   f. For any new module, list ALL imports needed (including transitive dependencies from guards — e.g., if using `RolesGuard`, the module must import `AuditModule`).
   g. Record the verified codebase state in the plan header (see "Codebase State Snapshot" in template). Every claim in the plan (dependency counts, method names, line numbers) must trace back to a file that was actually read.
   h. If this ticket is part of a sequence (e.g., layers 1→8), confirm the previous ticket is fully implemented and committed before proceeding (see `forge/specs/workflow-standards.mdc`).
4. **Regression Impact Analysis (MANDATORY)** — Before writing the plan steps:
   a. **Blast radius mapping**: For every file/class this ticket will modify, grep for all files that import or reference it. Document the full dependency tree:
      - Which modules import from modified modules?
      - Which services inject modified services?
      - Which controllers use modified guards/interceptors?
      - Which test files mock modified classes? (grep `--include="*.spec.ts"` for class names)
   b. **Breaking change detection**: For each class/function being modified, check if the change alters:
      - Constructor signatures (adding/removing/reordering parameters)
      - Method signatures (changing params, return types, or removing methods)
      - Module exports (removing or renaming exported providers)
      - DTO structures (adding required fields, removing fields, changing types)
      - Guard behavior (changing what roles/permissions are checked)
   c. **API contract impact**: If any endpoint is modified, check `forge/specs/api-spec.yml` and flag:
      - Request body schema changes → frontend must adapt
      - Response schema changes → frontend must adapt
      - New/changed auth requirements → frontend auth flow may break
      - Removed/renamed endpoints → frontend will get 404s
   d. **Schema migration impact**: If Prisma schema changes:
      - New non-nullable fields without defaults → existing data migration required
      - Removed fields → verify no code references remain
      - Renamed fields → all query references must update
      - Relation changes → cascading effects on related queries
   e. **Test impact assessment**: List ALL existing test files that will need updates due to:
      - Modified constructor signatures (new mock providers needed)
      - Changed method return values (mock return values need updating)
      - New guard dependencies (test modules need new imports)
   f. **Document the blast radius** in the plan's "Regression Impact Analysis" section (see template below). If blast radius > 5 files, flag for extra review attention.
5. **CI Gate Anticipation (MANDATORY)** — Codified by <TICKET-ID> after the two consecutive one-shot CI green pushes (<TICKET-ID> + <TICKET-ID>) confirmed the pattern.

   Before writing implementation steps, explicitly list every CI gate this ticket will affect and state the expected behavior per gate:

   | CI gate                                       | Expected behavior                                |
   |-----------------------------------------------|--------------------------------------------------|
   | Job 1: `py_compile (all tools)`               | PASS / unchanged                                  |
   | Job 2: `Schema validate (changed artifacts)`  | PASS / new SCHEMA_BY_PATH rule / new SKIP_PATHS  |
   | Job 2: `Groundedness (warn-only)`             | PASS / warns / unchanged                          |
   | Job 2: `Audit: coupling check (warn-only)`    | PASS / new violation / unchanged                  |
   | Job 2: `Audit: completion check (warn-only)`  | SKIP / per-folder / unchanged                     |
   | Job 3: `Schema validate (historical)`         | SKIP / conditional on schemas/                    |
   | Job 4: `Smoke test: state-machine.py`         | PASS / unchanged                                  |
   | Job 5: `pytest (linchpin tests)`              | PASS / N new tests / N existing-tests-modified    |

   Plus SKIP_PATHS / SCHEMA_BY_PATH expectations: list every NEW `.md` or `.yml` file this ticket will create under `.lifecycle/artifacts/**` or `forge/registers/**` AND confirm each has either (a) `schema:` frontmatter, (b) matching SCHEMA_BY_PATH rule, or (c) matching SKIP_PATHS rule. Files lacking any of these will fail Job 2 schema-validate with "Could not determine which schema to apply".

   **Why this rule exists**: <TICKET-ID>/481/482 each shipped with an in-PR CI fix iteration because schema-validate routing wasn't anticipated at plan time. <TICKET-ID> + 484 anticipated correctly and landed one-shot CI green. This rule promotes that discipline from happy-accident to enforceable plan-time gate.

   **Rule application**: include the table verbatim in the plan's §1 (Codebase State Snapshot) "Plan-time decisions" subsection. If the plan cannot fill the table accurately, the plan is incomplete — `steps.plan.schema_validated` must not be asserted.
6. Propose a step-by-step plan for the backend part, taking into account everything mentioned in the ticket and applying the project's best practices and rules you can find in `/forge/specs` (including `workflow-standards.mdc` for integration integrity and sequential ticket rules).
7. Apply the best practices of your role to ensure the developer can be fully autonomous and implement the ticket end-to-end using only your plan.
8. Do not write code yet; provide only the plan in the output format defined below.
9. `plan` produces the plan only — it does not write code. Implementation (branch creation + code) is the develop phase's concern, not this one.

## Frontend Planning (scope = frontend or fullstack)

1. Adopt the role of `forge/.agents/frontend-developer.md`
2. Analyze the Jira ticket using the MCP. If the mention is a local file, then avoid using MCP
3. Propose a step-by-step plan for the frontend part, taking into account everything mentioned in the ticket and applying the project's best practices and rules you can find in `/forge/specs`.
4. Apply the best practices of your role to ensure the developer can be fully autonomous and implement the ticket end-to-end using only your plan.
5. Do not write code yet; provide only the plan in the output format defined below.
6. `plan` produces the plan only — it does not write code. Implementation (branch creation + code) is the develop phase's concern, not this one.

## Fullstack Planning (scope = fullstack)

When scope = fullstack:
1. Create a single plan file: `SCRUM-XX_fullstack.md`
2. Include both backend sections and frontend sections, clearly separated with `---` dividers
3. Backend section first, then frontend section
4. A shared "Architecture Context" section covers cross-cutting concerns (e.g., API contract between backend and frontend)

# Output format

Markdown document at the path `.lifecycle/artifacts/[module]/plans/Sprint [N]/[jira_id]_[scope].md` containing the complete implementation details.

- **scope** = `backend`, `frontend`, or `fullstack` (auto-detected)
- **module**: Derive from the code path being modified (e.g., from `<workspace.backend_root>/{module}/` per WorkRequest workspace context — the parent agent receives `workspace.backend_root` mechanically post-Wave-31). If no clear module, use `backlog`.
- **Sprint folder**: Before writing the plan, determine which sprint the ticket belongs to by checking its Jira sprint field (via MCP or Agile API). Use that sprint name as the folder (e.g., `internal cycle`, `internal cycle`). If the sprint cannot be determined, ask the user.

Follow the appropriate template below based on scope.

---

## Backend Implementation Plan Template (16 sections)

### 1. **Header**
- Title: `# Backend Implementation Plan: [TICKET-ID] [Feature Name]`

### 2. **Codebase State Snapshot**
- **Date**: YYYY-MM-DD
- **Last completed ticket**: SCRUM-XX (name)
- **Integration state verified**: Yes/No (must be Yes)
- **Files verified against live code**: List every file that was READ from the actual codebase. Every fact in this plan (dependency counts, method names, line references) must trace back to a file listed here. If a file was not read, its internals cannot appear in the plan.
- **Constructor signatures verified**: For each class this plan modifies, list: `ClassName(dep1: Type1, dep2: Type2, ...)` as confirmed from live code. The plan's "add as Nth dep" instructions must match these signatures.
- **Methods verified to exist**: For each method this plan references as an integration point (e.g., "add call in `logoutAll()`"), confirm it exists in live code with file path and line number. If a method does not exist, it MUST NOT appear in the plan.
- **Guard dependency chain verified**: For each `@UseGuards()` in this plan, list the guard → dependency → source module chain
- **Discrepancies with integration-state.md**: List any differences found between `integration-state.md` and live code (if any). This catches documentation drift.

### 3. **Regression Impact Analysis**
- **Blast radius**: List ALL files that import/reference the classes being modified (use grep results as evidence). Categorize as: direct dependents (import the class), transitive dependents (import a module that exports the class), test dependents (mock the class in `.spec.ts` files).
- **Breaking changes identified**: For each modified class, document any signature changes (constructor, methods, exports) and list every file that must be updated as a consequence.
- **API contract impact**: If endpoints change, list the spec vs. code deltas and note frontend impact.
- **Schema migration impact**: If Prisma schema changes, document backward compatibility and data migration needs.
- **Test files requiring updates**: Explicit list of `.spec.ts` files that mock modified classes and need new/updated providers. This list becomes a mandatory checklist during implementation.
- **Blast radius size**: `N files affected` — if >5 files, flag for careful regression testing in `/verify`.

### 4. **Overview**
- Brief description of the feature and architecture principles (NestJS modular architecture, clean code)

### 5. **Architecture Context**
- Modules involved (feature module, shared modules)
- Components affected (controller, service, DTO, guard, strategy)
- Files referenced

### 6. **Implementation Steps**
Detailed steps, typically:

#### **Step 0: Create Feature Branch**
- **Action**: Create and switch to a new feature branch following the development workflow. Check if it exists and if not, create it
- **Branch Naming**: Follow the project's branch naming convention (`feature/[ticket-id]-backend`, make it required to use this naming, don't allow to keep on the general task [ticket-id] if it exists to separate concerns)
- **Implementation Steps**:
  1. Ensure you're on the latest `main` or `develop` branch (or appropriate base branch)
  2. Pull latest changes: `git pull origin [base-branch]`
  3. Create new branch: `git checkout -b [branch-name]`
  4. Verify branch creation: `git branch`
- **Notes**: This must be the FIRST step before any code changes. Refer to `lifecycle/specs/backend-standards.mdc` section "Development Workflow" for specific branch naming conventions and workflow rules.

#### **Step N: [Action Name]**
- **File**: Target file path
- **Action**: What to implement
- **Function Signature**: Code signature
- **Implementation Steps**: Numbered list
- **Dependencies**: Required imports
- **Implementation Notes**: Technical details

Common steps:
- **Step 1**: Create DTO with class-validator decorators
- **Step 2**: Create Service Method (@Injectable, constructor injection)
- **Step 3**: Create Controller Endpoint (@Controller, @Post/@Get, @UseGuards)
- **Step 4**: Register in Module (@Module imports, providers, exports)
- **Step 5**: Write Unit Tests (with subcategories: Successful Cases, Validation Errors, Not Found, Authorization, Server Errors, Edge Cases)

Example of a good structure:
**Implementation Steps**:

1. **Check for existing resource**:
   - Use `this.usersService.findByEmail(dto.email)` to check for duplicates
   - If found, throw `new ConflictException('Email already registered')`
   - Proceed with creation if no conflict

#### **Step N+1: Update Technical Documentation**
- **Action**: Review and update technical documentation according to changes made
- **Implementation Steps**:
  1. **Review Changes**: Analyze all code changes made during implementation
  2. **Identify Documentation Files**: Determine which documentation files need updates based on:
     - Data model changes → Update `forge/specs/data-model.md`
     - API endpoint changes → Update `forge/specs/api-spec.yml`
     - Standards/libraries/config changes → Update relevant `*-standards.mdc` files
     - Architecture changes → Update relevant architecture documentation
  3. **Update Documentation**: For each affected file:
     - Update content in English (as per `documentation-standards.mdc`)
     - Maintain consistency with existing documentation structure
     - Ensure proper formatting
  4. **Verify Documentation**:
     - Confirm all changes are accurately reflected
     - Check that documentation follows established structure
  5. **Report Updates**: Document which files were updated and what changes were made
- **References**:
  - Follow process described in `forge/specs/documentation-standards.mdc`
  - All documentation must be written in English
- **Notes**: This step is MANDATORY before considering the implementation complete. Do not skip documentation updates.

### 7. **Implementation Order**
- Numbered list of steps in sequence (must start with Step 0: Create Feature Branch and end with documentation update step)

### 8. **Testing Checklist**
- Post-implementation verification checklist
- **Regression test checklist**: For each file listed in the Regression Impact Analysis "Test files requiring updates" section, confirm the test file was updated and passes.

### 9. **Error Response Format**
- JSON structure (following HttpExceptionFilter pattern)
- HTTP status code mapping

### 10. **Partial Update Support** (if applicable)
- Behavior for partial updates

### 11. **Dependencies**
- External libraries and tools required

### 12. **Notes**
- Important reminders and constraints
- Business rules
- Language requirements

### 13. **Next Steps After Implementation**
- Post-implementation tasks (documentation is already covered in Step N+1, but may include integration, deployment, etc.)

### 14. **Implementation Verification**
- Final verification checklist:
  - Code Quality
  - Functionality
  - Testing
  - **Regression**: All files in blast radius verified (imports resolve, tests pass, no broken mocks)
  - Integration
  - Documentation updates completed

### 15. **Module-Level Planning** (when ticket involves a complete new module)

Use this section when the ticket creates or significantly modifies a complete internal module within the governed product. Adapt to product conventions declared in `<workspace.custom_standards.backend>`:

- **Module Scope Assessment**: Identify entities affected (reference `<workspace.data_model_path>` if declared).
- **Entity Design**: For new entities, define fields, validation rules, business invariants, relationships.
- **API Surface**: List new/modified endpoints (reference `<workspace.api_spec_path>` if declared). Per endpoint: path, method, guards, request/response schema.
- **Cross-Module Dependencies**: Identify which existing services the module needs to inject. Document the injection chain.
- **Domain Events**: List domain events emitted by this module.
- **Transaction Boundaries**: Identify multi-entity operations requiring transactional atomicity.
- **Module Registration**: If the module needs central registration (e.g. toggle-able per project), document the registration entry.
- **Permissions**: List new permissions/roles to seed (format per product convention).

Product-specific module patterns (entity catalog, service registry, etc.) live in `<workspace.custom_standards.backend>` per-project; this section provides the generic framework discipline.

### 16. **Satellite/External-Integration Planning** (when ticket involves a new satellite app or external service)

Use this section when the ticket creates a new external app/service that integrates with the governed product.

- **Satellite Identity**: Name, purpose, scope. Confirm the integration architecture pattern declared in `<workspace.custom_standards.backend>`.
- **Auth Integration**: Document auth endpoints consumed + token handling (per product auth contract).
- **Data Dependencies**: List API endpoints the satellite consumes (per `<workspace.api_spec_path>`).
- **Satellite's Own Schema**: Document the satellite's own data model. MUST NOT duplicate core entities — reference by ID only.
- **Registry Entry**: Document the satellite's registration in the core product (if applicable per product convention).
- **Integration Error Handling**: Document handling of core-product API failures (401/403/404/5xx retry/circuit-breaker policy).
- **Environment Variables**: API URLs + shared secrets per product conventions.

Product-specific integration patterns live in `<workspace.custom_standards.backend>` per-project.

---

## Frontend Implementation Plan Template (14 sections)

### 1. **Header**
- Title: `# Frontend Implementation Plan: [TICKET-ID] [Feature Name]`

### 2. **Overview**
- Brief description of the feature and frontend architecture principles (Next.js App Router, component-based architecture, TailwindCSS)

### 3. **Architecture Context**
- Components/pages involved
- Files referenced
- Routing considerations (App Router file-system routing)
- State management approach (Context + Reducer, local state)

### 4. **Implementation Steps**
Detailed steps, typically:

#### **Step 0: Create Feature Branch**
- **Action**: Create and switch to a new feature branch following the development workflow. Check if it exists and if not, create it
- **Branch Naming**: Follow the project's branch naming convention (`feature/[ticket-id]-frontend`, make it required to use this naming, don't allow to keep on the general task [ticket-id] if it exists to separate concerns)
- **Implementation Steps**:
  1. Ensure you're on the latest `main` or `develop` branch (or appropriate base branch)
  2. Pull latest changes: `git pull origin [base-branch]`
  3. Create new branch: `git checkout -b [branch-name]`
  4. Verify branch creation: `git branch`
- **Notes**: This must be the FIRST step before any code changes. Refer to `lifecycle/specs/frontend-standards.mdc` section "Development Workflow" for specific branch naming conventions and workflow rules.

#### **Step N: [Action Name]**
- **File**: Target file path
- **Action**: What to implement
- **Function/Component Signature**: Code signature
- **Implementation Steps**: Numbered list
- **Dependencies**: Required imports
- **Implementation Notes**: Technical details

Common steps:
- **Step 1**: Add API methods to ApiClient or create service in `src/lib/`
- **Step 2**: Create/Update Components in `src/components/{category}/`
- **Step 3**: Create App Router page in `src/app/{route}/page.tsx`
- **Step 4**: Write Jest + React Testing Library tests in `tests/`

#### **Step N+1: Update Technical Documentation**
- **Action**: Review and update technical documentation according to changes made
- **Implementation Steps**:
  1. **Review Changes**: Analyze all code changes made during implementation
  2. **Identify Documentation Files**: Determine which documentation files need updates based on:
     - API endpoint changes → Update `forge/specs/api-spec.yml`
     - UI/UX patterns or component patterns → Update `lifecycle/specs/frontend-standards.mdc`
     - Routing changes → Update routing documentation
     - New dependencies or configuration changes → Update `lifecycle/specs/frontend-standards.mdc`
     - Test patterns → Update testing documentation
  3. **Update Documentation**: For each affected file:
     - Update content in English (as per `documentation-standards.mdc`)
     - Maintain consistency with existing documentation structure
     - Ensure proper formatting
  4. **Verify Documentation**:
     - Confirm all changes are accurately reflected
     - Check that documentation follows established structure
  5. **Report Updates**: Document which files were updated and what changes were made
- **References**:
  - Follow process described in `forge/specs/documentation-standards.mdc`
  - All documentation must be written in English
- **Notes**: This step is MANDATORY before considering the implementation complete. Do not skip documentation updates.

### 5. **Implementation Order**
- Numbered list of steps in sequence (must start with Step 0: Create Feature Branch and end with documentation update step)

### 6. **Testing Checklist**
- Post-implementation verification checklist
- Component and integration test coverage
- Component functionality verification
- Error handling verification

### 7. **Error Handling Patterns**
- Error state management in components
- User-friendly error messages
- API error handling via ApiClient

### 8. **UI/UX Considerations** (if applicable)
- TailwindCSS utility classes and theme compliance
- Responsive design considerations
- Accessibility requirements
- Loading states and feedback

### 9. **Dependencies**
- External libraries and tools required
- Custom UI components used (Button, Input, Spinner, etc.)
- Third-party packages (if any)

### 10. **Notes**
- Important reminders and constraints
- Business rules
- Language requirements (English only)

### 11. **Next Steps After Implementation**
- Post-implementation tasks (documentation is already covered in Step N+1, but may include integration, deployment, etc.)

### 12. **Implementation Verification**
- Final verification checklist:
  - Code Quality
  - Functionality
  - Testing
  - Integration
  - Documentation updates completed

### 13. **Module-Level Planning** (when ticket involves a complete new frontend module)

Use this section when the ticket creates or significantly modifies a complete frontend module within the governed product. Adapt to product conventions declared in `<workspace.custom_standards.frontend>`:

- **Module Scope Assessment**: Identify entities the module renders/manages (reference `<workspace.data_model_path>` + `<workspace.api_spec_path>` if declared).
- **Page Structure**: List new pages + routing per the product's frontend framework conventions.
- **Component Tree**: Break down components per product UI conventions (atomic / feature-based / etc. as declared).
- **State Management**: New Context / local state / external store per product convention.
- **API Integration**: List API methods needed (reference `<workspace.api_spec_path>`).
- **Route Guards**: Specify guards per product conventions.
- **Navigation Updates**: Document changes to nav components if applicable.
- **Shared Types**: List shared types/interfaces to add.

Product-specific frontend patterns (component library, theming system, design tokens) live in `<workspace.custom_standards.frontend>` per-project.

### 14. **Satellite-Frontend Planning** (when ticket involves a satellite frontend app)

Use this section when the ticket creates a new satellite frontend application.

- **Satellite Identity**: Name, purpose, target users, framework choice.
- **Auth Integration**: Document the auth flow per the core product's auth contract.
- **Core API Client**: Document the API client + methods per `<workspace.api_spec_path>`.
- **Shared UI Theme**: Document theme/CSS reuse with the core product (variables, accent colors, dark mode strategy) per product conventions.
- **Satellite-Specific Pages**: List the satellite's own pages and routing structure.
- **Environment Configuration**: API URLs + shared config per product conventions.

Product-specific satellite-frontend patterns live in `<workspace.custom_standards.frontend>` per-project.

# Model routing

| Scope | Recommended model | Reason |
|-------|------------------|--------|
| Backend | **Opus** | Deep architectural reasoning, dependency analysis |
| Frontend | Sonnet | Less complex dependency chains |
| Fullstack | **Opus** for backend sections, Sonnet for frontend sections | Cost-effective split |

## Closing: Advance State (FW-004 — MANDATORY)

After the plan file has been written AND has passed `/validate-artifact` against `plan.schema.yml`, record completion in the lifecycle state file:

```bash
python3 ~/projects/em-development-framework/forge/tools/state-machine.py \
    advance plan <TICKET> <MODULE> \
    --field path=".lifecycle/artifacts/<MODULE>/plans/<sprint>/<TICKET>_<scope>.md" \
    --field schema_validated=true
```

`schema_validated=true` is the agent's assertion that `/validate-artifact <plan>` returned exit 0. If validation failed, do NOT advance — fix the plan first. `/develop` refuses unless both `plan.done==true` AND `plan.schema_validated==true`.

# References

- `lifecycle/specs/backend-standards.mdc`: NestJS architecture, SOLID, testing, security
- `lifecycle/specs/frontend-standards.mdc`: Next.js 14, TailwindCSS, component patterns
- `forge/specs/workflow-standards.mdc`: JIT planning, sequential tickets, integration integrity
- `forge/specs/integration-state.md`: Living module dependency map
- `forge/specs/data-model.md`: Entity definitions
- `forge/specs/api-spec.yml`: API endpoints
- `forge/specs/documentation-standards.mdc`: Documentation conventions
- `.lifecycle/artifacts/STATE-MACHINE.md`: Lifecycle state machine concept doc (FW-003).
