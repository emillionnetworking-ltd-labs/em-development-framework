# ai-specs — EM Ecosystem Development Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

The multi-copilot development framework by **EMillion Networking LTD**. This framework defines the standards, agent roles, and command workflows that govern all development across a product ecosystem — from a core platform application to satellite applications.

The framework lives **outside** the governed product's codebase. It does not contain application code — it contains the rules, patterns, and specifications that AI coding copilots use to generate, review, and maintain code consistently across the entire product ecosystem.

## Download (clean distribution)

End users (operators who want to USE the framework, not develop it) should download the clean distribution artifact from the [Releases page](https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases) rather than cloning the source repo:

```bash
# Linux / macOS
curl -L https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases/latest/download/em-framework-v0.22.0.tar.gz | tar xz
cd em-framework-v0.22.0
./forge/distribution/install.sh
```

```powershell
# Windows
Invoke-WebRequest -Uri https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases/latest/download/em-framework-v0.22.0.zip -OutFile em-framework.zip
Expand-Archive em-framework.zip -DestinationPath .
cd em-framework-v0.22.0
.\forge\distribution\install.ps1
```

Verify archive integrity via the `SHA256SUMS` asset on the same release.

The clean distribution OMITS development surface (`.lifecycle/`, strategy session debates, internal tests, hardcoded dogfood config). Contributors who want full source for development continue with `git clone`.

> **Repository structure**: this is the public **distribution mirror**. Development happens in a separate private source repo where the framework's own lifecycle workflow drives release production. Community feedback flows through GitHub Discussions (see [`CONTRIBUTING.md`](CONTRIBUTING.md) for details).

## Workspace anatomy

The framework's installation directory is treated as **read-only post-install**. All generated state — state machine files, strategy session checkpoints, audit logs — lives in a separate **user-controlled output directory** that you choose. The default is `.em-out/` in your current working directory; you can override it via CLI flag, env var, or programmatic constructor.

```python
from framework import Framework
fw = Framework(output_dir="./my-workspace")
```

CLI:
```bash
python -m framework.cli.run --output-dir ./my-workspace --mode lifecycle ...
```

Env var:
```bash
export EM_FRAMEWORK_OUTPUT_DIR=./my-workspace
python -m framework.cli.run --mode lifecycle ...
```

Precedence: CLI flag > constructor arg > env var > default (`.em-out/`).

## Security model

The workspace isolation enforced by v0.22.0 closes two attack patterns. First, **IP isolation**: the framework's internal methodology (specs, playbooks, agents) is excluded from the distribution — your installation contains only the executable engine. Second, **secret isolation**: the framework's installation directory is read-only, so your project secrets cannot accidentally land inside the framework code when you back up or share your workspace. Generated state goes to `.em-out/` (or your chosen path) which lives in your project, not in the framework install.

### Recommended `.gitignore` for projects using the framework

```
.em-out/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

## Documentation

The framework's documentation is organized in two tiers. Start here:

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the framework works under the hood — lifecycle internals (state flow, the lib + CLI-shell pattern, the anti-drift shield, the orchestrator direction). |
| [COMMANDS_REFERENCE.md](COMMANDS_REFERENCE.md) | The map of every command — Skills (`/<name>`) vs Tools (`python3 …`), and how to invoke them. |
| [INSTALL.md](INSTALL.md) | Setup, prerequisites, and how to wire the skills. |

Deeper reference (Tier 2) lives under `forge/`:

| Location | What it covers |
|---|---|
| [`forge/specs/`](forge/specs/) | Coding standards (`*-standards.mdc`), the data model, the API spec, and the audit framework. |
| [`forge/specs/adrs/`](forge/specs/adrs/) | Architecture Decision Records — *why* each foundational choice was made. |

## Framework Structure

```
.
├── forge/                        # Core framework directory
│   ├── specs/                       # Development standards and specifications
│   │   ├── base-standards.mdc       # Core development rules (single source of truth)
│   │   ├── documentation-standards.mdc  # Documentation conventions
│   │   ├── workflow-standards.mdc   # JIT planning, sequential tickets, integration integrity
│   │   ├── integration-state.md     # Living module dependency map (updated per ticket)
│   │   ├── api-spec.yml             # OpenAPI 3.0 specification (~63 endpoints)
│   │   ├── data-model.md            # Domain model (15 entities, 12 enums, Prisma schema)
│   │   └── development_guide.md     # Setup and development workflow
│   ├── .playbooks/                  # Skill prompts (operator slash-commands + internal playbooks read at LangGraph interrupts)
│   │   ├── plan-backend-ticket.md   # Backend implementation planning
│   │   ├── plan-frontend-ticket.md  # Frontend implementation planning
│   │   ├── develop-backend.md       # Backend implementation execution
│   │   ├── develop-frontend.md      # Frontend implementation execution
│   │   ├── enrich-us.md             # User story enrichment
│   │   ├── commit.md                # Git commit and PR workflow
│   │   ├── explain.md               # Concept explanation and learning
│   │   ├── update-docs.md           # Implementation records and documentation updates
│   │   ├── check-api-contract.md    # API spec vs codebase contract audit
│   │   └── meta-prompt.md           # Prompt engineering
│   ├── .agents/                     # Agent role definitions
│   │   ├── backend-developer.md     # NestJS backend architect agent
│   │   ├── frontend-developer.md    # Next.js frontend developer agent
│   │   └── product-strategy-analyst.md  # Product strategy agent
│   └── changes/                     # Feature lifecycle documentation (output directory)
│       ├── [module]/                # Organized by module (auth, users, permissions, etc.)
│       │   ├── plans/               # PRE-implementation: enrichment, architecture, steps, tests
│       │   │   ├── internal cycle/        # Plans organized by sprint
│       │   │   ├── internal cycle/
│       │   │   └── Sprint N/
│       │   ├── records/             # POST-implementation: commits, deltas, test results, lessons
│       │   │   ├── internal cycle/        # Records organized by sprint
│       │   │   ├── internal cycle/
│       │   │   └── Sprint N/
│       │   └── audit/               # Timestamped audit reports for this module
│       │       └── audit-YYYY-MM-DDTHH-MM/
│       └── backlog/                 # For tickets not assigned to a specific module
│
├── AGENTS.md                        # Generic agent configuration
├── CLAUDE.md                        # Claude / Cursor configuration
├── codex.md                         # GitHub Copilot / Codex configuration
└── GEMINI.md                        # Google Gemini configuration
```

## Multi-Copilot Support

ai-specs supports multiple AI coding copilots through naming conventions:

| File        | Copilot                | Purpose                         |
|-------------|------------------------|---------------------------------|
| `CLAUDE.md` | Claude                 | Claude-optimized configuration  |
| `codex.md`  | GitHub Copilot / Codex | Copilot-optimized configuration |
| `GEMINI.md` | Google Gemini          | Gemini-optimized configuration  |
| `AGENTS.md` | Generic                | Works with most copilots        |

All configuration files reference the same core rules in `forge/specs/base-standards.mdc`, ensuring consistency across tools while allowing copilot-specific customizations.

**Why this approach:**
- **Single source of truth** — core rules maintained in one place
- **Copilot flexibility** — each team member uses their preferred AI tool
- **Zero configuration** — copilots auto-detect their configuration file
- **Easy updates** — update rules once, all copilots benefit

## Role Within the EM Ecosystem

ai-specs is the **development engine** of the EM Ecosystem. It defines how code is written, reviewed, and maintained — but it does not contain application code.

```
Workspace: <your-org>
├── <your-product>/          # Application code (e.g. backend-api + dashboard-frontend + marketing-website)
├── forge/                # THIS FRAMEWORK — standards, agents, commands
└── integrations/            # External integrations (Jira bridge, etc.)
```

**Key distinctions:**
- ai-specs **governs** em-ecosystem-code but lives outside it
- ai-specs **does not** get copied into the codebase — it is referenced from the workspace root
- ai-specs **defines** the architecture, domain model, API spec, and coding standards
- the framework **generates** implementation plans for core product modules and satellite apps
- `integrations/` exists in the workspace but is **not part of** ai-specs

## EM Ecosystem Context

ai-specs is tailored for the EM Ecosystem's architecture and domain:

### Architecture: Core + Satellite Apps

- **Core Product** — typically a monolith with all foundational modules + a single schema + a frontend dashboard
- **Satellite Apps** — independent applications (own backend + frontend) that integrate with the core product via REST API

### Technology Stack

| Layer    | Technology                                      |
|----------|-------------------------------------------------|
| Backend  | NestJS 11, TypeScript 5.7, Prisma 7, PostgreSQL |
| Frontend | Next.js 14 (App Router), React 18, TailwindCSS  |
| Auth     | Passport.js, JWT, OAuth 2.0 (Google, GitHub)    |
| Testing  | Jest, React Testing Library                     |

### Domain (15 entities, 12 enums)

The domain model covers: **User**, **Auth/RefreshToken**, **Roles/Permissions** (granular RBAC), **Projects**, **Teams**, **Notifications**, **Billing** (Subscriptions + Invoices), **Settings**, **Modules** (platform registry), and **Apps** (satellite registry).

Full specifications in `forge/specs/data-model.md` and `forge/specs/api-spec.yml`.

## Development Workflow

### 1. Enrich the User Story (Optional)

If a user story lacks detail, enrich it before planning:

```
/enrich-us <TICKET-ID>
```

Analyzes the Jira ticket and adds: detailed acceptance criteria, field specifications, endpoint definitions, file references, testing scenarios, and non-functional requirements.

### 2. Plan the Feature (Just-In-Time)

> **CRITICAL**: Plans must be created **immediately before implementation**, never in batches. Plan ticket N only after ticket N-1 is fully implemented, tested, and committed. See `workflow-standards.mdc` for full JIT rules.

Generate a detailed implementation plan:

```
/plan <TICKET-ID>
```

Creates a comprehensive plan in `forge/changes/[module]/plans/Sprint [N]/` with:
- **Codebase State Snapshot** — verified against live code, not stale assumptions
- Architecture context (affected modules, entities, endpoints)
- Step-by-step implementation instructions
- **Guard dependency chain verification** — for each `@UseGuards()`, validated against `integration-state.md`
- Testing checklist and error handling
- Documentation update requirements
- **Module-Level Planning** — when the ticket involves a full core-product module (entity design, API surface, cross-module dependencies, transaction boundaries, permissions)
- **Satellite App Planning** — when the ticket involves a satellite app (core-product auth integration, data dependencies, own schema, app registry entry)

### 3. Implement the Feature

Execute the plan:

```
/develop <TICKET-ID>
```

The AI determines workspace context (core-product module vs. satellite app), performs a **pre-implementation integrity check** (verifies module imports, guard dependencies, constructor signatures against `integration-state.md`), implements changes following the plan, runs a **post-implementation integrity check** (build, tests, startup), updates `integration-state.md`, and prepares a PR.

### 4. Commit and PR

```
/commit <TICKET-ID>
```

Creates a scoped commit and pull request with ticket linking.

### Additional Commands

| Command                 | Purpose  |
|-------------------------|----------|
| `/explain [topic]`      | Concept-focused learning and skill acquisition |
| `/update-docs`          | Create implementation record and update technical documentation |
| `/check-api-contract`   | Audit api-spec.yml vs actual controllers — find undocumented or mismatched endpoints |
| `/meta-prompt [prompt]` | Refine and structure a prompt |

### 5. Document the Record

After implementation is complete, create a record in `forge/changes/[module]/records/Sprint [N]/`:

```
/update-docs <TICKET-ID>
```

Documents the implementation outcome: commits, deviations from plan, bugs found, test results, and lessons learned. If the implementation deviated from the plan, the Jira ticket description must also be updated to reflect the actual state.

### Changes Directory Convention

The `forge/changes/` directory tracks the full lifecycle of each feature:

| Directory | Phase | Content | Mutability |
|-----------|-------|---------|------------|
| `changes/[module]/plans/Sprint [N]/` | PRE-implementation | Enrichment, architecture, steps, code, tests, DoD | **Frozen** after development starts |
| `changes/[module]/records/Sprint [N]/` | POST-implementation | Commits, deltas vs plan, test results, bugs, lessons | Created after implementation |
| `changes/[module]/audit/audit-YYYY-MM-DDTHH-MM/` | Audit | Timestamped audit reports | Created by `/audit` |

**Folder convention**: Plans, records, and audits are organized by module (e.g., `auth/`, `users/`, `permissions/`), then by sprint (e.g., `internal cycle/`, `internal cycle/`). The module is derived from the code path being modified (e.g., `<workspace.backend_root>/auth/` → `auth`). The sprint is determined from the ticket's Jira sprint assignment. Use `backlog/` for tickets not assigned to a specific module.

**Naming convention**: `SCRUM-{id}_{scope}.md` where scope is `backend`, `frontend`, or `fullstack`.

**Plan structure**: Defined by the planning command templates:
- Plans → `.playbooks/plan.md` (unified, auto-detects scope: backend 16 sections, frontend 14 sections, fullstack both)

**Record structure**: Defined by the `/update-docs` command template (see `.playbooks/update-docs.md`). Sections:
- **Header**: `# Implementation Record: [TICKET-ID] [Feature Name]`
- **Summary**: What was implemented, scope (backend/frontend/fullstack), branch name
- **Plan Reference**: Link to the original plan in `changes/[module]/plans/Sprint [N]/`
- **Commits**: List of commits (hash, message, files changed)
- **Deviations from Plan**: What changed vs the original plan and why
- **Test Results**: Coverage %, tests passed/failed, manual verification outcomes
- **Bugs Found**: Issues discovered during implementation (fixed or deferred)
- **Documentation Updates**: Files updated (including `integration-state.md` — MANDATORY)
- **Lessons Learned**: Insights for future implementations

**Rules**:
- Plans are **not modified** after development begins — they serve as the original contract
- Records document **what actually happened** — deviations, decisions, bugs found
- If the implementation deviates from the plan, the **Jira ticket** is updated to reflect the current truth
- Records should be concise — no need to repeat the plan, only document deltas

## Core Development Rules

All development follows principles defined in `forge/specs/base-standards.mdc`:

1. **Small Tasks, One at a Time** — incremental, focused changes
2. **Test-Driven Development** — write failing tests first
3. **Type Safety** — fully typed TypeScript, strict mode
4. **Clear Naming** — descriptive variables and functions
5. **English Only** — all code, comments, documentation, and commits in English
6. **90%+ Test Coverage** — comprehensive testing across all layers
7. **Incremental Changes** — reviewable, atomic modifications

### Standards Documents

| Document                      | Scope  |
|-------------------------------|--------|
| `base-standards.mdc`          | Core rules (language, TDD, code quality, git workflow) |
| `documentation-standards.mdc` | Technical documentation structure and conventions |
| `workflow-standards.mdc`      | JIT planning, sequential tickets, integration integrity, test mock propagation |
| `integration-state.md`        | Living module dependency map, guard chains, permissions registry (updated per ticket) |
| `api-spec.yml`                | OpenAPI 3.0 specification with ~63 endpoints across 12 tag groups |
| `data-model.md`               | 15 entities, 12 enums, complete Prisma schema, TypeScript interfaces, ER diagram |

> **Product-specific specs** (e.g. `backend-standards.mdc`, `frontend-standards.mdc`) live with the product, not the engine. For a governed project they are loaded from `<project>/.lifecycle/specs/` via the `LIFECYCLE_ROOT` env var. The framework engine carries only generic (product-agnostic) specs.

## Agent Roles

| Agent                      | Model  | Specialty  |
|----------------------------|--------|------------|
| `backend-developer`        | Sonnet | Backend modular architecture, schema/ORM, guards, DTOs, testing. Knows how to build core-product modules and satellite apps.  |
| `frontend-developer`       | Sonnet | Frontend App Router, styling, contexts, API client. Knows how to build core-product frontend modules and satellite frontends. |
| `product-strategy-analyst` | Opus   | Product ideation, market analysis, value proposition design. |

## Benefits

**For developers:** Consistent code quality, automatic 90%+ coverage, complete documentation, faster onboarding, reduced review time.

**For teams:** Copilot flexibility, knowledge preservation, quality consistency across AI tools, scalable practices.

**For the ecosystem:** Maintainable codebase, production-ready code from day one, living documentation (API specs and data models always current), autonomous AI implementation from plans, module and satellite app generation.

## License

Released under the [MIT License](LICENSE). Copyright © 2026 EMillion Networking LTD.

The framework is permissively licensed — you may use, modify, distribute, and build on it freely, including in commercial contexts. See [`LICENSE`](LICENSE) for the canonical terms.

Upstream attributions and third-party notices live in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Authoring of the framework's adaptations and extensions is by EMillion Networking LTD.

Authoring of the framework's architectural decisions, governance specs, and agent runtime conventions remains attributable to EMillion Networking LTD via the copyright notice preserved in each file's metadata.

---

**Maintained by EMillion Networking Labs**
