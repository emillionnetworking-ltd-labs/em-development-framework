# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""<TICKET-ID> (framework release layer) — Procedural Checks As Config (pure lib).

Replaces the prose pseudocode in verify.md Step 4 with a deterministic
runner. Each check is declared in forge/.checks-registry.yml (governed by
checks.schema.yml) and resolved here via the EXECUTORS dict.

Result enum carries graceful-degradation `skipped-infra` per critic must_fix
#1 of strategy session framework-lifecycle-architecture-v2: when a check's
subprocess fails for infrastructure reasons (timeout / missing binary / OS
error), the row records skipped-infra instead of failed — verify operator
decides whether to treat as deviation candidate or re-run.

Public surface:
  - CheckResult enum
  - CheckOutcome dataclass
  - EXECUTORS dict (executor_key -> callable)
  - load_registry(path) -> list[dict]
  - run_checks(registry, scope, repo_root, ticket, module) -> list[CheckOutcome]
  - report_to_markdown(outcomes) -> str
  - report_to_yaml(outcomes, run_at, ticket, module) -> str
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install --user pyyaml", file=sys.stderr)
    sys.exit(2)


sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root  # noqa: E402


class CheckResult(str, Enum):
    """Per-check verdict. SKIPPED_INFRA closes the flake gap (critic must_fix #1)."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED_INFRA = "skipped-infra"
    NOT_APPLICABLE = "not-applicable"


@dataclass
class CheckOutcome:
    """One row in the ChecksReport."""
    id: str
    name: str
    result: CheckResult
    severity: str
    message: str = ""
    evidence: Optional[dict] = None


# ---------- Registry loading ----------

def load_registry(path: Path) -> list[dict]:
    """Load and shallow-validate the checks registry YAML."""
    if not path.is_file():
        raise RuntimeError(f"checks registry missing at {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError(f"checks registry {path} has no `checks` list")
    return checks


# ---------- Executor implementations ----------

_FILE_LINE_REF_RE = re.compile(r'\b([\w./-]+\.(?:py|md|mdc|yml|yaml))(:\d+)\b')


def _exec_file_line_refs_in_artifacts(cfg, repo_root, ticket, module) -> CheckOutcome:
    """c01: scan ticket artifacts under .lifecycle/artifacts/<module>/{plans,records}/ for file:line refs."""
    base = repo_root / ".lifecycle" / "artifacts" / module
    if not base.is_dir():
        return CheckOutcome(
            id="c01", name="No file:line refs in committed artifacts",
            result=CheckResult.NOT_APPLICABLE, severity="block",
            message=f"Artifacts dir not present: {base}",
        )
    hits = []
    for sub in ("plans", "records"):
        for md in (base / sub).rglob(f"{ticket}_*.md"):
            text = md.read_text(encoding="utf-8", errors="replace")
            for m in _FILE_LINE_REF_RE.finditer(text):
                hits.append(f"{md.relative_to(repo_root).as_posix()}: {m.group(1)}{m.group(2)}")
    if hits:
        return CheckOutcome(
            id="c01", name="No file:line refs in committed artifacts",
            result=CheckResult.FAILED, severity="block",
            message=f"{len(hits)} file:line refs found in artifacts (Wave-8 anti-rot directive).",
            evidence={"hits": hits[:10]},
        )
    return CheckOutcome(
        id="c01", name="No file:line refs in committed artifacts",
        result=CheckResult.PASSED, severity="block", message="0 refs",
    )


def _exec_integration_state_header_bumped(cfg, repo_root, ticket, module) -> CheckOutcome:
    """c02: integration-state.md top entry must mention the current ticket id."""
    path = repo_root / "forge" / "specs" / "integration-state.md"
    if not path.is_file():
        return CheckOutcome(
            id="c02", name="integration-state.md header references this ticket",
            result=CheckResult.SKIPPED_INFRA, severity="warn",
            message=f"integration-state.md not found at {path}",
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    head = text[:4000]
    if ticket in head:
        return CheckOutcome(
            id="c02", name="integration-state.md header references this ticket",
            result=CheckResult.PASSED, severity="warn",
            message=f"{ticket} found in header (first 4KB).",
        )
    return CheckOutcome(
        id="c02", name="integration-state.md header references this ticket",
        result=CheckResult.FAILED, severity="warn",
        message=f"{ticket} not mentioned in integration-state.md header — update-docs step likely pending.",
    )


def _exec_workrequest_schema_validation(cfg, repo_root, ticket, module) -> CheckOutcome:
    """c03: reserved placeholder — returns NOT_APPLICABLE until a future <TICKET-ID> wires the schema."""
    return CheckOutcome(
        id="c03", name="WorkRequest schema validation (reserved)",
        result=CheckResult.NOT_APPLICABLE, severity="warn",
        message="Reserved for <TICKET-ID> (WorkRequest schema enforcement at motor↔agent contract).",
    )


def _exec_pytest_linchpin_passes(cfg, repo_root, ticket, module) -> CheckOutcome:
    """c04: run pytest over forge/tools/_tests + forge/evals; subprocess infra failures -> skipped-infra."""
    timeout = int((cfg or {}).get("timeout_seconds", 90))
    cmd = [sys.executable, "-m", "pytest",
           "forge/tools/_tests/", "forge/evals/",
           "-q", "--tb=line", "-x"]
    try:
        proc = subprocess.run(
            cmd, cwd=str(repo_root),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckOutcome(
            id="c04", name="Linchpin pytest suite passes",
            result=CheckResult.SKIPPED_INFRA, severity="block",
            message=f"pytest exceeded timeout={timeout}s; rerun in a clean env or extend timeout.",
        )
    except (FileNotFoundError, OSError) as e:
        return CheckOutcome(
            id="c04", name="Linchpin pytest suite passes",
            result=CheckResult.SKIPPED_INFRA, severity="block",
            message=f"pytest invocation infra failure: {e!r}",
        )
    if proc.returncode == 0:
        return CheckOutcome(
            id="c04", name="Linchpin pytest suite passes",
            result=CheckResult.PASSED, severity="block",
            message="pytest exit 0",
        )
    return CheckOutcome(
        id="c04", name="Linchpin pytest suite passes",
        result=CheckResult.FAILED, severity="block",
        message=f"pytest exit {proc.returncode}",
        evidence={"stdout_tail": proc.stdout[-500:]},
    )


def _exec_anti_rot_scope_all_clean(cfg, repo_root, ticket, module) -> CheckOutcome:
    """c05: run anti_rot_checker.py --scope all; subprocess failures -> skipped-infra."""
    timeout = int((cfg or {}).get("timeout_seconds", 30))
    cmd = [sys.executable, "forge/tools/anti_rot_checker.py", "--scope", "all"]
    try:
        proc = subprocess.run(
            cmd, cwd=str(repo_root),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckOutcome(
            id="c05", name="Anti-rot scope=all returns 0 findings",
            result=CheckResult.SKIPPED_INFRA, severity="block",
            message=f"anti-rot exceeded timeout={timeout}s",
        )
    except (FileNotFoundError, OSError) as e:
        return CheckOutcome(
            id="c05", name="Anti-rot scope=all returns 0 findings",
            result=CheckResult.SKIPPED_INFRA, severity="block",
            message=f"anti-rot invocation infra failure: {e!r}",
        )
    if proc.returncode == 0:
        return CheckOutcome(
            id="c05", name="Anti-rot scope=all returns 0 findings",
            result=CheckResult.PASSED, severity="block",
            message="anti-rot exit 0 — 0 findings",
        )
    return CheckOutcome(
        id="c05", name="Anti-rot scope=all returns 0 findings",
        result=CheckResult.FAILED, severity="block",
        message=f"anti-rot exit {proc.returncode} — at least 1 finding",
        evidence={"stdout_tail": proc.stdout[-500:]},
    )


# Stable function key -> callable mapping. The registry uses these keys.
EXECUTORS: dict[str, Callable] = {
    "check_file_line_refs_in_artifacts": _exec_file_line_refs_in_artifacts,
    "check_integration_state_header_bumped": _exec_integration_state_header_bumped,
    "check_workrequest_schema_validation": _exec_workrequest_schema_validation,
    "check_pytest_linchpin_passes": _exec_pytest_linchpin_passes,
    "check_anti_rot_scope_all_clean": _exec_anti_rot_scope_all_clean,
}


# ---------- Orchestrator ----------

def run_checks(
    registry: list[dict],
    scope: str,
    repo_root: Path,
    ticket: str,
    module: str,
) -> list[CheckOutcome]:
    """Execute every check whose `applies_to` includes the scope (or 'all')."""
    outcomes: list[CheckOutcome] = []
    for entry in registry:
        applies = entry.get("applies_to", [])
        if scope not in applies and "all" not in applies:
            outcomes.append(CheckOutcome(
                id=entry["id"], name=entry["name"],
                result=CheckResult.NOT_APPLICABLE,
                severity=entry["severity"],
                message=f"scope={scope} not in applies_to={applies}",
            ))
            continue
        executor_key = entry["executor"]
        fn = EXECUTORS.get(executor_key)
        if fn is None:
            outcomes.append(CheckOutcome(
                id=entry["id"], name=entry["name"],
                result=CheckResult.SKIPPED_INFRA,
                severity=entry["severity"],
                message=f"executor key {executor_key!r} not resolved in EXECUTORS dict",
            ))
            continue
        try:
            outcome = fn(entry.get("config"), repo_root, ticket, module)
        except Exception as e:  # noqa: BLE001 — any predicate bug becomes skipped-infra
            outcome = CheckOutcome(
                id=entry["id"], name=entry["name"],
                result=CheckResult.SKIPPED_INFRA,
                severity=entry["severity"],
                message=f"predicate raised: {e!r}",
            )
        outcomes.append(outcome)
    return outcomes


# ---------- Reporting ----------

def report_to_markdown(outcomes: list[CheckOutcome]) -> str:
    """Render outcomes as a Markdown table for the verify report."""
    lines = ["| Check | Result | Severity | Message |",
             "|-------|--------|----------|---------|"]
    for o in outcomes:
        lines.append(f"| `{o.id}` {o.name} | `{o.result.value}` | {o.severity} | {o.message} |")
    return "\n".join(lines)


def report_to_yaml(
    outcomes: list[CheckOutcome],
    run_at: str,
    ticket: str,
    module: str,
) -> str:
    """Render outcomes as a YAML document for ChecksReport persistence."""
    return yaml.safe_dump({
        "run_at": run_at,
        "ticket": ticket,
        "module": module,
        "checks": [
            {
                "id": o.id, "name": o.name,
                "result": o.result.value, "severity": o.severity,
                "message": o.message,
                **({"evidence": o.evidence} if o.evidence else {}),
            }
            for o in outcomes
        ],
    }, sort_keys=False, default_flow_style=False)


# ---------- Top-level verdict ----------

def overall_verdict(outcomes: list[CheckOutcome]) -> int:
    """Return shell exit code: 0 if no block-severity failed or skipped-infra; 1 otherwise."""
    for o in outcomes:
        if o.severity == "block" and o.result in (CheckResult.FAILED, CheckResult.SKIPPED_INFRA):
            return 1
    return 0
