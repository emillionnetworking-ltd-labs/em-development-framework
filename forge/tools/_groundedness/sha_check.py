# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""GRD-002a/b — commit SHA existence + ambiguity check via `git cat-file -e`.

Two-channel extraction: frontmatter (merge_commit + commits[].hash) + body backticks.

Cross-repo nuance: only framework-repo SHAs are validated. If the artifact's
frontmatter module != 'framework' the check is skipped entirely — SHA refs in
non-framework records typically point at em-ecosystem-code commits which this
process cannot reach from framework_root.
"""

import re
import subprocess
from pathlib import Path

from .types import Violation

SHA_BODY_RE = re.compile(r"`([0-9a-f]{7,40})`")


def _is_framework_module(parsed: dict) -> bool:
    fm = parsed.get("frontmatter", {}) if isinstance(parsed, dict) else {}
    return isinstance(fm, dict) and fm.get("module") == "framework"


def _collect_frontmatter_shas(parsed: dict) -> list[tuple[str, int | None]]:
    """Returns list of (sha, line) — line is None for frontmatter (no body offset)."""
    out: list[tuple[str, int | None]] = []
    fm = parsed.get("frontmatter", {}) if isinstance(parsed, dict) else {}
    if not isinstance(fm, dict):
        return out
    mc = fm.get("merge_commit")
    if isinstance(mc, str) and re.fullmatch(r"[0-9a-f]{7,40}", mc):
        out.append((mc, None))
    commits = fm.get("commits", [])
    if isinstance(commits, list):
        for c in commits:
            if isinstance(c, dict):
                h = c.get("hash")
                if isinstance(h, str) and re.fullmatch(r"[0-9a-f]{7,40}", h):
                    out.append((h, None))
    return out


def _line_of_offset(body: str, offset: int) -> int:
    return body[:offset].count("\n") + 1


def _git_cat_file(framework_root: Path, sha: str) -> str:
    """Returns 'exists' | 'unknown' | 'ambiguous' | 'error'."""
    try:
        r = subprocess.run(
            ["git", "-C", str(framework_root), "cat-file", "-e", sha],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "error"
    if r.returncode == 0:
        return "exists"
    stderr = (r.stderr or "").lower()
    if "ambiguous" in stderr:
        return "ambiguous"
    # `git cat-file -e <fully-resolved-but-missing>` returns rc=1 with empty stderr.
    # `git cat-file -e <bad-format>` returns rc=128 with "Not a valid object name".
    # Treat both as 'unknown'; only true subprocess failures fall through to 'error'.
    if r.returncode in (1, 128):
        return "unknown"
    return "error"


def check(
    parsed: dict,
    body: str,
    file_path: Path,
    framework_root: Path,
    allowlist: dict,
    offline: bool = False,
) -> list[Violation]:
    if not _is_framework_module(parsed):
        return []

    allowlist_refs = set(allowlist.get("sha_refs", []))
    violations: list[Violation] = []
    seen: set[str] = set()

    # Frontmatter SHAs (no body line number)
    for sha, _ in _collect_frontmatter_shas(parsed):
        if sha in allowlist_refs or sha in seen:
            continue
        seen.add(sha)
        status = _git_cat_file(framework_root, sha)
        if status == "unknown":
            violations.append(
                Violation(
                    rule_id="GRD-002a",
                    severity="WARN",
                    file=str(file_path),
                    line=None,
                    ref=sha,
                    message=f"SHA {sha} does not exist in framework repo.",
                )
            )
        elif status == "ambiguous":
            violations.append(
                Violation(
                    rule_id="GRD-002b",
                    severity="WARN",
                    file=str(file_path),
                    line=None,
                    ref=sha,
                    message=f"SHA {sha} is ambiguous (matches multiple commits). Use a longer prefix.",
                )
            )

    # Body SHAs (backtick-wrapped)
    for m in SHA_BODY_RE.finditer(body):
        sha = m.group(1)
        if sha in allowlist_refs or sha in seen:
            continue
        seen.add(sha)
        status = _git_cat_file(framework_root, sha)
        line = _line_of_offset(body, m.start())
        if status == "unknown":
            violations.append(
                Violation(
                    rule_id="GRD-002a",
                    severity="WARN",
                    file=str(file_path),
                    line=line,
                    ref=sha,
                    message=f"SHA {sha} does not exist in framework repo.",
                )
            )
        elif status == "ambiguous":
            violations.append(
                Violation(
                    rule_id="GRD-002b",
                    severity="WARN",
                    file=str(file_path),
                    line=line,
                    ref=sha,
                    message=f"SHA {sha} is ambiguous (matches multiple commits). Use a longer prefix.",
                )
            )
    return violations
