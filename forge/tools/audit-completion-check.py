#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""audit-completion-check — verify post-audit invariants.

<TICKET-ID>. Stdlib-only.

Given an audit folder (product-module audit), verify two completion invariants:
  (i)   at least 1 phase report present (digit-prefix or fase-N prefix)
  (ii)  an index/summary present (00-index.md OR 00-summary.md)

Flags:
  <audit-folder>     required positional
  --json             machine-readable output
  --strict           require findings/ subdir too (relaxed default)

Exit codes:
  0  complete
  1  incomplete (itemized failures on stderr; details on stdout if --json)
  2  usage / parse error
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Folder name patterns:
#   new full-audit:   <YYYY-MM-DD>-full-audit  or <YYYY-MM-DD>-<scope>
#   legacy:           audit-<YYYY-MM-DD>T<HH-MM>
NEW_FOLDER_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})-([a-z][a-z0-9-]*)$')
LEGACY_FOLDER_RE = re.compile(r'^audit-(\d{4}-\d{2}-\d{2})T\d{2}-\d{2}$')

# Phase report patterns:
#   new:    NN-name.md  (e.g. 05-security-and-compliance.md)
#   legacy: fase-N-name.md  (e.g. fase-3-security-auth.md)
PHASE_REPORT_RE = re.compile(r'^(\d{2}-[a-z][a-z0-9-]*|fase-\d+[a-z0-9-]*)\.md$')


def _extract_audit_date(folder_name: str) -> str | None:
    """Return iso_date parsed from the folder name, or None on parse failure."""
    m = NEW_FOLDER_RE.match(folder_name)
    if m:
        return m.group(1)
    m = LEGACY_FOLDER_RE.match(folder_name)
    if m:
        return m.group(1)
    return None


def check_audit_folder(folder: Path, strict: bool = False) -> dict:
    """Return a dict with verdict, audit_date, and per-check status."""
    result = {
        "audit_folder": str(folder),
        "audit_date": None,
        "checks": {},
        "failures": [],
    }

    if not folder.is_dir():
        result["failures"].append(f"folder does not exist: {folder}")
        result["verdict"] = "ERROR"
        return result

    audit_date = _extract_audit_date(folder.name)
    result["audit_date"] = audit_date
    if audit_date is None:
        result["failures"].append(
            f"cannot parse audit_date from folder name '{folder.name}' "
            f"(expected <YYYY-MM-DD>-<scope> or audit-<YYYY-MM-DD>T<HH-MM>)"
        )
        result["verdict"] = "ERROR"
        return result

    # Check (i): ≥1 phase report (NN-name.md or fase-N-name.md).
    body_files = [p.name for p in folder.iterdir()
                  if p.is_file() and PHASE_REPORT_RE.match(p.name)]
    has_body = len(body_files) > 0
    result["checks"]["content_body"] = {
        "ok": has_body,
        "kind": "phase reports",
        "count": len(body_files),
    }
    if not has_body:
        result["failures"].append("no phase reports found in audit folder")

    # Check (ii): 00-index.md OR 00-summary.md present.
    has_index = (folder / "00-index.md").is_file()
    has_summary = (folder / "00-summary.md").is_file()
    has_either = has_index or has_summary
    result["checks"]["index_or_summary"] = {
        "ok": has_either,
        "found": "00-index.md" if has_index else ("00-summary.md" if has_summary else None),
    }
    if not has_either:
        result["failures"].append("missing 00-index.md or 00-summary.md in audit folder")

    # Optional --strict: require findings/ subdir to exist (relaxed by default
    # because findings/ is new-convention going forward; legacy folders may not
    # have it).
    if strict:
        findings_dir = folder / "findings"
        findings_ok = findings_dir.is_dir()
        result["checks"]["findings_dir"] = {"ok": findings_ok}
        if not findings_ok:
            result["failures"].append("--strict: findings/ subdir missing")

    result["verdict"] = "PASS" if not result["failures"] else "FAIL"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="audit-completion-check",
        description="Verify post-audit completion invariants (<TICKET-ID>).",
    )
    ap.add_argument("folder", help="Path to the audit folder.")
    ap.add_argument("--json", action="store_true", help="Machine-readable output.")
    ap.add_argument("--strict", action="store_true",
                    help="Also require findings/ subdir.")
    args = ap.parse_args()

    folder = Path(args.folder).resolve()
    result = check_audit_folder(folder, strict=args.strict)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"== Audit Completion Check — {folder.name} ==")
        print(f"   audit_date: {result['audit_date']}")
        for name, chk in result["checks"].items():
            mark = "OK" if chk.get("ok") else "FAIL"
            print(f"   [{mark}] {name}: {chk}")
        if result["failures"]:
            print("\nFailures:", file=sys.stderr)
            for f in result["failures"]:
                print(f"  - {f}", file=sys.stderr)

    if result["verdict"] == "ERROR":
        return 2
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
