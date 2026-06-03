#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Validate a directory tree (or extracted git archive) against the frozen
distribution manifest at forge/.distribution-manifest.yml.

Used by:
  - distro-mirror.yml: pre-push gate to confirm the snapshot is exactly the
    144 distributable files before pushing to PUBLIC.
  - distro-mirror.yml: post-push gate to re-verify after mirror commit.

Exit codes:
  0 — tree matches manifest exactly
  1 — drift detected (missing or extra files); prints diff
  2 — usage error / manifest missing / cannot read tree

Usage:
  python3 validate_distribution_manifest.py --tree <dir> --manifest <path>
  python3 validate_distribution_manifest.py --tree <dir> --manifest <path> --json
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed", file=sys.stderr)
    sys.exit(2)


def load_manifest(path: Path) -> set[str]:
    if not path.is_file():
        print(
            f"ERROR: manifest file not found at {path}.\n"
            f"  Hint: the manifest is authored in W60 (SCRUM-628). "
            f"If running pre-W60, this error is expected.",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"ERROR: manifest YAML invalid: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict) or "files" not in data:
        print(
            f"ERROR: manifest must be a dict with 'files' key listing distributable paths",
            file=sys.stderr,
        )
        sys.exit(2)
    files = data["files"]
    if not isinstance(files, list):
        print("ERROR: manifest 'files' must be a list", file=sys.stderr)
        sys.exit(2)
    return set(files)


def collect_tree_files(tree: Path) -> set[str]:
    if not tree.is_dir():
        print(f"ERROR: tree path is not a directory: {tree}", file=sys.stderr)
        sys.exit(2)
    out = set()
    for p in tree.rglob("*"):
        if p.is_file():
            out.add(str(p.relative_to(tree)))
    return out


def diff_report(manifest: set[str], tree: set[str]) -> tuple[set[str], set[str]]:
    missing_in_tree = manifest - tree
    extra_in_tree = tree - manifest
    return missing_in_tree, extra_in_tree


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate tree against distribution manifest")
    ap.add_argument("--tree", required=True, help="Directory tree to validate")
    ap.add_argument("--manifest", required=True, help="Path to forge/.distribution-manifest.yml")
    ap.add_argument("--json", action="store_true", help="Emit JSON diff on drift (machine-readable)")
    args = ap.parse_args(argv)

    manifest_path = Path(args.manifest)
    tree_path = Path(args.tree)

    expected = load_manifest(manifest_path)
    actual = collect_tree_files(tree_path)
    missing, extra = diff_report(expected, actual)

    if not missing and not extra:
        print(f"PASS: tree at {tree_path} matches manifest {manifest_path} ({len(expected)} files)")
        return 0

    if args.json:
        print(json.dumps({
            "result": "FAIL",
            "manifest_size": len(expected),
            "tree_size": len(actual),
            "missing_in_tree": sorted(missing),
            "extra_in_tree": sorted(extra),
        }, indent=2))
    else:
        print(f"FAIL: drift detected ({len(missing)} missing, {len(extra)} extra)", file=sys.stderr)
        if missing:
            print(f"\nMissing in tree (expected by manifest):", file=sys.stderr)
            for f in sorted(missing)[:20]:
                print(f"  - {f}", file=sys.stderr)
            if len(missing) > 20:
                print(f"  ... ({len(missing) - 20} more)", file=sys.stderr)
        if extra:
            print(f"\nExtra in tree (not in manifest):", file=sys.stderr)
            for f in sorted(extra)[:20]:
                print(f"  + {f}", file=sys.stderr)
            if len(extra) > 20:
                print(f"  ... ({len(extra) - 20} more)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
