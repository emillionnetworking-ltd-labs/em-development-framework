# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""GRD-001 — PR existence check via `gh pr view` with persistent cache.

Cache: ~/.cache/em-development-framework/gh-pr-cache.json (XDG-compatible).
TTL: 24h positive, 1h negative.

Cross-repo: module=='framework' → em-development-framework; else em-ecosystem-code.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from .types import Violation

PR_RE = re.compile(r"(?:PR\s*#|/pull/)(\d+)\b")

FRAMEWORK_REPO = "emillionnetworking-ltd-labs/em-development-framework"
ECOSYSTEM_REPO = "emillionnetworking-ltd-labs/em-ecosystem-code"

POSITIVE_TTL_SECONDS = 24 * 60 * 60
NEGATIVE_TTL_SECONDS = 60 * 60


def _cache_path() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "em-development-framework" / "gh-pr-cache.json"


def _load_cache() -> dict:
    p = _cache_path()
    if not p.is_file():
        return {}
    try:
        with p.open() as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    p = _cache_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with tmp.open("w") as fh:
            json.dump(cache, fh, indent=2)
        tmp.replace(p)
    except OSError:
        pass  # cache write failures are non-fatal


def _resolve_repo(parsed: dict) -> str:
    fm = parsed.get("frontmatter", {}) if isinstance(parsed, dict) else {}
    module = fm.get("module") if isinstance(fm, dict) else None
    return FRAMEWORK_REPO if module == "framework" else ECOSYSTEM_REPO


def _is_cache_fresh(entry: dict) -> bool:
    age = time.time() - entry.get("checked_at_epoch", 0)
    ttl = POSITIVE_TTL_SECONDS if entry.get("exists") else NEGATIVE_TTL_SECONDS
    return age < ttl


def _gh_pr_view(repo: str, pr_number: str) -> Optional[bool]:
    """Returns True (exists), False (not found), or None (gh failure / no network)."""
    try:
        r = subprocess.run(
            ["gh", "pr", "view", pr_number, "--repo", repo, "--json", "number"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode == 0:
        return True
    if "Could not resolve to a PullRequest" in (r.stderr or ""):
        return False
    return None


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
    repo = _resolve_repo(parsed)
    allowlist_refs = set(allowlist.get("pr_refs", []))

    cache = _load_cache()
    cache_dirty = False
    seen: set[tuple[str, str]] = set()
    violations: list[Violation] = []

    for m in PR_RE.finditer(body):
        pr_number = m.group(1)
        ref_literal = f"#{pr_number}"
        if ref_literal in allowlist_refs:
            continue

        key = (repo, pr_number)
        if key in seen:
            continue
        seen.add(key)

        entry = cache.get(repo, {}).get(pr_number)
        if entry and _is_cache_fresh(entry):
            exists = entry.get("exists")
        elif offline:
            # Skip without violation when we can't verify
            continue
        else:
            result = _gh_pr_view(repo, pr_number)
            if result is None:
                # gh failure — do not generate a false violation
                continue
            exists = result
            cache.setdefault(repo, {})[pr_number] = {
                "checked_at_epoch": time.time(),
                "exists": exists,
            }
            cache_dirty = True

        if not exists:
            line = _line_of_offset(body, m.start())
            violations.append(
                Violation(
                    rule_id="GRD-001",
                    severity="WARN",
                    file=str(file_path),
                    line=line,
                    ref=ref_literal,
                    message=(
                        f"PR {ref_literal} not found in {repo}. "
                        f"Confirm number or add to forge/.groundedness-allowlist.yml."
                    ),
                )
            )

    if cache_dirty:
        _save_cache(cache)
    return violations
