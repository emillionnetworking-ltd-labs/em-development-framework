# em-development-framework - Installation Guide

## Download (clean distribution)

End users should download the clean distribution artifact from the [Releases page](https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases) rather than cloning the source repo:

```bash
# Linux / macOS
curl -L https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases/latest/download/em-framework-v0.19.0.tar.gz | tar xz
cd em-framework-v0.19.0
./forge/distribution/install.sh
```

```powershell
# Windows
Invoke-WebRequest -Uri https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases/latest/download/em-framework-v0.19.0.zip -OutFile em-framework.zip
Expand-Archive em-framework.zip -DestinationPath .
cd em-framework-v0.19.0
.\forge\distribution\install.ps1
```

Verify integrity via the `SHA256SUMS` asset published alongside each release.

The clean distribution OMITS development surface (`.lifecycle/`, strategy session debates, internal tests, hardcoded dogfood `forge.config.yml`). Contributors who want full source for development continue with `git clone` (see Quick Start section below).

## Quick Start (one command)

Strategy v3 internal cycle ships a one-command installer for both humans and AI agents.

**Linux / macOS**:

```bash
git clone git@github.com:emillionnetworking-ltd-labs/em-development-framework.git ~/projects/em-development-framework
cd ~/projects/em-development-framework
./forge/distribution/install.sh
```

**Windows (PowerShell 5+)**:

```powershell
git clone git@github.com:emillionnetworking-ltd-labs/em-development-framework.git $HOME\projects\em-development-framework
cd $HOME\projects\em-development-framework
.\forge\distribution\install.ps1
```

**Verification** (post-install):

```bash
python3 forge/tools/em-cli.py doctor    # exits rc=0 when healthy
```

**Idempotency**: re-running the installer after success is a silent no-op (rc=0). Use `--force` to re-run init explicitly.

## What the installer does

1. **Pre-flight**: verifies python3 + git on PATH; emits distro-aware error message if `python3-venv` (Debian/Ubuntu) or `ensurepip` (Fedora/Arch/macOS) is missing.
2. **Bootstrap**: creates local `.venv` + installs 4 runtime dependencies (pyyaml + jsonschema + pydantic + mcp).
3. **Setup**: invokes `em-cli setup` which auto-detects greenfield-vs-map mode from filesystem signals (package.json/pyproject.toml/Cargo.toml/go.mod/etc.) + initializes `forge.config.yml` + chains `em-cli doctor` + emits "em-cli setup COMPLETE" summary.

The setup flow is **atomic**: any mid-flow failure rolls back to a clean state without touching pre-existing operator content (6 safety invariants proved by construction; see `forge/tools/_init_atomicity.py`).

## AI agents (zero-prompt autopilot)

Any AI coding agent (Claude Code, Cursor, GitHub Copilot, Windsurf, etc.) opening the freshly-cloned repo MUST first read `AI_START.md` at repo root, then execute the single directive within. AI_START.md anchors a hard termination criterion preventing autopilot exploration loops.

## Prerequisites

- Python >= 3.10 (3.12 recommended - operator's reference version)
- `git` and `gh` (GitHub CLI) on PATH
- Network access to PyPI (for `pip install`)
- A GitHub account with access to `emillionnetworking-ltd-labs/em-development-framework`

### Optional but recommended

- `pipx` for isolated CLI tool installs (some operators may prefer pipx-distributed flow once the framework is pyproject-packaged in a future Wave; not required today).

## Skills setup (Claude Code integration)

To invoke lifecycle skills as `/enrich-us`, `/plan`, etc. inside Claude Code, create this symlink one-time:

```bash
ln -s ~/projects/em-development-framework/forge/.playbooks ~/.claude/commands
```

Verify:

```bash
ls -la ~/.claude/commands
# Expected: lrwxrwxrwx ... commands -> /home/.../em-development-framework/forge/.playbooks
```

The skills' YAML frontmatter carries a `description:` field; Claude Code uses it to list them in the `/` menu (reload the window after first wiring).

## Environment variables

Required for lifecycle skills that hit the Jira API (`/enrich-us`, `/update-docs`):

- `JIRA_EMAIL` - Atlassian account email
- `JIRA_BASE_URL` - e.g. `https://your-instance.atlassian.net`
- `JIRA_TOKEN` - API token from your Atlassian profile (do NOT commit)

A convenient pattern is a `~/.atlassian-credentials` file (sourced, not committed) exporting the three.

## Fallback: manual setup (advanced)

If you prefer manual control over the installer, follow these 5 steps:

```bash
git clone git@github.com:emillionnetworking-ltd-labs/em-development-framework.git ~/projects/em-development-framework
cd ~/projects/em-development-framework
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -c "import yaml, jsonschema, pydantic; print('deps OK')"
```

Then wire the skills (see "Skills setup" above) and initialize your workspace:

```bash
cd ~/your-target-project
python3 ~/projects/em-development-framework/forge/tools/em-cli.py init --mode=greenfield
```

You'll be prompted for: product name (slug), stack language, framework name, backend root path, frontend root path. Defaults are auto-detected from filesystem signals.

Non-interactive mode (CI / automation):

```bash
python3 ~/projects/em-development-framework/forge/tools/em-cli.py init --mode=greenfield \
    --non-interactive \
    --product-name acme \
    --language typescript --framework Next.js \
    --backend-root null --frontend-root src
```

## Verify (manual checklist for either flow)

| Check | Severity if missing |
|---|---|
| Python >= 3.10 (`python3 --version`) | blocking |
| `import yaml, jsonschema, pydantic, mcp` succeeds | blocking |
| `git` CLI on PATH | blocking |
| `gh` CLI on PATH | degraded - only `/commit` lifecycle step fails |
| `~/.claude/commands` symlink -> `forge/.playbooks` | degraded - skills won't appear as `/<name>` |
| `JIRA_EMAIL` + `JIRA_BASE_URL` + `JIRA_TOKEN` env vars | degraded - only Jira-touching steps fail |

Without Jira env vars, `validate-artifact.py`, `py_compile`, and `state-machine.py` all work; only Jira-touching lifecycle steps (`/enrich-us`, `/update-docs`) fail.

## Running live evals (optional)

The framework includes opt-in live evals that invoke Claude via the Anthropic SDK to validate skill behavior. They are SKIPPED by default to avoid token spend on every PR. To run them locally:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export EVALS_LIVE=true
python3 -m pytest forge/evals/live/ -v
```

Cost note: each live eval consumes ~5-10k tokens. Operator-controlled. Without `EVALS_LIVE=true` (or without `ANTHROPIC_API_KEY`), live tests skip silently.

Static evals (skill `.md` structure validation) run automatically via Job 5 (pytest) in CI - no setup needed.

## MCP server (optional)

Strategy v2 framework release layer shipped a Model Context Protocol server. Run it:

```bash
python3 forge/tools/em-cli.py serve-mcp
```

Default transport: stdio (local-only, single-client-per-process per MCP 2026-07-28 spec). Operator can opt into streamable-HTTP via `--transport http --port 8765`. Any major 2026 MCP client (Claude Desktop, Cursor, GitHub Copilot, etc.) can connect and discover framework tools/resources at runtime.

## Multi-agent gateway files (optional)

Strategy v2 framework release layer shipped `em-cli render-gateway` which generates 4 vendor-specific instruction files from `forge.config.yml`:

```bash
python3 forge/tools/em-cli.py render-gateway
```

Generates: `AGENTS.md` (universal 2026 convention) + `.github/copilot-instructions.md` (Copilot Workspace) + `CLAUDE.md` (Claude Code) + `ai-bootstrap.md` (chat-web fallback).
