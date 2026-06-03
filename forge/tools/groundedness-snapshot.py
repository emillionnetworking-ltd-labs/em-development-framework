#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""groundedness-snapshot — manage the corpus baseline of known groundedness violations.

<TICKET-ID> / workflow-standards.mdc §18.3.2. Companion to `validate-artifact.py --strict-groundedness`.

Two flags:
  --update  Regenerate the snapshot from the current corpus scan. Overwrites
            forge/.groundedness-baseline.yml. Operator-driven; never automatic.
  --diff    Scan the current corpus, compare to the snapshot. Print:
              + N new (violations not in snapshot — would fail CI block-mode)
              - M removed (violations in snapshot no longer present — fixed)
            Exit code 0 if N == 0; 1 otherwise.

Snapshot format (forge/.groundedness-baseline.yml):
  generated_at: <ISO date>
  total_violations: <int>
  pr_violations:    [{rule_id, ref, file_pattern}, ...]
  sha_violations:   [{rule_id, ref, file_pattern}, ...]
  file_line_violations: [{rule_id, ref, file_pattern}, ...]

file_pattern uses fnmatch glob against the last-N-segments of the file path so
the snapshot survives framework_root differences across operator environments.
"""

import argparse
import datetime
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install --user pyyaml", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root, _atomic_write  # noqa: E402

SNAPSHOT_REL_PATH = "forge/.groundedness-baseline.yml"
VIOLATION_CATEGORY_BY_RULE = {
    "GRD-001": "pr_violations",
    "GRD-002a": "sha_violations",
    "GRD-002b": "sha_violations",
    "GRD-003": "file_line_violations",
}


def _normalize_file_pattern(absolute_path: str, framework_root: Path) -> str:
    """Convert an absolute violation file path to a portable glob pattern.

    Strategy: take the last 3 path segments (.../records/backlog/SCRUM-X_backend.md
    or .../plans/backlog/SCRUM-X_verify.md). That's specific enough to identify
    the record uniquely + portable across operator environments.
    """
    try:
        rel = Path(absolute_path).resolve().relative_to(framework_root.resolve())
    except (ValueError, OSError):
        rel = Path(absolute_path)
    parts = rel.parts
    if len(parts) >= 3:
        return "*/" + "/".join(parts[-3:])
    return str(rel)


def _scan_corpus(framework_root: Path) -> list[dict]:
    """Run validate-artifact --strict-groundedness --groundedness-offline over the corpus.

    Returns list of {rule_id, ref, file_pattern} dicts (deduplicated).
    """
    validator = framework_root / "forge" / "tools" / "validate-artifact.py"
    corpus_dirs = [
        framework_root / ".ai-specs" / "changes",
    ]
    targets = []
    for d in corpus_dirs:
        if not d.is_dir():
            continue
        targets.extend(d.rglob("records/**/*.md"))
        targets.extend(d.rglob("plans/**/*.md"))

    violations: list[dict] = []
    seen: set[tuple] = set()

    for target in sorted(set(targets)):
        r = subprocess.run(
            [sys.executable, str(validator),
             "--strict-groundedness", "--groundedness-offline",
             "--json", str(target)],
            capture_output=True, text=True,
        )
        if not r.stdout.strip():
            continue
        try:
            result = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        g = result.get("groundedness", {})
        for w in g.get("warnings", []):
            rule_id = w.get("rule_id")
            ref = w.get("ref")
            if not rule_id or not ref:
                continue
            file_pattern = _normalize_file_pattern(w.get("file", ""), framework_root)
            key = (rule_id, ref, file_pattern)
            if key in seen:
                continue
            seen.add(key)
            violations.append({
                "rule_id": rule_id,
                "ref": ref,
                "file_pattern": file_pattern,
            })
    return violations


def _load_snapshot(snapshot_path: Path) -> dict:
    if not snapshot_path.is_file():
        return {
            "generated_at": "",
            "total_violations": 0,
            "pr_violations": [],
            "sha_violations": [],
            "file_line_violations": [],
        }
    with snapshot_path.open() as fh:
        data = yaml.safe_load(fh) or {}
    return data


def _violations_set(snapshot: dict) -> set[tuple]:
    """Flatten the 3 category lists into a set of (rule_id, ref, file_pattern) tuples."""
    out: set[tuple] = set()
    for key in ("pr_violations", "sha_violations", "file_line_violations"):
        for entry in snapshot.get(key, []) or []:
            if isinstance(entry, dict):
                out.add((entry.get("rule_id"), entry.get("ref"), entry.get("file_pattern")))
    return out


def _build_snapshot(violations: list[dict]) -> dict:
    snap = {
        "generated_at": datetime.date.today().isoformat(),
        "total_violations": len(violations),
        "pr_violations": [],
        "sha_violations": [],
        "file_line_violations": [],
    }
    for v in violations:
        category = VIOLATION_CATEGORY_BY_RULE.get(v["rule_id"], "file_line_violations")
        snap[category].append(v)
    # Sort each category for deterministic snapshot output.
    for key in ("pr_violations", "sha_violations", "file_line_violations"):
        snap[key] = sorted(snap[key], key=lambda e: (e["rule_id"], e["ref"], e["file_pattern"]))
    return snap


def cmd_update(framework_root: Path) -> int:
    snapshot_path = framework_root / SNAPSHOT_REL_PATH
    violations = _scan_corpus(framework_root)
    snapshot = _build_snapshot(violations)

    header = (
        "# Groundedness corpus baseline snapshot (<TICKET-ID> / workflow-standards.mdc §18.3.2).\n"
        "# Update via: python3 forge/tools/groundedness-snapshot.py --update\n"
        "# Diff vs current: python3 forge/tools/groundedness-snapshot.py --diff\n"
        "# DO NOT edit manually — operator regenerates via --update after deliberate corpus cleanup.\n"
        "\n"
    )

    import io
    buf = io.StringIO()
    buf.write(header)
    yaml.safe_dump(snapshot, buf, sort_keys=False, default_flow_style=False, width=120)
    _atomic_write(snapshot_path, buf.getvalue())

    print(f"OK: snapshot written to {snapshot_path}")
    print(f"    total_violations: {snapshot['total_violations']}")
    print(f"    pr_violations: {len(snapshot['pr_violations'])}")
    print(f"    sha_violations: {len(snapshot['sha_violations'])}")
    print(f"    file_line_violations: {len(snapshot['file_line_violations'])}")
    return 0


def cmd_diff(framework_root: Path) -> int:
    snapshot_path = framework_root / SNAPSHOT_REL_PATH
    snapshot = _load_snapshot(snapshot_path)
    snap_set = _violations_set(snapshot)

    current_violations = _scan_corpus(framework_root)
    current_set = {(v["rule_id"], v["ref"], v["file_pattern"]) for v in current_violations}

    new = sorted(current_set - snap_set)
    removed = sorted(snap_set - current_set)

    print(f"snapshot: {snapshot_path} ({snapshot.get('generated_at', 'unknown')})")
    print(f"snapshot total: {len(snap_set)}")
    print(f"current total: {len(current_set)}")
    print(f"+ {len(new)} new")
    for rule_id, ref, file_pattern in new:
        print(f"    [{rule_id}] {ref} ({file_pattern})")
    print(f"- {len(removed)} removed")
    for rule_id, ref, file_pattern in removed:
        print(f"    [{rule_id}] {ref} ({file_pattern})")

    return 0 if not new else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="groundedness-snapshot",
        description="Manage the corpus baseline of known groundedness violations (<TICKET-ID>).",
    )
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--update", action="store_true",
                     help="Regenerate the snapshot from the current corpus scan.")
    grp.add_argument("--diff", action="store_true",
                     help="Compare current corpus vs snapshot; exit 1 if new violations exist.")
    args = ap.parse_args()

    framework_root = find_framework_root()
    if framework_root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 2

    if args.update:
        return cmd_update(framework_root)
    return cmd_diff(framework_root)


if __name__ == "__main__":
    sys.exit(main())
