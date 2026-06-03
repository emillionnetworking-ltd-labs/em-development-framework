#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Compare the PRIVATE repo's latest tag archive tree to the PUBLIC mirror's
tree at the same tag. Detects silent drift between PRIVATE and PUBLIC mirrors.

Used by:
  - tag-mirror-validator.yml: cron-scheduled drift detector. Opens a GitHub
    issue on PRIVATE if PUBLIC has diverged.

Exit codes:
  0 — trees identical (no drift)
  1 — drift detected; prints diff and (optionally) JSON for issue body
  2 — usage error / cannot fetch public tree / git not available

Usage:
  python3 compare_mirror_tag_tree.py --public-repo <slug> --private-tag <tag>
  python3 compare_mirror_tag_tree.py --public-repo <slug> --private-tag <tag> --json
"""
import argparse
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **kw)


def fetch_private_tree(tag: str) -> set[str]:
    cp = subprocess.run(
        ["git", "archive", "--format=tar", tag],
        check=False, capture_output=True,
    )
    if cp.returncode != 0:
        print(
            f"ERROR: git archive failed for tag {tag}: "
            f"{cp.stderr.decode(errors='replace').strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    out = set()
    with tarfile.open(fileobj=io.BytesIO(cp.stdout), mode="r") as t:
        for m in t.getmembers():
            if m.isfile():
                out.add(m.name)
    return out


def fetch_public_tree(repo: str, tag: str) -> set[str]:
    cp = run(["gh", "api", f"repos/{repo}/git/refs/tags/{tag}"])
    if cp.returncode != 0:
        print(
            f"ERROR: cannot read tag {tag} from {repo}: {cp.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        ref_obj = json.loads(cp.stdout)
        commit_sha = ref_obj.get("object", {}).get("sha")
    except json.JSONDecodeError:
        print(f"ERROR: malformed gh api response", file=sys.stderr)
        sys.exit(2)
    if not commit_sha:
        print(f"ERROR: could not resolve commit SHA for {repo}@{tag}", file=sys.stderr)
        sys.exit(2)
    cp2 = run(["gh", "api", f"repos/{repo}/git/trees/{commit_sha}?recursive=1"])
    if cp2.returncode != 0:
        print(
            f"ERROR: cannot fetch tree for {commit_sha}: {cp2.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        tree = json.loads(cp2.stdout)
    except json.JSONDecodeError:
        print(f"ERROR: malformed tree response", file=sys.stderr)
        sys.exit(2)
    return {entry["path"] for entry in tree.get("tree", []) if entry.get("type") == "blob"}


def report_drift(private: set[str], public: set[str], emit_json: bool) -> int:
    missing_in_public = private - public
    extra_in_public = public - private
    if not missing_in_public and not extra_in_public:
        print(f"PASS: PRIVATE archive tree matches PUBLIC tree ({len(private)} files)")
        return 0
    if emit_json:
        print(json.dumps({
            "result": "DRIFT",
            "private_size": len(private),
            "public_size": len(public),
            "missing_in_public": sorted(missing_in_public),
            "extra_in_public": sorted(extra_in_public),
        }, indent=2))
    else:
        print(
            f"FAIL: drift detected (missing in PUBLIC: {len(missing_in_public)}, "
            f"extra in PUBLIC: {len(extra_in_public)})",
            file=sys.stderr,
        )
        if missing_in_public:
            print(f"\nFiles in PRIVATE archive but missing in PUBLIC:", file=sys.stderr)
            for f in sorted(missing_in_public)[:20]:
                print(f"  - {f}", file=sys.stderr)
            if len(missing_in_public) > 20:
                print(f"  ... ({len(missing_in_public) - 20} more)", file=sys.stderr)
        if extra_in_public:
            print(f"\nFiles in PUBLIC but not in PRIVATE archive (RECONTAMINATION RISK):", file=sys.stderr)
            for f in sorted(extra_in_public)[:20]:
                print(f"  + {f}", file=sys.stderr)
            if len(extra_in_public) > 20:
                print(f"  ... ({len(extra_in_public) - 20} more)", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare PRIVATE tag tree to PUBLIC mirror tree")
    ap.add_argument("--public-repo", required=True, help="owner/repo slug for PUBLIC mirror")
    ap.add_argument("--private-tag", required=True, help="Tag to compare (e.g., v0.20.0)")
    ap.add_argument("--json", action="store_true", help="Emit JSON diff on drift")
    args = ap.parse_args(argv)

    private_tree = fetch_private_tree(args.private_tag)
    public_tree = fetch_public_tree(args.public_repo, args.private_tag)
    return report_drift(private_tree, public_tree, args.json)


if __name__ == "__main__":
    sys.exit(main())
