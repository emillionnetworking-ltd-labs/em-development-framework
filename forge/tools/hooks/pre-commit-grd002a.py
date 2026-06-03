#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""pre-commit-grd002a.py — git pre-commit hook blocking pre-squash SHA citations.

<TICKET-ID> (framework release layer — Proposal D Phase 3/3 FINAL). Closes the recurring
GRD-002a violation captured 6 consecutive Waves (subtypes 1+2+3+4):
- Subtype 1: pre-squash SHA in docs during work
- Subtype 2: prior record's SHA in new record
- Subtype 3: self-narration of own feature-branch commits
- Subtype 4: documenting a prior violation by reproducing the SHA literal

Mechanism: scans `git diff --cached` for short-SHA-like literals (7-12 hex
chars). For each candidate, checks reachability from origin/main via
`git merge-base --is-ancestor`. If NOT reachable, the SHA is pre-squash
and citing it is a violation — block the commit.

Pairs with <TICKET-ID> pre-bash-guard.py safety model:
- Fail-open on errors (git command failure, no origin/main configured) → exit 0
- Operator override via standard `git commit --no-verify` (git handles natively)
- Exit 0 (allow) on success; exit 1 (block) on real violations

Install via:
    python3 forge/tools/em-cli.py install-hook --hook=pre-commit-grd002a

OR manually:
    cp forge/tools/hooks/pre-commit-grd002a.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
"""

from __future__ import annotations

import re
import subprocess
import sys


SHA_RE = re.compile(r"\b[0-9a-f]{7,12}\b")

# Allowlist patterns: SHA-like literals in known-safe contexts.
# These are common false-positive sources (hash digests in test fixtures, etc.).
ALLOWLIST_CONTEXT_PATTERNS = (
    re.compile(r"sha256:[0-9a-f]{40,64}"),   # docker image digests
    re.compile(r"md5:[0-9a-f]{32}"),         # md5 hash refs
    re.compile(r"\"sha\":\s*\"[0-9a-f]+\""), # JSON sha fields (e.g. GitHub API)
    re.compile(r"#\s*example[^\n]*[0-9a-f]{7,12}", re.IGNORECASE),  # commented example SHAs
)


def _staged_diff() -> str:
    """Return git diff --cached for added lines only. Fail-open on git error."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--no-color"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return ""
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _origin_main_exists() -> bool:
    """Probe whether origin/main is resolvable. If not, the hook cannot
    meaningfully classify SHAs → fail-open at higher level (skip checks)."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/main"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _is_reachable(sha: str) -> bool:
    """Check if sha is an ancestor of origin/main. Returns False (block) for:
    - sha exists in repo but is not ancestor (pre-squash citation)
    - sha doesn't exist in repo at all (fabricated / non-resolving literal)
    Returns True (allow) only if sha exists AND is ancestor. Caller MUST
    have verified origin/main exists via _origin_main_exists() before calling."""
    try:
        # First check sha exists in repo at all
        r_exists = subprocess.run(
            ["git", "cat-file", "-e", sha],
            capture_output=True, text=True, timeout=5,
        )
        if r_exists.returncode != 0:
            return False  # sha does not resolve — suspicious, block
        # Then check ancestry
        r_anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
            capture_output=True, text=True, timeout=5,
        )
        return r_anc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return True  # Genuine env error → fail-open


def _is_allowlisted_context(line: str) -> bool:
    """Check if the line matches a known-safe context where SHA-like literals
    are not pre-squash citations (docker digests, JSON sha fields, etc.)."""
    for pat in ALLOWLIST_CONTEXT_PATTERNS:
        if pat.search(line):
            return True
    return False


def main() -> int:
    diff = _staged_diff()
    if not diff:
        return 0  # Nothing staged or git error → fail-open allow.

    # If origin/main cannot be resolved (e.g. brand-new repo, no remote),
    # we cannot meaningfully classify SHA reachability — fail-open allow.
    if not _origin_main_exists():
        return 0

    violations = []  # list of (file_path, line_text, sha)
    current_file = None

    for line in diff.split("\n"):
        # Track current file from diff headers
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        # This is an added line
        if _is_allowlisted_context(line):
            continue
        # Extract SHA candidates
        for sha_match in SHA_RE.finditer(line):
            sha = sha_match.group(0)
            # Heuristic: require at least one digit + at least one letter to avoid
            # pure-numeric IDs and pure-alpha words that match the regex by accident.
            if not (any(c.isdigit() for c in sha) and any(c.isalpha() for c in sha)):
                continue
            if _is_reachable(sha):
                continue
            violations.append((current_file or "<unknown>", line.lstrip("+").strip(), sha))

    if not violations:
        return 0

    print("ERROR: pre-commit-grd002a — pre-squash SHA citation(s) detected", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"Found {len(violations)} candidate violation(s) of the GRD-002a directive:", file=sys.stderr)
    print(file=sys.stderr)
    for path, line_text, sha in violations[:10]:  # cap output
        snippet = line_text[:120] + ("..." if len(line_text) > 120 else "")
        print(f"  {path}: cites {sha}", file=sys.stderr)
        print(f"    in line: {snippet}", file=sys.stderr)
    if len(violations) > 10:
        print(f"  ... and {len(violations) - 10} more", file=sys.stderr)
    print("", file=sys.stderr)
    print("These SHAs are NOT reachable from origin/main → pre-squash citations.", file=sys.stderr)
    print("Per the GRD-002a directive (forge/.playbooks/update-docs.md §subtypes 1-4):", file=sys.stderr)
    print("  - Use narrative paraphrase ('the Wave-N feature-branch pre-squash SHA')", file=sys.stderr)
    print("  - OR cite the merge_commit (which IS reachable from main)", file=sys.stderr)
    print("  - NEVER reproduce the SHA literal, even in lessons-learned narrative", file=sys.stderr)
    print("", file=sys.stderr)
    print("To override (operator discretion): git commit --no-verify", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
