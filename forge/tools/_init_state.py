# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_init_state — FW-003 (framework release layer) · importable library.

Logic for initializing a ticket-state.yml from the template at
`forge/tools/state-template.yml`. The hyphenated CLI entrypoint
`init-state.py` is a thin shell over `run_cli` here (ADR-006: forge/tools/
is not a package; this underscore module is importable, the hyphen one is not).

The state file is produced by TEMPLATE-FILL (string substitution on
state-template.yml, which carries comments + exact formatting) — NOT by
serializing a model — so the on-disk output is byte-identical to pre-refactor.
`LifecycleState` (`_lifecycle_state.py`) is the additive typed in-memory view.

Exit codes (preserved):
    0  state file created (and validated, if validator available)
    1  refused (file exists, validation failed, bad args)
    2  fatal error (template missing, repo root not found)
"""

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_repo_root, resolve_artifacts_root, ARTIFACTS_SUBPATH  # noqa: E402

TICKET_RE = re.compile(r'^[A-Z][A-Z0-9]*-\d+$')
MODULE_RE = re.compile(r'^[a-z][a-z0-9-]*$')
SPRINT_RE = re.compile(r'^(Sprint \d+|SAT\d+ S\d+|backlog|Wave \d+ - .+)$')


def load_template(repo_root):
    """Return the template text. Raises FileNotFoundError if it is missing
    (the CLI maps that to exit 2 — a library must not sys.exit on a caller)."""
    path = repo_root / 'forge' / 'tools' / 'state-template.yml'
    if not path.is_file():
        raise FileNotFoundError(f'template not found at {path}')
    return path.read_text(encoding='utf-8')


def fill_template(template, ticket, module, sprint, timestamp):
    """Substitute {{PLACEHOLDER}} tokens. No regex magic — simple replace."""
    return (template
            .replace('{{TICKET}}', ticket)
            .replace('{{MODULE}}', module)
            .replace('{{SPRINT}}', sprint)
            .replace('{{TIMESTAMP}}', timestamp))


def target_path(repo_root, module, ticket):
    # Pure function of an explicit root (ARTIFACTS_SUBPATH centralizes the
    # subpath for T2). The CLI feeds the ARTIFACTS root. <TICKET-ID>.
    return repo_root / ARTIFACTS_SUBPATH / module / 'state' / f'{ticket}.yml'


def run_validator(repo_root, target):
    """Optional. Returns (rc, stdout)."""
    validator = repo_root / 'forge' / 'tools' / 'validate-artifact.py'
    if not validator.is_file():
        return None, 'validator not found (FW-002 not landed?); skipping'
    proc = subprocess.run(
        [sys.executable, str(validator), str(target), '--quiet'],
        capture_output=True, text=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    return proc.returncode, out


def run_cli(argv=None):
    """Relocated main(): parse argv, render+write the state file, RETURN exit code."""
    ap = argparse.ArgumentParser(
        prog='init-state',
        description='Initialize a ticket-state.yml from the template.',
    )
    ap.add_argument('ticket', help='Ticket ID (e.g., <TICKET-ID>, FW-003, SAT01-1)')
    ap.add_argument('module', help='Module slug (kebab-case, e.g., framework, auth, sat-cristian-garcia)')
    ap.add_argument('sprint', help='Sprint name (e.g., "internal cycle", "framework release layer - ai-specs reinforce")')
    ap.add_argument('--force', action='store_true', help='Overwrite if state file already exists')
    ap.add_argument('--no-validate', action='store_true', help='Skip post-write validation against state.schema.yml')
    ap.add_argument('--timestamp', help='Override enrich-us timestamp (default: now UTC)')
    args = ap.parse_args(argv)

    # --- arg validation
    if not TICKET_RE.match(args.ticket):
        print(f'ERROR: ticket {args.ticket!r} does not match ^[A-Z]+-\\d+$', file=sys.stderr)
        return 1
    if not MODULE_RE.match(args.module):
        print(f'ERROR: module {args.module!r} does not match ^[a-z][a-z0-9-]*$', file=sys.stderr)
        return 1
    if not SPRINT_RE.match(args.sprint):
        print(f'ERROR: sprint {args.sprint!r} does not match expected pattern '
              f'(Sprint N | SAT01 SN | backlog | Wave N - <name>)', file=sys.stderr)
        return 1

    # --- locate repo
    repo_root = find_repo_root(Path.cwd())
    if repo_root is None:
        print('ERROR: could not locate framework repo root (no forge/schemas/ found in any parent).',
              file=sys.stderr)
        return 2

    # --- target
    target = target_path(resolve_artifacts_root(), args.module, args.ticket)
    if target.exists() and not args.force:
        print(f'REFUSE: state file already exists: {target}\n        Pass --force to overwrite.',
              file=sys.stderr)
        return 1

    # --- render
    try:
        template = load_template(repo_root)
    except FileNotFoundError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    timestamp = args.timestamp or datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    rendered = fill_template(template, args.ticket, args.module, args.sprint, timestamp)

    # --- write
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding='utf-8')
    print(f'CREATED: {target}')
    print(f'         ticket={args.ticket}  module={args.module}  sprint={args.sprint!r}')
    print(f'         state=enriched  enrich-us.timestamp={timestamp}')

    # --- validate
    if args.no_validate:
        print('         (validation skipped per --no-validate)')
        return 0
    rc, out = run_validator(repo_root, target)
    if rc is None:
        print(f'         {out}')
        return 0
    if rc == 0:
        print('         validate-artifact: PASS')
        return 0
    print(f'         validate-artifact: FAIL (rc={rc})', file=sys.stderr)
    if out:
        print(out, file=sys.stderr)
    print(f'         (state file was created but does not validate — investigate)', file=sys.stderr)
    return 1
