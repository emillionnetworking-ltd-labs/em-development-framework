#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""sprint-cleanup — find pending-improvements eligible for closure at sprint-end.

<TICKET-ID> (framework release layer). The closer of the pending-improvements register loop:
classify-deviation OPENS, audit-coupling-check VIGILA, check-pending REPORTS,
sprint-cleanup CLOSES with evidence.

Three evidence sources per entry (A1 auto-trigger re-eval, A2 jira-ticket-done,
A3 operator-marked-in-note). Approval gated per id. Tool NEVER writes to Jira.

Flags:
  --sprint NAME             (required) Sprint to inspect, OR "backlog" for null-sprint entries.
  --include-backlog         Also evaluate null-sprint entries (A1 + A2 only — A3 disabled
                            for backlog because there is no sprint context to mark against).
  --report                  (default) Print candidates; zero side effects.
  --json                    Machine-readable.
  --approve ID [ID ...]     Close listed entries (requires --sprint).
  --note "TEXT"             Optional note override.
  --jira-creds              Force Jira lookup; FAIL LOUDLY if creds missing (exit 2).
  --no-jira                 Skip Jira lookup silently (mutex with --jira-creds).
  --quiet                   Suppress header banner; keep candidate rows only.

Exit codes:
  0  --report ran, ZERO candidates (clean state) | --approve completed
  1  --report ran, >=1 candidate (CALL TO ACTION — consumable by CI)
  2  usage error / parse error / Jira creds missing when --jira-creds set
  3  --approve failed (atomic write, unknown id, status not waiting/eligible,
     post-mutation schema re-validation failed)
"""

import argparse
import datetime
import io
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. pip install --user pyyaml", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root, _atomic_write  # noqa: E402
from _pending_improvements import PendingRegistry, PendingImprovementEntry  # noqa: E402
from _sprint_cleanup import (  # noqa: E402
    EvidenceSource, SourceEvaluation, JiraCredsMissing,
    resolve_jira_credentials, make_jira_query,
    evaluate_entry, close_entry, select_entries,
)


REGISTRY_REL_PATH = "forge/registers/pending-improvements.yml"


def _load_registry(framework_root: Path, override: Path | None = None) -> tuple[dict, Path, PendingRegistry]:
    """Load the registry as raw dict + typed model + path. The raw dict preserves
    the YAML key order; the typed model is what the logic operates on."""
    path = override if override else framework_root / REGISTRY_REL_PATH
    if not path.is_file():
        print(f"ERROR: registry not found at {path}", file=sys.stderr)
        sys.exit(2)
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    try:
        typed = PendingRegistry.model_validate(raw)
    except Exception as exc:
        print(f"ERROR: registry failed Pydantic validation:\n  {exc}", file=sys.stderr)
        sys.exit(2)
    return raw, path, typed


def _write_registry_preserving_comments(path: Path, raw: dict) -> None:
    """Write the registry yaml back, preserving the top-of-file comment block.
    Same helper pattern as check-pending-improvements.py."""
    original = path.read_text(encoding="utf-8")
    header_lines = []
    for ln in original.splitlines(keepends=True):
        if ln.startswith("#") or not ln.strip():
            header_lines.append(ln)
        else:
            break
    buf = io.StringIO()
    buf.write("".join(header_lines))
    yaml.safe_dump(raw, buf, sort_keys=False, default_flow_style=False, width=120)
    _atomic_write(path, buf.getvalue())


def _persist_and_revalidate(framework_root: Path, path: Path, raw: dict) -> None:
    """Atomic write + invoke validate-artifact.py for post-mutation re-check.
    Rolls back on validation failure. Exits 3 on failure."""
    backup = path.read_text(encoding="utf-8")
    try:
        _write_registry_preserving_comments(path, raw)
        validator = framework_root / "forge" / "tools" / "validate-artifact.py"
        result = subprocess.run(
            ["python3", str(validator), str(path), "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            _atomic_write(path, backup)
            print(
                f"ERROR: post-mutation schema re-validation FAILED — rolled back.\n"
                f"  Validator: {result.stdout}{result.stderr}",
                file=sys.stderr,
            )
            sys.exit(3)
    except Exception as exc:
        _atomic_write(path, backup)
        print(f"ERROR: persistence failed, rolled back: {exc}", file=sys.stderr)
        sys.exit(3)


# ----- report rendering -----


def _format_a1(a1) -> str:
    icons = {
        "fired": "✓ fired",
        "still-pending": "· still-pending",
        "n-a-manual": "— n/a (manual)",
        "n-a-no-check": "— n/a (no check)",
        "error": "✗ error",
    }
    return f"{icons[a1.state]:<24} {a1.detail}"


def _format_a2(a2) -> str:
    icons = {
        "done": "✓ done",
        "open": "· open",
        "skipped-no-creds": "⚠ [SKIPPED — MISSING CREDS]",
        "skipped-no-ticket": "— no ticket",
        "skipped-by-flag": "— --no-jira",
        "error": "✗ lookup failed",
    }
    return f"{icons[a2.state]:<32} {a2.detail}"


def _format_a3(a3) -> str:
    icons = {
        "marked": "✓ marked",
        "unmarked": "— unmarked",
    }
    return f"{icons[a3.state]:<24} {a3.detail}"


def _print_entry_detail(entry: PendingImprovementEntry, ev: SourceEvaluation,
                       is_backlog: bool) -> None:
    src_label = f"<null — backlog>" if is_backlog else (entry.sprint or "—")
    win = ev.winning_source
    win_label = win.value if win else "[no-evidence]"
    print(f"  ▸ {entry.id}")
    print(f"      sprint:        {src_label}")
    print(f"      jira_ticket:   {entry.jira_ticket or '—'}")
    print(f"      evidence:      {win_label}")
    print(f"      sources evaluated:")
    print(f"        A1 (auto-trigger):     {_format_a1(ev.a1)}")
    print(f"        A2 (jira-ticket-done): {_format_a2(ev.a2)}")
    print(f"        A3 (operator-marked):  {_format_a3(ev.a3)}")
    if entry.value_estimate or entry.cost_estimate:
        print(f"      value: {entry.value_estimate or '—':<10} "
              f"cost: {entry.cost_estimate or '—'}")


def _build_evals(entries: list[PendingImprovementEntry], framework_root: Path,
                jira_query, creds, skip_jira: bool) -> list[tuple[PendingImprovementEntry, SourceEvaluation]]:
    has_creds = creds is not None
    return [
        (e, evaluate_entry(e, framework_root, jira_query, has_creds, skip_jira))
        for e in entries
    ]


def cmd_report(args, framework_root: Path, typed: PendingRegistry) -> int:
    in_scope, backlog = select_entries(typed.entries, args.sprint, args.include_backlog)

    try:
        creds = resolve_jira_credentials(force=args.jira_creds, skip_by_flag=args.no_jira)
    except JiraCredsMissing as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    jira_query = make_jira_query(creds)

    in_scope_evals = _build_evals(in_scope, framework_root, jira_query, creds, args.no_jira)
    backlog_evals = _build_evals(backlog, framework_root, jira_query, creds, args.no_jira)

    in_scope_candidates = [(e, ev) for e, ev in in_scope_evals if ev.is_candidate]
    backlog_candidates = [(e, ev) for e, ev in backlog_evals if ev.is_candidate]
    in_scope_remain = [(e, ev) for e, ev in in_scope_evals if not ev.is_candidate]

    total_candidates = len(in_scope_candidates) + len(backlog_candidates)

    if args.json:
        out = {
            "sprint": args.sprint,
            "include_backlog": args.include_backlog,
            "candidates": {
                "in_scope": [{"id": e.id, "source": ev.winning_source.value if ev.winning_source else None}
                             for e, ev in in_scope_candidates],
                "backlog": [{"id": e.id, "source": ev.winning_source.value if ev.winning_source else None}
                            for e, ev in backlog_candidates],
            },
            "remain_in_scope": [e.id for e, _ in in_scope_remain],
        }
        print(json.dumps(out, indent=2))
        return 1 if total_candidates else 0

    if not args.quiet:
        today = datetime.date.today().isoformat()
        print(f"== Sprint Cleanup Candidates — {args.sprint} — {today} ==")
        print()

    if in_scope_candidates:
        print(f"IN-SPRINT CANDIDATES ({len(in_scope_candidates)}):")
        for entry, ev in in_scope_candidates:
            _print_entry_detail(entry, ev, is_backlog=False)
        print()

    if backlog_candidates:
        print(f"BACKLOG CANDIDATES (--include-backlog, evidence A1+A2 only) ({len(backlog_candidates)}):")
        for entry, ev in backlog_candidates:
            _print_entry_detail(entry, ev, is_backlog=True)
        print()

    if total_candidates == 0:
        if not args.quiet:
            print(f"No candidates for closure in scope. Clean state.")
        return 0

    if not args.quiet:
        print(f"To close: sprint-cleanup.py --sprint {args.sprint!r} --approve "
              f"<id> [<id>...]")
    return 1


def cmd_approve(args, framework_root: Path, raw: dict, typed: PendingRegistry,
                registry_path: Path) -> int:
    if not args.approve:
        print("ERROR: --approve requires at least one entry id", file=sys.stderr)
        return 2

    today = datetime.date.today()

    try:
        creds = resolve_jira_credentials(force=args.jira_creds, skip_by_flag=args.no_jira)
    except JiraCredsMissing as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    jira_query = make_jira_query(creds)

    # Locate each entry; verify it qualifies as candidate.
    closures: list[tuple[int, PendingImprovementEntry, EvidenceSource]] = []
    for target_id in args.approve:
        idx = next((i for i, e in enumerate(typed.entries) if e.id == target_id), None)
        if idx is None:
            print(f"ERROR: unknown entry id {target_id!r}", file=sys.stderr)
            return 3
        entry = typed.entries[idx]
        if entry.status not in ("waiting", "eligible"):
            print(f"ERROR: entry {target_id!r} status={entry.status!r}; "
                  f"only waiting|eligible are closable", file=sys.stderr)
            return 3
        ev = evaluate_entry(entry, framework_root, jira_query,
                            has_jira_creds=creds is not None,
                            skip_jira_by_flag=args.no_jira)
        if not ev.is_candidate:
            print(f"ERROR: entry {target_id!r} has NO evidence (A1.{ev.a1.state} "
                  f"A2.{ev.a2.state} A3.{ev.a3.state}); refuse to close", file=sys.stderr)
            return 3
        closures.append((idx, entry, ev.winning_source))

    # Apply transitions in-memory.
    for idx, entry, source in closures:
        new_entry = close_entry(
            entry, source, args.sprint, today, note=args.note,
        )
        raw["entries"][idx] = new_entry.model_dump(mode="json", exclude_none=True)

    # Persist with atomic write + post-mutation re-validation + rollback on failure.
    _persist_and_revalidate(framework_root, registry_path, raw)

    print(f"OK: closed {len(closures)} entries in {args.sprint!r}")
    for _, entry, source in closures:
        print(f"  ▸ {entry.id:<40} by={source.value}")
    print(f"Registry: {registry_path}")
    print(f"NO Jira side effects (per feedback_no_unsolicited_backlog_mining).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sprint-cleanup",
                                  description="Find pending-improvements eligible for closure at sprint-end (<TICKET-ID>).")
    ap.add_argument("--sprint", required=True,
                    help="Sprint to inspect (canonical name) or 'backlog' for null-sprint entries.")
    ap.add_argument("--include-backlog", action="store_true",
                    help="Also evaluate null-sprint entries (A1+A2 only).")

    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--report", action="store_true",
                     help="Print candidates report (default).")
    grp.add_argument("--approve", nargs="+", metavar="ID",
                     help="Close listed entries (atomic write + re-validation).")

    ap.add_argument("--json", action="store_true", help="Machine-readable (with --report).")
    ap.add_argument("--note", help="Optional note override (with --approve).")
    ap.add_argument("--quiet", action="store_true", help="Suppress banner; rows only.")

    jira_grp = ap.add_mutually_exclusive_group()
    jira_grp.add_argument("--jira-creds", action="store_true",
                          help="Force Jira lookup; fail (exit 2) if env not set.")
    jira_grp.add_argument("--no-jira", action="store_true",
                          help="Skip Jira lookup silently.")

    ap.add_argument("--registry-path",
                    help="Override registry path (mainly for tests).")

    args = ap.parse_args(argv)

    framework_root = find_framework_root()
    if framework_root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 2

    override = Path(args.registry_path) if args.registry_path else None
    raw, path, typed = _load_registry(framework_root, override=override)

    if args.approve:
        return cmd_approve(args, framework_root, raw, typed, path)
    return cmd_report(args, framework_root, typed)


if __name__ == "__main__":
    sys.exit(main())
