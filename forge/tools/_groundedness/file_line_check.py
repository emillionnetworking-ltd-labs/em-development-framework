# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""GRD-003 — file:line reference check via filesystem.

Paths resolve relative to framework_root. Absolute paths are skipped.
"""

import re
from pathlib import Path

from .types import Violation

FILE_LINE_RE = re.compile(r"([a-zA-Z_./-]+\.(?:py|md|ts|yml|yaml|sh|mdc)):(\d+)\b")


def _line_of_offset(body: str, offset: int) -> int:
    return body[:offset].count("\n") + 1


def check(
    parsed: dict,
    body: str,
    file_path: Path,
    framework_root: Path,
    allowlist: dict,
    offline: bool = False,
) -> list[Violation]:
    allowlist_refs = set(allowlist.get("file_line_refs", []))
    violations: list[Violation] = []
    seen: set[str] = set()

    for m in FILE_LINE_RE.finditer(body):
        path_str = m.group(1)
        line_no = int(m.group(2))
        ref_literal = f"{path_str}:{line_no}"
        if ref_literal in allowlist_refs or ref_literal in seen:
            continue
        seen.add(ref_literal)

        if path_str.startswith("/"):
            continue  # absolute paths not in repo scope

        target = framework_root / path_str
        line_in_body = _line_of_offset(body, m.start())

        if not target.is_file():
            violations.append(
                Violation(
                    rule_id="GRD-003",
                    severity="WARN",
                    file=str(file_path),
                    line=line_in_body,
                    ref=ref_literal,
                    message=f"File {path_str} not found in repo.",
                )
            )
            continue

        try:
            with target.open(encoding="utf-8", errors="replace") as fh:
                total_lines = sum(1 for _ in fh)
        except OSError:
            continue

        if line_no > total_lines:
            violations.append(
                Violation(
                    rule_id="GRD-003",
                    severity="WARN",
                    file=str(file_path),
                    line=line_in_body,
                    ref=ref_literal,
                    message=f"Line {line_no} out of range; {path_str} has {total_lines} lines.",
                )
            )
    return violations
