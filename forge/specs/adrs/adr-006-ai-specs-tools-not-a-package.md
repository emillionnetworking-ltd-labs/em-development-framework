---
id: ADR-006
title: ai-specs/tools/ Is Not a Python Package
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---

# ADR-006: `ai-specs/tools/` Is Not a Python Package

## Context

The framework ships Python tools under `ai-specs/tools/` covering schema validation, lifecycle state management, and audit-delta computation. Some have hyphens in their filenames (`state-machine.py`, `validate-artifact.py`, `audit-delta.py`) — a stylistic choice predating this ADR.

Two competing pressures shaped the design:

1. **Skills invoke tools from arbitrary CWDs.** When `/develop` is running, the AI may be in `~/projects/em-development-framework`, in a worktree subdirectory, or anywhere else. Skill prose hardcodes invocations like `python3 ai-specs/tools/state-machine.py check ...` — this must resolve correctly from any reasonable CWD.
2. **Zero-install bootstrap is a design constraint.** A fresh contributor (human or AI in a clean container) should be operational after `git clone` + `pip install -r requirements.txt`. Adding `pip install -e .` to the bootstrap is a real cost, and `pyproject.toml` introduces ongoing packaging maintenance.

A conventional Python package layout (`pyproject.toml`, `__init__.py` everywhere, `pip install -e .`) would solve cross-tool imports but fail the bootstrap test. The hyphen-named files block direct `import` in tests (`import state-machine` is a SyntaxError). And the framework is fundamentally a co-located developer toolset, not a distributable library.

## Decision

**`ai-specs/tools/` is a flat directory of standalone Python scripts, not a package.**

- **No `pyproject.toml` or `setup.py`** for the tools directory.
- **No `__init__.py`** in `ai-specs/tools/` itself. (There is an `__init__.py` in `ai-specs/tools/_tests/` because pytest needs it for test discovery — that is a test-infrastructure concession, not a package declaration.)
- **Shared utilities live in `_common.py`** (no hyphen, importable directly via `from _common import find_framework_root` after `sys.path` injection).
- **Hyphen-named files are loaded via `importlib`** when tests need to reach into them. The conftest pattern (`ai-specs/tools/_tests/conftest.py`) uses `importlib.util.spec_from_file_location(name, path)` to bypass the import-by-name limitation.
- **Skills invoke tools as `python3 ai-specs/tools/X.py args...`**, framework-root-relative. CWD-independence is provided by each tool's internal call to `_common.find_framework_root()` (which uses `Path(__file__).resolve().parent` to anchor on the script's own location, not on the cwd).

## Consequences

### Positive

- **Zero-install bootstrap**. `git clone + pip install -r requirements.txt` is sufficient. No editable-install step; no packaging recipe to maintain.
- **CWD-independent invocation**. Every tool that needs the framework root resolves it via `_common.find_framework_root()`. Tested explicitly in SCRUM-465 (centralization) and SCRUM-469 (pytest coverage).
- **Hyphenated filenames preserved**. Pre-existing tool names like `state-machine.py` and `validate-artifact.py` stayed stable; no rename burden for downstream callers.
- **No packaging-related accidental complexity**. No `MANIFEST.in`, no console-scripts entry points, no version pinning across tools, no namespace packages.

### Negative

- **Cross-tool imports require `sys.path` manipulation**. Patterns like `sys.path.insert(0, str(Path(__file__).parent))` followed by `from _common import find_framework_root` are repeated in many tools (centralized via the SCRUM-465 refactor, but still present as a 3-line shim).
- **Tests for hyphen-named tools use `importlib` gymnastics**. The `_tests/conftest.py` loader (`importlib.util.spec_from_file_location`) is more verbose than `import state_machine`. Documented and tested; not a maintenance burden in practice.
- **Cannot `pip install` the toolkit from outside the repo**. External consumers (if any ever exist) would need to clone the repo or vendor the scripts. This is acceptable today; the framework is internal.

### Operational

50+ tools shipping under `ai-specs/tools/` today. Examples of the pattern in action:

- `_common.py` (62 lines, SCRUM-465) — the canonical shared utility module.
- `state-machine.py` (332 lines) — invoked as `python3 ai-specs/tools/state-machine.py ...` from every skill.
- `validate-artifact.py` (335 lines) — same pattern.
- `_tests/conftest.py` (91 lines, SCRUM-469) — `importlib.util.spec_from_file_location` loader for hyphen-named files.
- `ai-specs/tools/consolidation/` and `ai-specs/tools/runtime/` — sub-categories within the flat structure; still scripts, not subpackages.

## Re-evaluate when

This decision should be reconsidered if any of the following happen:

- The toolkit grows beyond ~100 tools (current: ~55) and cross-tool dependency wrangling becomes painful.
- External consumers emerge who need to `pip install` the toolkit (e.g. a sibling project wants to reuse the schema validator).
- The hyphen-naming convention is renounced project-wide (would unblock direct `import` and could simplify tests significantly).

None of these conditions is met today. The decision stands.

## Alternatives Considered

- **Full Python package** (`pyproject.toml` + `pip install -e .` at bootstrap) — rejected. Friction added to every fresh clone; ongoing packaging maintenance cost; doesn't fit the "co-located developer toolset" character of the framework.
- **Submodule under em-ecosystem's package** — rejected. Tight coupling between framework and em-ecosystem that doesn't match the design intent (framework is parallel to and supportive of em-ecosystem, not a dependency of it).
- **Bash-only tools** — rejected. Tools need YAML parsing, JSON-schema validation, subprocess control, structured error reporting. Python is the appropriate language for everything except the backup script (where bash + rsync is the right fit, see SCRUM-472).
- **Rename all hyphenated tools to underscores** (would enable direct `import`) — considered but deferred. Renames break every skill that invokes the tools by current path; backwards-compatibility shims would proliferate. Cost > benefit at current scale.

## References

- `ai-specs/tools/_common.py` — canonical shared utility (62 lines).
- `ai-specs/tools/_tests/conftest.py` — importlib loader pattern (91 lines).
- SCRUM-465 commit `0ba6d7c` — centralized `find_framework_root()` into `_common.py`; refactored 26 tools to import from there.
- SCRUM-469 commit `2c131eb` — established the pytest infrastructure including the importlib loader for hyphen-named tools.
- SCRUM-470 — fixed Bug A in `validate-artifact.py:165` (Path object handling) discovered via the new test infrastructure.
- ADR-001 (`adr-001-fw-004-state-machine.md`) — `state-machine.py` is the prime example of a hyphen-named, framework-root-relative tool.
- ADR-004 (`adr-004-schema-driven-validation.md`) — `validate-artifact.py` follows the same pattern.
