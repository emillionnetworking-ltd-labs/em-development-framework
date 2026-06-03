#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""meta-audit/lifecycle.py — framework meta-audit for the LIFECYCLE subsystem.

The framework's first meta-audit (mechanical replacement for the deleted
/re-audit layer), scoped to the lifecycle. It verifies that lifecycle stages
are deterministic, isolated and exit-code-honest enough to be wrapped as nodes
by the future LangGraph orchestrator.

LangGraph patterns (State / Nodes / Edges) are modeled in PURE FUNCTIONS — the
`langgraph` library is NOT imported (reserved for the orchestrator itself).

Invoked by path (ADR-006: forge/tools/ is not a package):

    python3 forge/tools/meta-audit/lifecycle.py [--json] [--phase <name>]

Exit codes (the meta-audit obeys its own Node A rule):
    0  CLEAN or WARNING — fit for governance
    1  at least one phase BROKEN
    2  usage / environment error
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

# ADR-006 import shims: this module's own dir (for state/nodes) + tools/ (for _common).
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

from state import AuditState, PhaseAudit  # noqa: E402
import nodes  # noqa: E402
from _common import find_framework_root  # noqa: E402

# The lifecycle artifact map — the audit target. Each stage maps to the
# concrete artifacts the four metrics are evaluated against. Paths are
# framework-root-relative. (Stages are LLM prompts; the mechanically-checkable
# substance lives in their schema + support-tool members.)
LIFECYCLE_MAP: dict[str, dict] = {
    "enrich-us": {
        "skill": "forge/.playbooks/enrich-us.md",
        "schemas": [],
        "tools": ["forge/tools/init-state.py", "forge/tools/state-machine.py"],
    },
    "plan": {
        "skill": "forge/.playbooks/plan.md",
        "schemas": ["forge/schemas/plan.schema.yml"],
        "tools": ["forge/tools/state-machine.py", "forge/tools/validate-artifact.py"],
    },
    "develop": {
        "skill": "forge/.playbooks/develop.md",
        "schemas": ["forge/schemas/record.schema.yml",
                    "forge/schemas/deviation-taxonomy.schema.yml"],
        "tools": ["forge/tools/classify-deviation.py", "forge/tools/state-machine.py"],
    },
    "verify": {
        "skill": "forge/.playbooks/verify.md",
        "schemas": ["forge/schemas/verify.schema.yml",
                    "forge/schemas/checks.schema.yml"],
        "tools": ["forge/tools/validate-artifact.py", "forge/tools/state-machine.py",
                  "forge/tools/verify-checks.py"],
    },
    "commit": {
        "skill": "forge/.playbooks/commit.md",
        "schemas": [],
        "tools": ["forge/tools/state-machine.py"],
    },
    "update-docs": {
        "skill": "forge/.playbooks/update-docs.md",
        "schemas": [],
        "tools": ["forge/tools/state-machine.py"],
    },
    "cross-cutting": {
        "skill": None,
        "schemas": ["forge/schemas/state.schema.yml",
                    "forge/schemas/deviation-taxonomy.schema.yml",
                    "forge/schemas/checks.schema.yml"],
        "tools": ["forge/tools/state-machine.py"],
    },
}

_METRICS = ("idempotency_safe", "deterministic_output", "predictable_exit_code", "context_isolated")


def run_audit(framework_root: Path, only_phase: str | None = None) -> AuditState:
    """Build the initial state and thread it through the node pipeline."""
    fmap = LIFECYCLE_MAP if only_phase is None else {only_phase: LIFECYCLE_MAP[only_phase]}
    state = AuditState(
        started_at=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        framework_root=str(framework_root),
        phases={name: PhaseAudit() for name in fmap},
    )
    for node in nodes.PIPELINE:
        state = node(state, fmap)
    return state


def _cell(value) -> str:
    return {True: "ok", False: "FAIL", None: "n/a"}[value]


def render_report(state: AuditState) -> None:
    """Human-readable structured report to stdout."""
    print(f"== Meta-Audit: {state.subsystem} subsystem ==")
    print(f"   framework_root: {state.framework_root}")
    print(f"   started_at:     {state.started_at}\n")
    header = f"{'phase':<14} {'idem':>5} {'determ':>7} {'exit':>5} {'isol':>5}  status"
    print(header)
    print("-" * len(header))
    for name, audit in state.phases.items():
        print(f"{name:<14} "
              f"{_cell(audit.idempotency_safe):>5} "
              f"{_cell(audit.deterministic_output):>7} "
              f"{_cell(audit.predictable_exit_code):>5} "
              f"{_cell(audit.context_isolated):>5}  {audit.status}")

    findings = [(name, e) for name, a in state.phases.items() for e in a.errors]
    if findings:
        print("\nFindings:")
        for name, msg in findings:
            print(f"  [{name}] {msg}")

    worst = state.worst_status()
    print(f"\nOverall: {worst}  ->  exit {1 if worst == 'BROKEN' else 0}")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="meta-audit-lifecycle",
        description="Mechanical meta-audit of the lifecycle subsystem "
                    "(determinism / isolation / exit-code honesty).",
    )
    ap.add_argument("--json", action="store_true", help="Emit the AuditState as JSON.")
    ap.add_argument("--phase", choices=list(LIFECYCLE_MAP),
                    help="Audit a single lifecycle stage instead of all.")
    args = ap.parse_args()

    framework_root = find_framework_root()
    if framework_root is None:
        print("ERROR: framework root not found (no forge/schemas/ ancestor).", file=sys.stderr)
        return 2

    state = run_audit(framework_root, args.phase)

    if args.json:
        print(json.dumps(state.model_dump(), indent=2, default=str))
    else:
        render_report(state)

    return 1 if state.worst_status() == "BROKEN" else 0


if __name__ == "__main__":
    sys.exit(main())
