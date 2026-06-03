# Changelog

End-user-facing release notes for the **em-development-framework** distribution artifact.
Append-only; entries match GitHub Release tags published at
https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases.

For framework-protocol changelog (developer-facing append-only log of playbook conventions + skill behavior changes), see `forge/CHANGELOG.md`.

---

## [v0.19.0] — 2026-05-31 — Clean Distribution Pipeline (first release)

First GitHub Release of the framework as a **clean distribution artifact**. Prior git tags (v0.5.0–v0.18.1) were commit markers only with no Release assets.

### Highlights since prior tags

- **ONE-COMMAND installer** (internal cycle): `./forge/distribution/install.sh` (Linux/macOS) + `.\forge\distribution\install.ps1` (Windows). End-to-end bootstrap with atomicity safety net + idempotent re-run + cross-platform 9-cell CI matrix.
- **AI agents step-0 directive** (internal cycle): `AI_START.md` at repo root anchors a hard termination criterion preventing autopilot exploration loops.
- **MCP server** (internal cycle Strategy v2): `em-cli serve-mcp` exposes 3 tools + 3 resources via Model Context Protocol (stdio default + opt-in streamable-HTTP). Any major 2026 MCP client can connect.
- **Multi-agent gateway artifacts** (internal cycle Strategy v2): `em-cli render-gateway` generates AGENTS.md + copilot-instructions.md + CLAUDE.md + ai-bootstrap.md from `forge.config.yml`.
- **Workspace contract runtime injection** (internal cycle Strategy v2): motor LangGraph consumes `forge.config.yml` at session-build and exposes the workspace dict in every `WorkRequest` context.
- **Atomicity safety net** (internal cycle): `em-cli init` rollback on mid-flow failure; 6 invariants provable-by-construction; operator pre-existing content NEVER deleted.

### Clean distribution scope (this release)

- Source repo dev surface (`.lifecycle/`, `orchestrator/.strategy-sessions/`, `forge/_parked/`, internal tests, `forge/evals/`, `conftest.py`, `pytest.ini`, `requirements-dev.txt`) EXCLUDED via `.gitattributes export-ignore`.
- Hardcoded dogfood `forge.config.yml` OMITTED — `em-cli setup` regenerates per-operator on first run via the Wave B atomicity-safe init flow.
- `LICENSE` at root + `SHA256SUMS` published with each release asset for integrity verification.

### Operator install

```bash
curl -L https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases/download/v0.19.0/em-framework-v0.19.0.tar.gz | tar xz
cd em-framework-v0.19.0
./forge/distribution/install.sh
```

### Integrity verification

```bash
curl -LO https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases/download/v0.19.0/SHA256SUMS
sha256sum -c SHA256SUMS
```

---

(Future releases will append entries here; oldest at bottom, newest at top.)
