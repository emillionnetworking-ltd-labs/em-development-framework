# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""run.py — the unified framework entrypoint (the baton's CLI).

Drives the compiled LangGraph brains one hop per invocation and maps interrupts to
exit-codes (see _protocol). Thin: argument parsing + dispatch; all orchestration is
in _session.

  python -m framework.cli.run --mode lifecycle --ticket <TICKET-ID> --module framework --advance
  python -m framework.cli.run --mode strategy  --target "<your-product> module-audit" --advance
  python -m framework.cli.run --mode strategy  --target "<your-product> module-audit" --resume --decision approve
  python -m framework.cli.run --mode lifecycle --ticket <TICKET-ID> --module framework --resume --feed work.json
  python -m framework.cli.run --status --mode lifecycle --ticket <TICKET-ID> --module framework
"""

import argparse
import json
import subprocess
import sys

from framework.cli._protocol import EXIT_DONE, EXIT_ERROR
from framework.cli import _session, framework_install_root


def _emit(req, code: int) -> int:
    if req is not None:
        print(req.to_json())
    return code


def _emit_pending_warning_if_any() -> None:
    """Pre-flight courtesy banner: fire `sprint-cleanup --report` once on lifecycle
    start (advance). If it reports candidates (rc=1), print a WARNING inviting the
    operator to run /sprint-cleanup. NEVER blocks the lifecycle. <TICKET-ID>.

    Fail-open: any exception path → silent return. Subprocess timeout 3s.
    Skips Jira (--no-jira) to keep the check fast and offline-safe.
    """
    try:
        tool = framework_install_root() / "forge" / "tools" / "sprint-cleanup.py"
        if not tool.is_file():
            return  # tool not present in this checkout — fail-open

        r = subprocess.run(
            ["python3", str(tool),
             "--sprint", "backlog", "--report", "--quiet", "--no-jira"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode != 1:
            return  # 0 = clean state; 2/3 = tool error (silent — not our problem)

        print(
            "\n┌─ WARNING ─────────────────────────────────────────────────┐\n"
            "│ pending-improvements has closure candidates.              │\n"
            "│ Run  /sprint-cleanup  to review and approve closures.     │\n"
            "└───────────────────────────────────────────────────────────┘\n",
            file=sys.stderr,
        )
    except Exception:
        # Defensive: pre-flight is a courtesy, NEVER blocks the lifecycle.
        return


def _drive(args) -> int:
    """Build (or resume) a session and stream to the next stop; emit + exit-code."""
    # <TICKET-ID>: pre-flight banner on lifecycle start (advance only, not resume).
    if args.mode == "lifecycle" and args.advance and not args.resume:
        _emit_pending_warning_if_any()

    if args.mode == "lifecycle":
        app, config, fresh = _session.build_lifecycle_session(
            args.ticket, args.module, work_impl=args.work_impl,
            output_dir=args.output_dir)
    else:
        app, config, fresh = _session.build_strategy_session(
            args.target, work_impl=args.work_impl,
            output_dir=args.output_dir)

    if args.resume:
        feed = None
        if args.feed:
            with open(args.feed, encoding="utf-8") as fh:
                feed = json.load(fh)
        snap, interrupt_value = _session.resume(app, config, feed=feed, decision=args.decision)
    else:
        snap, interrupt_value = _session.run_until_stop(app, config, fresh)

    req, code = _session.build_request(snap, args.mode, config["configurable"]["thread_id"],
                                       interrupt_value)
    if code == EXIT_DONE and args.mode == "strategy":
        report = snap.values.get("executive_report")
        if report:
            print(report)
    return _emit(req, code)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="framework.cli.run", description="The framework baton.")
    p.add_argument("--mode", choices=["lifecycle", "strategy"])
    p.add_argument("--ticket")
    p.add_argument("--module")
    p.add_argument("--target")
    p.add_argument("--advance", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--thread")
    p.add_argument("--feed")
    p.add_argument("--decision", choices=["approve", "refine", "abort"])
    p.add_argument("--status", action="store_true")
    p.add_argument("--work-impl", default="stub")
    p.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory where generated state (checkpoints, strategy sessions) "
            "is written. Overrides EM_FRAMEWORK_OUTPUT_DIR + forge.config.yml. "
            "Default: .em-out/ in the current working directory."
        ),
    )
    args = p.parse_args(argv)

    try:
        if args.status:
            if args.mode != "lifecycle" or not (args.ticket and args.module):
                print(json.dumps({"error": "--status needs --mode lifecycle --ticket --module"}),
                      file=sys.stderr)
                return EXIT_ERROR
            st = _session.lifecycle_status(args.ticket, args.module)
            if st is None:
                print(json.dumps({"error": f"no state for {args.ticket}/{args.module}"}),
                      file=sys.stderr)
                return EXIT_ERROR
            print(json.dumps(st, indent=2))
            return EXIT_DONE

        if not args.mode:
            print(json.dumps({"error": "--mode is required (lifecycle|strategy)"}), file=sys.stderr)
            return EXIT_ERROR
        if not (args.advance or args.resume):
            print(json.dumps({"error": "pass --advance or --resume"}), file=sys.stderr)
            return EXIT_ERROR

        return _drive(args)
    except Exception as exc:  # surface as a clean console error, not a traceback
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
