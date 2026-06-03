#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""verify-checks — <TICKET-ID> (framework release layer) · CLI shell.

Thin CLI over the importable library `_verify_checks.py`. The library owns
the predicates + orchestrator + report renderers; this shell just parses
argv, loads the registry, runs the checks, prints the report, and emits
the verdict exit code.

Usage:
  python3 forge/tools/verify-checks.py --module framework --ticket <TICKET-ID>
  python3 forge/tools/verify-checks.py --module framework --ticket <TICKET-ID> --json
  python3 forge/tools/verify-checks.py --module framework --ticket <TICKET-ID> --registry /path/to/custom-registry.yml

Exit codes:
  0  all block-severity checks passed (or not-applicable)
  1  at least one block-severity check failed or skipped-infra
  2  usage / registry parse error
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_framework_root  # noqa: E402
from _verify_checks import (  # noqa: E402
    load_registry, run_checks,
    report_to_markdown, report_to_yaml, overall_verdict,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="verify-checks", description="Procedural checks runner (<TICKET-ID>).")
    ap.add_argument("--module", required=True, help="Module being verified (e.g. framework, auth).")
    ap.add_argument("--ticket", required=True, help="Ticket id (e.g. <TICKET-ID>).")
    ap.add_argument("--scope", default=None,
                    help="Scope filter (backend|frontend|framework|fullstack). Defaults to --module if recognised, else 'framework'.")
    ap.add_argument("--registry", default=None, help="Path to checks registry (default: forge/.checks-registry.yml).")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown table.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    repo_root = find_framework_root()
    if repo_root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 2

    registry_path = Path(args.registry) if args.registry else (repo_root / "forge" / ".checks-registry.yml")
    try:
        registry = load_registry(registry_path)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: failed to load registry {registry_path}: {e}", file=sys.stderr)
        return 2

    scope = args.scope or ("framework" if args.module == "framework" else args.module)
    outcomes = run_checks(registry, scope, repo_root, args.ticket, args.module)

    if args.json:
        out = {
            "run_at": date.today().isoformat(),
            "ticket": args.ticket,
            "module": args.module,
            "scope": scope,
            "checks": [
                {"id": o.id, "name": o.name, "result": o.result.value,
                 "severity": o.severity, "message": o.message, "evidence": o.evidence}
                for o in outcomes
            ],
        }
        print(json.dumps(out, indent=2))
    elif not args.quiet:
        print(f"== verify-checks — ticket={args.ticket} module={args.module} scope={scope} ==\n")
        print(report_to_markdown(outcomes))
        print()

    verdict = overall_verdict(outcomes)
    if not args.quiet and not args.json:
        print(f"verdict: exit {verdict}")
    return verdict


if __name__ == "__main__":
    sys.exit(main())
