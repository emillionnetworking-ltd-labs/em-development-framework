---
id: ADR-009
title: Pydantic as a Runtime Dependency for the Meta-Audit
status: accepted
date: 2026-05-27
supersedes: null
superseded_by: null
---

# ADR-009: Pydantic as a Runtime Dependency for the Meta-Audit

## Context

After the 2026-05-27 framework reset (lifecycle + audit only) and the demolition of the deleted self-audit layer, the framework is rebuilding its self-checking from scratch. The first new component is the **meta-audit** (`ai-specs/tools/meta-audit/`, SCRUM-532), scoped to the lifecycle subsystem: it mechanically verifies that lifecycle stages are deterministic, isolated and exit-code-honest enough to be wrapped as nodes by the future LangGraph orchestrator.

The meta-audit carries a non-trivial in-memory state object — a map of lifecycle stage → four boolean metrics + status + errors + evidence — that is itself produced as a `--json` artifact. Two implementation styles were available:

1. **Stdlib `dataclasses` + hand-rolled validation.** Zero new dependency, consistent with the "tools are effectively stdlib + pyyaml/jsonschema" status quo.
2. **Pydantic models.** Typed, self-validating state with `extra="forbid"`, `model_dump()` for the JSON artifact, and enum/`Literal` rigor out of the box.

The framework is **not** strictly stdlib-only at the dependency level: `requirements.txt` already pins `pyyaml` and `jsonschema` as runtime deps used across the tools. So adopting one more well-established, widely-installed dependency is an incremental step, not a new category of risk.

The decisive forward-looking factor: the **orchestrator** this meta-audit is designed to serve will be built on **LangGraph**, whose state contract is Pydantic-based. Modeling the meta-audit's own state in Pydantic now keeps the framework's self-checking layer architecturally consistent with the orchestrator it audits readiness for, and lets the same `AuditState` discipline (rigid typing, no free-text injection) be dogfooded by the very tool that enforces it elsewhere.

## Decision

**Adopt `pydantic>=2,<3` as a runtime dependency, added to `requirements.txt`.**

- Used initially and exclusively by `ai-specs/tools/meta-audit/`.
- The meta-audit's `AuditState` / `PhaseAudit` models set `model_config = ConfigDict(extra="forbid")` — the auditor's own output obeys the determinism rule (no free-text outside typed fields) that it checks on the lifecycle schemas.
- ADR-006 still holds: `ai-specs/tools/` remains **not a package**. `meta-audit/` is a sub-directory of standalone scripts (like `consolidation/`, `runtime/`), invoked **by path** (`python3 ai-specs/tools/meta-audit/lifecycle.py`), never `python3 -m`. Pydantic does not change that.
- Bootstrap is unchanged: `git clone` + `pip install -r requirements.txt` remains sufficient.

## Consequences

### Positive

- Typed, self-validating state; the `--json` artifact is shape-guaranteed by the model.
- Forward-consistent with the LangGraph orchestrator (same state-contract family).
- The meta-audit dogfoods the rigidity it enforces.

### Negative

- One more runtime dependency to install and keep within its version range (`>=2,<3`).
- Tools that previously needed no third-party import now have a peer in the tree that does; future tools must decide per-case whether stdlib or pydantic is appropriate (default: stdlib unless typed-state rigor is warranted, as here).

### Operational

- `requirements.txt` gains `pydantic>=2,<3`. CI installs it; the meta-audit tests import the models directly.
- No change to existing tools; no `pyproject.toml`, no editable install.

## Re-evaluate when

- A lighter approach (stdlib `dataclasses` + a tiny validator) proves sufficient across the meta-audit suite and the pydantic dependency stops earning its place.
- Pydantic major-version churn (v3) imposes migration cost disproportionate to the benefit.
- The orchestrator direction changes away from a Pydantic-based state contract.

## Alternatives Considered

- **Stdlib dataclasses + manual validation** — rejected for the meta-audit: loses `extra="forbid"`, enum rigor, and `model_dump()` ergonomics; reimplementing them by hand is exactly the kind of accidental complexity pydantic removes. Still the default for tools that do not carry rich typed state.
- **Keep stdlib-only as a hard rule** — rejected: the rule was never actually hard (`pyyaml`/`jsonschema` are already runtime deps), and the orchestrator's Pydantic contract makes consistency more valuable than dependency-count minimalism here.

## References

- ADR-006 (`adr-006-ai-specs-tools-not-a-package.md`) — `meta-audit/` is a sub-directory of scripts, invoked by path; unchanged by this ADR.
- ADR-004 (`adr-004-schema-driven-validation.md`) — schema-driven validation principle; the meta-audit's typed state extends the same spirit to the auditor's own output.
- SCRUM-532 — Meta-Audit foundation + lifecycle-stage runner (first consumer of this decision).
- `requirements.txt` — `pydantic>=2,<3` pin.
