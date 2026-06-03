#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""anti_rot_checker — repo-wide GRD (Graph Reference Drift) detector.

<TICKET-ID> (framework release layer). Mechanical CI gate. Six self-inflicted instances
across <TICKET-ID>/576/578/579/580 (twice) — caught at PR time from now on.

Detects 4 reference classes (see _anti_rot_checker.py docstring):
  R1 repo-path inline (optional ./ ../ prefix preserved)
  R2 markdown link with anchor stripping
  R3 file:line refs — always flagged
  R4 short-SHA candidates — 3-cascade post-filter + reachability check

Exit codes:
  0  no findings (CI clean)
  1  ≥1 finding (CI consumable — blocks merge)
  2  usage error / allowlist parse / repo not found
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root  # noqa: E402
from _anti_rot_checker import (  # noqa: E402
    SCAN_SCOPES, RotFinding,
    load_allowlist, scan_repo,
)


def _format_finding(f: RotFinding, repo_root: Path) -> str:
    try:
        rel = f.source_file.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel = str(f.source_file)
    lines = [
        f"[{f.kind.value.upper()}] {rel}:{f.line_no}",
        f"  Reference: {f.reference!r}",
    ]
    if f.target is not None:
        lines.append(f"  Resolved:  {f.target}")
    if f.suggestion:
        lines.append(f"  Suggestion: {f.suggestion}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="anti_rot_checker", description="Repo-wide GRD detector (<TICKET-ID>).")
    ap.add_argument("--scope", choices=list(SCAN_SCOPES.keys()), default="all")
    ap.add_argument("--allowlist", help="Path to allowlist YAML (default: forge/.anti-rot-allowlist.yml).")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-git", action="store_true", help="Skip R4 (SHA checks).")
    ap.add_argument("--strict", action="store_true", help="Reserved; equivalent to default.")
    args = ap.parse_args(argv)

    repo_root = find_framework_root()
    if repo_root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 2

    allowlist_path = Path(args.allowlist) if args.allowlist else (repo_root / "forge" / ".anti-rot-allowlist.yml")
    try:
        allowlist = load_allowlist(allowlist_path)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: failed to load allowlist {allowlist_path}: {e}", file=sys.stderr)
        return 2

    findings = scan_repo(repo_root, args.scope, allowlist, skip_git=args.no_git)

    if args.json:
        out = {
            "scope": args.scope,
            "findings_count": len(findings),
            "findings": [
                {
                    "kind": f.kind.value,
                    "source_file": str(f.source_file.resolve().relative_to(repo_root.resolve()))
                                   if f.source_file.resolve().is_relative_to(repo_root.resolve())
                                   else str(f.source_file),
                    "line_no": f.line_no,
                    "reference": f.reference,
                    "target": str(f.target) if f.target else None,
                    "suggestion": f.suggestion,
                }
                for f in findings
            ],
        }
        print(json.dumps(out, indent=2))
        return 1 if findings else 0

    if not args.quiet:
        print(f"== Anti-Rot Checker — {date.today().isoformat()} — scope={args.scope} ==")
        print()

    if not findings:
        if not args.quiet:
            print("Clean state. Zero findings.")
        return 0

    print(f"Findings: {len(findings)}\n")
    for f in findings:
        print(_format_finding(f, repo_root))
        print()

    if not args.quiet:
        print("To allowlist intentional findings: edit forge/.anti-rot-allowlist.yml")
        print("  (every entry needs expires_at — the allowlist is not a cemetery).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
