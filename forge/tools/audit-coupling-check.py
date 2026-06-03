#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""audit-coupling-check — enforce workflow-standards.mdc §22.3 mechanically.

<TICKET-ID> / §22.7.2. Stdlib-only.

For each audit finding (findings/[GF]<N>.md) with
  disposition ∈ {acknowledged-deferred, open}
  AND severity ∈ {CRITICAL, HIGH}
verify that:
  - frontmatter.registry_entry is present
  - pending-improvements.yml has an entry with id == that value.

Flags:
  --audit-root <path>     default: <framework_root>/.lifecycle/artifacts/
  --registry-path <path>  default: <framework_root>/forge/registers/pending-improvements.yml

Note: DEFAULT_AUDIT_ROOT_REL is `.lifecycle/artifacts` (updated <TICKET-ID>
from prior `.lifecycle/changes` left stale after <TICKET-ID> T5 rename).
  --json                  machine-readable output

Exit codes:
  0  no violations
  1  ≥1 violation (itemized stderr)
  2  usage / parse error
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install --user pyyaml", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root  # noqa: E402

REGISTRY_REL_PATH = "forge/registers/pending-improvements.yml"
DEFAULT_AUDIT_ROOT_REL = ".lifecycle/artifacts"

# Severity threshold per §22.3: only these two require coupling.
GATED_SEVERITIES = {"CRITICAL", "HIGH"}
# Dispositions that trigger the coupling rule.
OPEN_DISPOSITIONS = {"acknowledged-deferred", "open"}

# Frontmatter delimiter pattern.
FRONTMATTER_RE = re.compile(r'\A---\r?\n(.*?)\r?\n---\r?\n', re.DOTALL)


def _parse_frontmatter(text: str) -> dict | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    return fm


def _walk_findings(audit_root: Path):
    """Yield (path, frontmatter) for every finding-like markdown file."""
    # Pattern 1: <audit-root>/<module>/audits/<folder>/findings/[GF]<N>.md
    for p in audit_root.glob("*/audits/*/findings/[GF][0-9]*.md"):
        if p.is_file():
            fm = _parse_frontmatter(p.read_text(encoding='utf-8'))
            if fm:
                yield p, fm
    # Pattern 2 (legacy): <audit-root>/<module>/audit/audit-*/findings/[GF]<N>.md
    for p in audit_root.glob("*/audit/audit-*/findings/[GF][0-9]*.md"):
        if p.is_file():
            fm = _parse_frontmatter(p.read_text(encoding='utf-8'))
            if fm:
                yield p, fm


def _load_registry_ids(registry_path: Path) -> set[str]:
    if not registry_path.is_file():
        return set()
    with registry_path.open() as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        return set()
    return {e.get("id") for e in data.get("entries", []) if isinstance(e, dict) and e.get("id")}


def check_coupling(audit_root: Path, registry_path: Path) -> dict:
    registry_ids = _load_registry_ids(registry_path)

    findings_checked: list[dict] = []
    violations: list[dict] = []

    for path, fm in _walk_findings(audit_root):
        severity = fm.get("severity")
        disposition = fm.get("disposition")
        finding_id = fm.get("finding_id")
        if not severity or not disposition:
            continue
        if severity not in GATED_SEVERITIES:
            continue
        if disposition not in OPEN_DISPOSITIONS:
            continue

        entry = {
            "file": str(path),
            "finding_id": finding_id,
            "severity": severity,
            "disposition": disposition,
            "registry_entry": fm.get("registry_entry"),
        }
        findings_checked.append(entry)

        reg = fm.get("registry_entry")
        if not reg:
            violations.append({**entry,
                               "violation": "missing frontmatter.registry_entry"})
            continue
        if reg not in registry_ids:
            violations.append({**entry,
                               "violation": f"registry_entry '{reg}' not found in pending-improvements.yml"})

    return {
        "audit_root": str(audit_root),
        "registry_path": str(registry_path),
        "gated_count": len(findings_checked),
        "violations": violations,
        "verdict": "PASS" if not violations else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="audit-coupling-check",
        description="Enforce workflow-standards.mdc §22.3 coupling rule (<TICKET-ID>).",
    )
    ap.add_argument("--audit-root", help="Override audit root (default: <framework_root>/.lifecycle/artifacts/).")
    ap.add_argument("--registry-path", help="Override pending-improvements.yml path.")
    ap.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = ap.parse_args()

    framework_root = find_framework_root()
    if framework_root is None and (args.audit_root is None or args.registry_path is None):
        print("ERROR: framework root not found; pass --audit-root and --registry-path", file=sys.stderr)
        return 2

    audit_root = (Path(args.audit_root)
                  if args.audit_root
                  else framework_root / DEFAULT_AUDIT_ROOT_REL)
    registry_path = (Path(args.registry_path)
                     if args.registry_path
                     else framework_root / REGISTRY_REL_PATH)

    if not audit_root.is_dir():
        print(f"ERROR: audit root not found: {audit_root}", file=sys.stderr)
        return 2

    result = check_coupling(audit_root, registry_path)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"== Audit Coupling Check (§22.3) ==")
        print(f"   audit_root:    {result['audit_root']}")
        print(f"   registry:      {result['registry_path']}")
        print(f"   gated count:   {result['gated_count']}  "
              f"(severity ∈ CRITICAL/HIGH AND disposition ∈ acknowledged-deferred/open)")
        print(f"   violations:    {len(result['violations'])}")
        if result["violations"]:
            print()
            print("Violations:", file=sys.stderr)
            for v in result["violations"]:
                print(f"  - [{v.get('finding_id', '?')}] {v['file']}", file=sys.stderr)
                print(f"      {v['violation']}", file=sys.stderr)

    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
