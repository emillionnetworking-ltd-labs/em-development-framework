# Changelog

End-user-facing release notes for the **em-development-framework** distribution artifact.
Append-only; entries match GitHub Release tags published at
https://github.com/emillionnetworking-ltd-labs/em-development-framework/releases.

For framework-protocol changelog (developer-facing append-only log of playbook conventions + skill behavior changes), see `forge/CHANGELOG.md`.

---

## [v0.23.0] — 2026-06-03 — Workspace Isolation Absolute Boundary (BREAKING)

W68 SCRUM-636 hotfix closing the workspace-isolation gap that surfaced post-v0.22.0.

### Breaking changes

- **Legacy-mode trigger removed**: the `is_legacy_mode()` and `_legacy_paths_for_repo()` functions no longer exist in `framework.api`. Pre-0.23 environments that relied on auto-detection of dogfood mode (forge.config.yml without `output_dir`) now get the same `.em-out/` default as new users. If you need the prior behavior, set `output_dir` explicitly in your forge.config.yml.
- **`repo_root()` hard-renamed to `framework_install_root()`**: the function `from framework.cli import repo_root` no longer works. Use `framework_install_root()`. The semantic is narrowed: this function returns the framework's INSTALL location and is used ONLY for finding adjacent read-only resources; it is NEVER a write target.
- **Checkpointer constructors require explicit paths**: `StateYamlCheckpointer(checkpoints_dir=None)` and `StrategySnapshotSaver(sessions_dir=None)` now raise `TypeError`. Use the session builders or pass explicit paths.

### Why

Post-v0.22.0 testing revealed that `--output-dir` only redirected langgraph checkpoints + strategy sessions; the canonical `state.yml` + `.lifecycle/artifacts/` tree still leaked into the framework install directory. The fix per ADR-015's stated intent: `output_dir` is the ABSOLUTE root for ALL writes. The framework code tree is read-only at runtime, mechanically enforced by `framework/tests/test_workspace_boundary.py`.

### Migration

If you used `from framework.cli import repo_root`, replace with `from framework.cli import framework_install_root`.

If you relied on dogfood-mode auto-detection, set `output_dir` explicitly in `forge.config.yml` (e.g., `output_dir: "."` to preserve repo-relative writes; or accept the `.em-out/` default).

If you previously expected `state.yml` to land at `<framework-install>/.lifecycle/artifacts/...`: it now lives at `<output_dir>/.lifecycle/artifacts/...`. This is the long-promised workspace isolation.

---

## [v0.22.0] — 2026-06-03 — Core Decoupling + Workspace Isolation

Sprint 28 SEAL — framework re-architected as commercial-grade product per ADR-015 P1-Refined.

Distribution shape: 75 files. Public API: `from framework import Framework; Framework(output_dir="./workspace")`.

### Highlights

- Module relocation: orchestrator/* → framework/_runtime/orchestrator/
- 5-level config precedence (CLI > class > env > config > default)
- IP isolation: forge/specs + .playbooks + .agents PRIVATE-only
- 12 active Open-Core compliance invariants

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
