# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Groundedness validation package (<TICKET-ID> / Phase 3.5).

Closes audit gap G3 (CRITICAL) from 2026-05-16 full audit. Provides three
content-correctness checks complementing structural schema validation:

  - GRD-001  PR existence (via `gh pr view`)
  - GRD-002a SHA unknown
  - GRD-002b SHA ambiguous (short prefix matches multiple commits)
  - GRD-003  file:line existence (filesystem)

Entry point: run_groundedness(parsed, body, file_path, framework_root, allowlist, offline)
"""

from pathlib import Path
from typing import Optional

import yaml

from . import pr_check, sha_check, file_line_check
from .types import Violation, Severity, RuleId  # re-export

__all__ = [
    "run_groundedness",
    "load_allowlist",
    "Violation",
    "Severity",
    "RuleId",
]


def run_groundedness(
    parsed: dict,
    body: str,
    file_path: Path,
    framework_root: Path,
    allowlist: dict,
    offline: bool = False,
) -> tuple[list[Violation], list[str]]:
    """Run all three groundedness checks. Returns (violations, rules_run)."""
    violations: list[Violation] = []
    rules_run: list[str] = []
    for module, rule_label in [
        (pr_check, "PR"),
        (sha_check, "SHA"),
        (file_line_check, "FileLine"),
    ]:
        rules_run.append(rule_label)
        violations.extend(
            module.check(parsed, body, file_path, framework_root, allowlist, offline)
        )
    return violations, rules_run


def load_allowlist(path_or_root: Path) -> dict:
    """Load forge/.groundedness-allowlist.yml.

    Args:
        path_or_root: either the framework root (we'll look up the conventional
            path) or an explicit file path.

    Returns:
        dict with three list keys: pr_refs, sha_refs, file_line_refs.
        Missing file or parse errors collapse to empty defaults — never raises.
    """
    if path_or_root.is_file():
        allowlist_path = path_or_root
    else:
        allowlist_path = path_or_root / "forge" / ".groundedness-allowlist.yml"

    empty = {"pr_refs": [], "sha_refs": [], "file_line_refs": []}
    if not allowlist_path.is_file():
        return empty

    try:
        with allowlist_path.open() as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError:
        return empty
    if not isinstance(data, dict):
        return empty

    out = dict(empty)
    for key in out:
        v = data.get(key, [])
        if isinstance(v, list):
            out[key] = [str(item) for item in v]
    return out
