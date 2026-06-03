# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_anti_rot_checker.py — pure logic for /anti-rot-checker.

<TICKET-ID> (framework release layer). Promotes the GRD (Graph Reference Drift) anti-pattern
from behavioral discipline to mechanical CI gate. Six instances across
<TICKET-ID>/576/578/579/580 (twice) — finally getting mechanized.

Four reference classes detected, all from regex-based parsing (stdlib only):

  R1 — repo-path inline:
       `forge/<path>.<ext>` with OPTIONAL ./ ../ prefix preserved (enmienda #2).
       The prefix SIGNALS source-relative intent; the resolver respects it.

  R2 — markdown link `[text](path)`:
       Anchor suffix `#section` is stripped BEFORE existence check
       (enmienda #1). The anchor is a markdown render-time concern.

  R3 — file:line refs (`<file>:<N>`):
       Always flagged. framework release layer anti-rot directive: line numbers drift,
       use symbol names. No validation against current file content —
       the policy is dura.

  R4 — short-SHA detection (`[0-9a-f]{7,12}`):
       Three-cascade post-filter (enmienda #3) before any git interrogation:
         CHECK 1: mixed-alphabet rule (≥1 digit AND ≥1 letter)
         CHECK 2: hex-word blocklist (defaced, effaced, acceded, ...)
         CHECK 3: `git cat-file -e` (object exists in local DB)
       Final check: `git merge-base --is-ancestor sha origin/main` —
       catches the cloud-only SHA pattern (squashed PR intermediates).

Three-tier allowlist:
  - Syntactic: URLs, framework placeholders (`<TICKET>`, `<MODULE>`, ...),
    shell vars (`$JIRA_TOKEN`, `${CLAUDE_PROJECT_DIR}`).
  - Per-file: changelogs, ADRs, baselines (history doc, not active refs).
  - Per-finding: explicit YAML entries with mandatory `expires_at`.

Exit codes (set by the CLI shell — this lib produces RotFinding lists):
  0  clean (no findings after allowlist)
  1  ≥1 finding (CI consumable)
  2  usage error / allowlist parse / repo_root not found
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root  # noqa: E402


# ----------------------------------------------------------------------------
# Regex constants — Blueprint v2 with the 3 enmiendas integrated.
# ----------------------------------------------------------------------------

# R1 — repo-path inline.
# Captures `forge/<path>.<ext>` WITH any leading `./` or `../` prefix.
# The captured string is the FULL match including prefix so the resolver can
# disambiguate intent (repo-rooted vs source-relative). See enmienda #2.
R1 = re.compile(
    r'(?<![\w])'                                          # no word char before
    r'((?:\.\.?/)*forge/[\w./-]+\.(?:py|yml|md|mdc|yaml|json))'
    r'(?![\w/])'                                          # no word/slash after
)

# R2 — markdown link `[text](target)`. Second capture group is the target.
# Anchor stripping is performed in split_ref_and_anchor() (enmienda #1).
R2 = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

# R3 — file:line refs. Always flagged. Anti-rot directive (framework release layer).
R3 = re.compile(
    r'\b([\w./-]+\.(?:py|md|mdc|yml|yaml))(:\d+)\b'
)

# R4 — short-SHA candidates. Sintáctica solamente; post-filter en
# is_real_sha_candidate() descarta palabras hex-coincidence (enmienda #3).
R4 = re.compile(r'(?<![\w/])\b([0-9a-f]{7,12})\b(?![\w/])')


# ----------------------------------------------------------------------------
# Syntactic allowlists — applied BEFORE any expensive check.
# ----------------------------------------------------------------------------

ALLOWLIST_SYNTACTIC = [
    re.compile(r'^https?://'),                  # External URLs
    re.compile(r'^<[A-Za-z][A-Za-z_-]*>$'),     # Framework placeholders
    re.compile(r'^\$\{?[A-Z_]+(:[-=]?[^}]*)?\}?$'),  # Shell vars
    re.compile(r'^/tmp/'),                       # Tmp paths in examples
]

# Files where findings are silently ignored — historical narrative, not active refs.
FILE_ALLOWLIST = {
    "forge/specs/integration-state.md",
    "forge/.groundedness-baseline.yml",
    "forge/bypass-log.yml",
    "forge/.anti-rot-allowlist.yml",
}
FILE_ALLOWLIST_PREFIXES = (
    "forge/specs/adrs/",                          # ADRs explain historical refactors
    ".lifecycle/artifacts/",                      # Historical lifecycle artifacts
)

# Hex-coincidence words that pass R4's regex but are NOT git SHAs.
# Mostly English words composed only of [0-9a-f]. Extensible.
HEX_WORD_BLOCKLIST = {
    "defaced", "effaced", "acceded", "deceded", "addable", "abaaba",
    "cabbed", "decadal", "decided", "deceived", "facaded", "decaf",
    "ace", "ade", "bad", "bed", "bee", "cab", "dab", "dad", "deed",
    "fed", "fee", "face", "fade", "cafe", "deaf", "dead", "bead",
    "feed", "beef", "babe", "decade", "facade",
}


# ----------------------------------------------------------------------------
# Data types
# ----------------------------------------------------------------------------

class IssueKind(Enum):
    BROKEN_PATH = "broken-path"
    BROKEN_MD_LINK = "broken-md-link"
    FILE_LINE_REF = "file-line-ref"
    UNREACHABLE_SHA = "unreachable-sha"
    ABSOLUTE_PATH_FLAGGED = "absolute-path-flagged"


@dataclass
class ResolveResult:
    target: Path
    exists: bool
    intent: str           # "repo-rooted" | "source-relative" | "absolute-flagged"
    anchor: Optional[str] = None


@dataclass
class RotFinding:
    kind: IssueKind
    source_file: Path
    line_no: int
    reference: str
    target: Optional[Path] = None
    suggestion: str = ""


# ----------------------------------------------------------------------------
# Enmienda #1 — anchor stripping
# ----------------------------------------------------------------------------

def split_ref_and_anchor(raw: str) -> tuple[str, Optional[str]]:
    """<TICKET-ID> enmienda #1. A markdown link target may carry `#anchor`.

    The file-on-disk check must ignore the anchor — only the path part is
    a filesystem ref. Anchor is a markdown render-time concern.

    Returns (path_only, anchor_or_None).
    """
    if "#" not in raw:
        return raw, None
    path, anchor = raw.split("#", 1)
    return path, anchor or None


# ----------------------------------------------------------------------------
# Enmienda #2 — resolver with intent preservation
# ----------------------------------------------------------------------------

def resolve_ref(repo_root: Path, source_file: Path, raw_ref: str) -> ResolveResult:
    """<TICKET-ID> enmienda #2. Distinguish repo-rooted vs source-relative.

    Resolution rules:
      - Starts with `./` or `../` → source-relative (operator's intent preserved)
      - Starts with `/` → absolute-flagged (always flagged in markdown)
      - Otherwise → repo-rooted
    """
    path_part, anchor = split_ref_and_anchor(raw_ref)

    if path_part.startswith("/"):
        return ResolveResult(
            target=Path(path_part), exists=False,
            intent="absolute-flagged", anchor=anchor,
        )
    if path_part.startswith("./") or path_part.startswith("../") or path_part.startswith("../../"):
        target = (source_file.parent / path_part).resolve()
        intent = "source-relative"
    else:
        target = (repo_root / path_part).resolve()
        intent = "repo-rooted"

    return ResolveResult(
        target=target,
        exists=target.is_file() or target.is_dir(),
        intent=intent,
        anchor=anchor,
    )


# ----------------------------------------------------------------------------
# Enmienda #3 — SHA semantic post-filter (3-cascade)
# ----------------------------------------------------------------------------

def is_real_sha_candidate(token: str, repo_root: Path) -> tuple[bool, str]:
    """<TICKET-ID> enmienda #3. Three checks in cascade — cheap → expensive.

    Rejects:
      CHECK 1: words that are all-letters (defaced) or all-digits (1234567)
      CHECK 2: known hex-coincidence words (face, deaf, etc.)
      CHECK 3: hashes git doesn't recognize as objects locally

    Returns (is_candidate, reason). True = worth asking reachability;
    False = stop short, NOT a SHA.
    """
    # CHECK 1 — mixed alphabet rule
    has_digit = any(c.isdigit() for c in token)
    has_letter = any(c.isalpha() for c in token)
    if not (has_digit and has_letter):
        return False, f"mixed-alphabet-rule (digits={has_digit}, letters={has_letter})"

    # CHECK 2 — hex-word blocklist (case-insensitive)
    if token.lower() in HEX_WORD_BLOCKLIST:
        return False, f"hex-word-blocklist (token={token!r})"

    # CHECK 3 — git knows this object?
    try:
        r = subprocess.run(
            ["git", "cat-file", "-e", token],
            cwd=str(repo_root), capture_output=True, timeout=2,
        )
        if r.returncode != 0:
            return False, "git-object-not-found-locally"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "git-unavailable"

    return True, "real-sha-candidate"


def sha_is_reachable(sha: str, repo_root: Path) -> bool:
    """Final check — called only after is_real_sha_candidate returns True.
    `git merge-base --is-ancestor sha origin/main` returns 0 if reachable."""
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
            cwd=str(repo_root), capture_output=True, timeout=2,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True  # fail-open: prefer false negatives over noise


# ----------------------------------------------------------------------------
# Allowlist mechanism
# ----------------------------------------------------------------------------

def load_allowlist(path: Path) -> dict:
    """Load the YAML allowlist. Rejects (raises ValueError) if any entry
    has an expired `expires_at` date."""
    if not path.is_file():
        return {"version": "1.0", "allowlist": []}
    with path.open() as fh:
        data = yaml.safe_load(fh)
    today = date.today()
    for entry in data.get("allowlist", []):
        exp = entry.get("expires_at")
        if exp is None:
            continue  # schema would have caught
        if isinstance(exp, str):
            exp = date.fromisoformat(exp)
        if exp < today:
            raise ValueError(
                f"anti-rot allowlist entry EXPIRED on {exp} for {entry.get('file')!r}: "
                f"{entry.get('reason', '<no-reason>')[:80]}. "
                f"Re-evaluate and either renew the expiration or remove the entry."
            )
    return data


def is_syntactic_allowlist(ref: str) -> bool:
    """True if the ref matches any syntactic allowlist pattern."""
    for pat in ALLOWLIST_SYNTACTIC:
        if pat.match(ref):
            return True
    return False


def is_file_allowlisted(source_file: Path, repo_root: Path) -> bool:
    """True if findings in this file are silently ignored."""
    try:
        rel = source_file.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return False
    if rel in FILE_ALLOWLIST:
        return True
    for prefix in FILE_ALLOWLIST_PREFIXES:
        if rel.startswith(prefix):
            return True
    return False


def matches_entry_allowlist(finding: RotFinding, allowlist: dict, repo_root: Path) -> bool:
    """True if a finding matches an explicit allowlist entry."""
    try:
        rel = finding.source_file.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return False
    for entry in allowlist.get("allowlist", []):
        entry_file = entry.get("file", "")
        # file or dir prefix match
        if not (rel == entry_file or rel.startswith(entry_file)):
            continue
        # optional line_range filter
        lr = entry.get("line_range")
        if lr and not (lr[0] <= finding.line_no <= lr[1]):
            continue
        # optional kind filter
        kf = entry.get("kind")
        if kf and finding.kind.value != kf:
            continue
        # optional regex pattern filter
        pat = entry.get("pattern")
        if pat and not re.search(pat, finding.reference):
            continue
        return True
    return False


# ----------------------------------------------------------------------------
# Scanning
# ----------------------------------------------------------------------------

# Hard exclusions — directories NEVER walked by the checker.
EXCLUDE_DIRS = (
    ".lifecycle/archive/",
    "forge/_parked/",
    ".lifecycle/artifacts/",  # historical artifacts per framework release layer directive
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".github/",  # workflows can carry historical refs; out of scope
)

SCAN_SCOPES = {
    "playbooks":  ["forge/.playbooks/*.md"],
    "agents":     ["forge/.agents/*.md"],
    "specs":      ["forge/specs/*.mdc", "forge/specs/*.md"],
    "schemas":    ["forge/schemas/*.yml"],
    "root-docs":  ["README.md", "ARCHITECTURE.md", "COMMANDS_REFERENCE.md",
                   "INSTALL.md", "CLAUDE.md", "AGENTS.md", "codex.md", "GEMINI.md"],
}
SCAN_SCOPES["all"] = sum(SCAN_SCOPES.values(), [])


def _under_excluded_dir(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return True  # outside repo = excluded
    return any(rel.startswith(d) for d in EXCLUDE_DIRS)


def discover_files(repo_root: Path, scope: str) -> list[Path]:
    """Return absolute paths matching the scope globs, excluding the EXCLUDE_DIRS."""
    if scope not in SCAN_SCOPES:
        raise ValueError(f"unknown scope: {scope!r}")
    found: set[Path] = set()
    for pattern in SCAN_SCOPES[scope]:
        for p in repo_root.glob(pattern):
            if p.is_file() and not _under_excluded_dir(p, repo_root):
                found.add(p.resolve())
    return sorted(found)


def scan_file(source: Path, repo_root: Path, *, skip_git: bool = False) -> list[RotFinding]:
    """Scan a single file for all 4 reference classes. Return findings."""
    findings: list[RotFinding] = []
    text = source.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        # R1 — repo-path inline
        for m in R1.finditer(line):
            ref = m.group(1)
            if is_syntactic_allowlist(ref):
                continue
            res = resolve_ref(repo_root, source, ref)
            if res.intent == "absolute-flagged":
                findings.append(RotFinding(
                    kind=IssueKind.ABSOLUTE_PATH_FLAGGED,
                    source_file=source, line_no=line_no, reference=ref,
                    target=res.target,
                    suggestion="Absolute paths in markdown leak environment; parametrize via env var.",
                ))
            elif not res.exists:
                findings.append(RotFinding(
                    kind=IssueKind.BROKEN_PATH,
                    source_file=source, line_no=line_no, reference=ref,
                    target=res.target,
                    suggestion=f"Target not found ({res.intent}). Verify rename history (e.g., framework release layer .commands→.playbooks).",
                ))

        # R2 — markdown link [text](target)
        for m in R2.finditer(line):
            ref = m.group(2)
            if is_syntactic_allowlist(ref):
                continue
            res = resolve_ref(repo_root, source, ref)
            if res.intent == "absolute-flagged":
                findings.append(RotFinding(
                    kind=IssueKind.ABSOLUTE_PATH_FLAGGED,
                    source_file=source, line_no=line_no, reference=ref,
                    target=res.target,
                    suggestion="Absolute path in markdown link; use repo-relative or external URL.",
                ))
            elif not res.exists:
                findings.append(RotFinding(
                    kind=IssueKind.BROKEN_MD_LINK,
                    source_file=source, line_no=line_no, reference=ref,
                    target=res.target,
                    suggestion=f"Link target missing ({res.intent}).",
                ))

        # R3 — file:line refs (always flagged)
        for m in R3.finditer(line):
            file_part = m.group(1)
            line_suffix = m.group(2)
            findings.append(RotFinding(
                kind=IssueKind.FILE_LINE_REF,
                source_file=source, line_no=line_no,
                reference=f"{file_part}{line_suffix}",
                suggestion=f"Drop {line_suffix!r}; use symbol name (anti-rot directive framework release layer).",
            ))

        # R4 — short-SHA (post-filter cascade)
        if not skip_git:
            for m in R4.finditer(line):
                token = m.group(1)
                is_cand, reason = is_real_sha_candidate(token, repo_root)
                if not is_cand:
                    continue
                if not sha_is_reachable(token, repo_root):
                    findings.append(RotFinding(
                        kind=IssueKind.UNREACHABLE_SHA,
                        source_file=source, line_no=line_no, reference=token,
                        suggestion=f"SHA {token[:7]} not reachable from origin/main "
                                   f"(likely pre-squash intermediate). De-hash or allowlist.",
                    ))
    return findings


def scan_repo(repo_root: Path, scope: str, allowlist: dict, *,
              skip_git: bool = False) -> list[RotFinding]:
    """Walk the repo for the given scope. Apply per-file + per-entry allowlists."""
    all_findings: list[RotFinding] = []
    for source in discover_files(repo_root, scope):
        if is_file_allowlisted(source, repo_root):
            continue
        file_findings = scan_file(source, repo_root, skip_git=skip_git)
        for f in file_findings:
            if not matches_entry_allowlist(f, allowlist, repo_root):
                all_findings.append(f)
    return all_findings
