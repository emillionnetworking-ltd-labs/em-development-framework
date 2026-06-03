#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""check-pending-improvements — scan the pending improvements registry and report eligibility.

<TICKET-ID> / workflow-standards.mdc §21. Pause-friendly safety net for solo-operator.

Flags:
  --report             (default) human-readable status grouped by status
  --json               machine-readable JSON output
  --eligible-only      filter to status: eligible OR manual-check-due
  --update-checked ID  mark last_checked + status (requires --note)
  --note "TEXT"        paired with --update-checked

Exit codes:
  0  no eligible AND no manual-check-due items
  1  ≥1 eligible OR manual-check-due (call to action)
  2  usage error / registry parse error / unknown id

Tool is OBSERVATION ONLY — never auto-creates Jira tickets (per feedback_no_unsolicited_backlog_mining).
"""

import argparse
import datetime
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

REGISTRY_REL_PATH = "forge/registers/pending-improvements.yml"
DEFAULT_TRIGGER_TIMEOUT = 10


def _today() -> datetime.date:
    return datetime.date.today()


def _parse_date(s: str | None) -> datetime.date | None:
    if not s:
        return None
    if isinstance(s, datetime.date):
        return s
    return datetime.date.fromisoformat(str(s))


def _evaluate_entry(entry: dict, framework_root: Path) -> str:
    """Return the effective status for an entry given today's state.

    Pure function: does NOT mutate the entry. Mutation happens in --update-checked.
    """
    declared = entry.get("status", "waiting")
    if declared in ("done", "withdrawn"):
        return declared

    trigger = entry.get("trigger", {})
    ttype = trigger.get("type")
    if ttype == "auto":
        check_cmd = trigger.get("check", "")
        timeout = trigger.get("timeout_seconds", DEFAULT_TRIGGER_TIMEOUT)
        try:
            r = subprocess.run(
                check_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(framework_root),
            )
            if r.returncode == 0:
                return "eligible"
            return "waiting"
        except subprocess.TimeoutExpired:
            return "waiting"
        except Exception:
            return "waiting"

    if ttype == "manual":
        nc = _parse_date(entry.get("next_check"))
        if nc is not None and nc <= _today():
            return "manual-check-due"
        return "waiting"

    return declared


def _load_registry(framework_root: Path, override: Path | None = None) -> tuple[dict, Path]:
    path = override if override is not None else framework_root / REGISTRY_REL_PATH
    if not path.is_file():
        print(f"ERROR: registry not found at {path}", file=sys.stderr)
        sys.exit(2)
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "entries" not in data:
        print("ERROR: registry shape invalid", file=sys.stderr)
        sys.exit(2)
    return data, path


def _render_text(buckets: dict[str, list[dict]], framework_root: Path) -> int:
    counts = {k: len(v) for k, v in buckets.items()}
    eligible = counts["eligible"]
    due = counts["manual-check-due"]
    waiting = counts["waiting"]
    done = counts["done"]
    withdrawn = counts["withdrawn"]

    print(f"== Pending Improvements Registry — {_today().isoformat()} ==")
    print(f"   eligible: {eligible}  manual-check-due: {due}  "
          f"waiting: {waiting}  done: {done}  withdrawn: {withdrawn}")
    print()

    if eligible > 0:
        print("ELIGIBLE (auto-trigger fired — call to action):")
        for e in buckets["eligible"]:
            _print_entry_detail(e)
        print()

    if due > 0:
        print("MANUAL-CHECK-DUE (next_check date reached — operator review):")
        for e in buckets["manual-check-due"]:
            _print_entry_detail(e)
        print()

    if waiting > 0:
        print("WAITING (compact):")
        for e in buckets["waiting"]:
            nc = e.get("next_check", "—")
            val = e.get("value_estimate", "—")
            print(f"  - {e['id']:<40} value={val:<8} next_check={nc}")
        print()

    if done > 0:
        print(f"DONE ({done}):", ", ".join(e["id"] for e in buckets["done"]))
    if withdrawn > 0:
        print(f"WITHDRAWN ({withdrawn}):", ", ".join(e["id"] for e in buckets["withdrawn"]))

    return 1 if (eligible > 0 or due > 0) else 0


def _print_entry_detail(e: dict) -> None:
    print(f"  ▸ {e['id']}")
    print(f"      source:       {e.get('source', '—')}")
    print(f"      value:        {e.get('value_estimate', '—')}")
    print(f"      cost:         {e.get('cost_estimate', '—')}")
    if e.get("trigger", {}).get("type") == "auto":
        print(f"      trigger:      auto (fired)")
    else:
        print(f"      next_check:   {e.get('next_check', '—')}")
    note = e.get("note")
    if note:
        print(f"      note:         {note}")


def cmd_report(args, data: dict, framework_root: Path) -> int:
    """Group + render report."""
    buckets: dict[str, list[dict]] = {
        "eligible": [],
        "manual-check-due": [],
        "waiting": [],
        "done": [],
        "withdrawn": [],
    }
    for entry in data["entries"]:
        eff = _evaluate_entry(entry, framework_root)
        # Preserve declared eligible/manual-check-due/done/withdrawn; auto-promote waiting→eligible/due.
        if entry.get("status") in ("done", "withdrawn"):
            buckets[entry["status"]].append(entry)
        else:
            buckets[eff].append(entry)

    if args.eligible_only:
        # Filter: keep only eligible + manual-check-due in the report.
        filtered = {k: v for k, v in buckets.items() if k in ("eligible", "manual-check-due")}
        if args.json:
            print(json.dumps(filtered, indent=2, default=str))
            return 1 if any(filtered.values()) else 0
        ec = len(filtered["eligible"])
        dc = len(filtered["manual-check-due"])
        if ec + dc == 0:
            print(f"No eligible or manual-check-due items as of {_today().isoformat()}.")
            return 0
        for cat in ("eligible", "manual-check-due"):
            if filtered[cat]:
                print(f"{cat.upper()}:")
                for e in filtered[cat]:
                    _print_entry_detail(e)
                print()
        return 1

    if args.json:
        out = {
            "generated_at": _today().isoformat(),
            "counts": {k: len(v) for k, v in buckets.items()},
            "buckets": buckets,
        }
        print(json.dumps(out, indent=2, default=str))
        return 1 if (buckets["eligible"] or buckets["manual-check-due"]) else 0

    return _render_text(buckets, framework_root)


def cmd_update_checked(args, data: dict, registry_path: Path) -> int:
    target_id = args.update_checked
    note = args.note
    if not note:
        print("ERROR: --update-checked requires --note", file=sys.stderr)
        return 2

    entry = None
    for e in data["entries"]:
        if e.get("id") == target_id:
            entry = e
            break
    if entry is None:
        ids = [e.get("id") for e in data["entries"]]
        print(f"ERROR: no entry with id '{target_id}'", file=sys.stderr)
        print(f"       available: {', '.join(ids)}", file=sys.stderr)
        return 2

    today_iso = _today().isoformat()
    entry["last_checked"] = today_iso
    existing_note = entry.get("note", "")
    audit_line = f"[{today_iso}] {note}"
    entry["note"] = (existing_note + "\n" + audit_line).strip() if existing_note else audit_line

    # Atomic write.
    import io
    buf = io.StringIO()
    # Preserve top-of-file comments by re-reading + re-emitting prefix.
    with registry_path.open() as fh:
        original = fh.read()
    header_lines = []
    for ln in original.splitlines(keepends=True):
        if ln.startswith("#") or not ln.strip():
            header_lines.append(ln)
        else:
            break
    buf.write("".join(header_lines))
    yaml.safe_dump(data, buf, sort_keys=False, default_flow_style=False, width=120)
    _atomic_write(registry_path, buf.getvalue())

    print(f"OK: updated {target_id}.last_checked = {today_iso}")
    print(f"    note appended: {audit_line}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check-pending-improvements",
        description="Scan pending improvements registry; report eligibility (<TICKET-ID>).",
    )
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--report", action="store_true",
                     help="Human-readable status report (default).")
    grp.add_argument("--update-checked", metavar="ID",
                     help="Mark last_checked + note for entry ID.")
    ap.add_argument("--json", action="store_true",
                    help="Machine-readable JSON output (with --report).")
    ap.add_argument("--eligible-only", action="store_true",
                    help="Filter to eligible + manual-check-due (with --report).")
    ap.add_argument("--note", help="Note for --update-checked (required when updating).")
    ap.add_argument("--registry-path",
                    help="Override registry path (mainly for tests; defaults to "
                         "<framework_root>/forge/registers/pending-improvements.yml).")
    args = ap.parse_args()

    framework_root = find_framework_root()
    if framework_root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 2

    override = Path(args.registry_path) if args.registry_path else None
    data, registry_path = _load_registry(framework_root, override=override)

    if args.update_checked:
        return cmd_update_checked(args, data, registry_path)
    # Default: --report
    return cmd_report(args, data, framework_root)


if __name__ == "__main__":
    sys.exit(main())
