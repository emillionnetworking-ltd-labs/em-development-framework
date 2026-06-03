#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""state-machine — FW-004 lifecycle gate.

CLI gate enforcing the lifecycle state machine documented in
`.lifecycle/artifacts/STATE-MACHINE.md`. Each of the 6 lifecycle commands
(`/enrich-us`, `/plan`, `/develop`, `/verify`, `/commit`, `/update-docs`)
invokes this script:

  - `check <cmd> <ticket> <module>` — exit 0 if prerequisites met, 1 if
    refused, 2 if state file missing or unparseable.
  - `advance <cmd> <ticket> <module> [--field k=v ...]` — re-checks prereqs,
    writes the step entry, advances `state`, validates the result via
    `validate-artifact.py`.
  - `state <ticket> <module>` — print the current state YAML (debug).

Rules live HERE, not in markdown. This is what makes the framework's
"MANDATORY sequence" mechanical instead of advisory.
"""

import argparse
import datetime
import errno
import fcntl
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

LOCK_TIMEOUT_SECONDS = 5
EX_TEMPFAIL = 75  # sysexits.h — "try again later"

try:
    import yaml
except ImportError:
    print('ERROR: PyYAML not installed. Run: pip install --user pyyaml', file=sys.stderr)
    sys.exit(2)


# Library error signals (a lib must not sys.exit on a caller — the CLI maps
# these back to the historical exit codes in run_cli, byte-identically).
class StateParseError(Exception):
    """Raised by load_state when the state file is unparseable (CLI → exit 2)."""


class LockTimeout(Exception):
    """Raised by _StateLock when the lock cannot be acquired (CLI → exit 75)."""


# ---------- Refusal rules ----------
#
# Each command has:
#   - prereq:        callable(state_dict) -> bool. True = OK.
#   - prereq_msg:    human-readable explanation when prereq fails.
#   - advance_state: the state enum value after this command completes.
#
# Add a new command here, NOT in the markdown command files. The markdown
# only invokes this script — it does not encode the rules.

def _step_done(s, name): return s.get('steps', {}).get(name, {}).get('done') is True
def _step_validated(s, name): return s.get('steps', {}).get(name, {}).get('schema_validated') is True
def _verify_verdict(s): return s.get('steps', {}).get('verify', {}).get('verdict')


COMMAND_RULES = {
    'enrich-us': {
        'prereq': lambda s: True,
        'prereq_msg': '',
        'advance_state': 'enriched',
        'allowed_fields': ['jira_hash'],
        'creates_state_if_missing': True,
    },
    'plan': {
        'prereq': lambda s: _step_done(s, 'enrich-us'),
        'prereq_msg': '/plan requires steps.enrich-us.done == true.',
        'advance_state': 'planned',
        'allowed_fields': ['path', 'schema_validated'],
        'creates_state_if_missing': False,
    },
    'develop': {
        'prereq': lambda s: _step_done(s, 'plan') and _step_validated(s, 'plan'),
        'prereq_msg': '/develop requires steps.plan.done == true AND steps.plan.schema_validated == true.',
        'advance_state': 'developing',
        'allowed_fields': ['branch', 'last_commit', 'plan_compliance_summary'],
        'creates_state_if_missing': False,
    },
    'verify': {
        'prereq': lambda s: _step_done(s, 'develop'),
        'prereq_msg': '/verify requires steps.develop.done == true.',
        'advance_state': 'verified',
        'allowed_fields': ['verdict', 'path', 'schema_validated', 'deviations_count'],
        'creates_state_if_missing': False,
    },
    'commit': {
        'prereq': lambda s: (
            _step_done(s, 'verify')
            and _step_validated(s, 'verify')
            and _verify_verdict(s) in ('PASS', 'PASS-WITH-DEBT')
        ),
        'prereq_msg': '/commit requires steps.verify.done==true AND steps.verify.schema_validated==true AND verdict in {PASS, PASS-WITH-DEBT}.',
        'advance_state': 'committed',
        'allowed_fields': ['pr', 'merge_commit', 'branch_deleted'],
        'creates_state_if_missing': False,
    },
    'update-docs': {
        'prereq': lambda s: _step_done(s, 'commit'),
        'prereq_msg': '/update-docs requires steps.commit.done == true.',
        'advance_state': 'documented',
        'allowed_fields': ['record_path', 'record_schema_validated', 'ai_specs_commit', 'specs_updated'],
        'creates_state_if_missing': False,
    },
}


# ---------- Filesystem helpers ----------

from framework._runtime.state._common import find_repo_root, resolve_artifacts_root, ARTIFACTS_SUBPATH  # noqa: E402
from framework._runtime.state._lifecycle_state import LifecycleState  # noqa: E402


def state_path(repo_root, module, ticket):
    # Pure function of an explicit root. The CLI feeds the ARTIFACTS root
    # (resolve_artifacts_root); the engine and other importers feed their own. The
    # `.lifecycle/changes` subpath is centralized in ARTIFACTS_SUBPATH (T2 flips
    # it to `.lifecycle/changes`). <TICKET-ID>.
    return repo_root / ARTIFACTS_SUBPATH / module / 'state' / f'{ticket}.yml'


def load_state(path):
    if not path.is_file():
        return None
    try:
        with path.open(encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError('state file root is not a mapping')
        return data
    except (yaml.YAMLError, ValueError) as e:
        raise StateParseError(f'cannot parse state file {path}: {e}')


class _StateLock:
    """fcntl-based file lock on state.yml. Linux/macOS only.

    Mode 'exclusive' is held by /advance writers; 'shared' by /check + /state
    readers. On acquire timeout (5s) exits non-zero with rule-id LCK-001.
    """

    def __init__(self, path, mode='exclusive'):
        self.path = path
        self.mode = mode
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open('a+', encoding='utf-8')
        flag = fcntl.LOCK_EX if self.mode == 'exclusive' else fcntl.LOCK_SH
        flag |= fcntl.LOCK_NB
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(self._fh.fileno(), flag)
                return self
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() > deadline:
                    self._fh.close()
                    self._fh = None
                    print(
                        f'ERROR [LCK-001]: could not acquire {self.mode} lock on '
                        f'{self.path} within {LOCK_TIMEOUT_SECONDS}s (another agent '
                        f'holds it). Wait + retry, or investigate orphan lock.',
                        file=sys.stderr,
                    )
                    raise LockTimeout()
                time.sleep(0.05)

    def __exit__(self, *exc):
        if self._fh is not None:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
            self._fh = None
        return False


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as fh:
        yaml.safe_dump(state, fh, sort_keys=False, default_flow_style=False, width=100)


# Field names that MUST be preserved as strings (no int / bool / null
# coercion in parse_field_value). YAML safe_dump auto-quotes strings whose
# content would otherwise round-trip as a non-string scalar, so this set
# guarantees that all-digit and hex-leading-digit Git short SHAs write as
# quoted YAML scalars and load back as strings without schema violation.
# <TICKET-ID> framework release layer.
STRING_ONLY_FIELDS = {"merge_commit"}


def parse_field_value(raw):
    """Convert `key=value` value strings to typed Python values.

    Returns: bool / None / int / list / str (in that priority order).
    Floats are intentionally NOT autocast — float() silently overflows
    SHA-like values matching <digits>e<digits> (e.g. '3e24088') to inf.
    """
    if raw.lower() == 'true':  return True
    if raw.lower() == 'false': return False
    if raw.lower() == 'null':  return None
    try: return int(raw)
    except ValueError: pass
    if raw.startswith('[') and raw.endswith(']'):
        inner = raw[1:-1].strip()
        if not inner: return []
        return [parse_field_value(x.strip()) for x in inner.split(',')]
    return raw


def run_validator(repo_root, target):
    validator = repo_root / 'forge' / 'tools' / 'validate-artifact.py'
    if not validator.is_file():
        return None, 'validate-artifact.py not found; skipping schema validation'
    proc = subprocess.run(
        [sys.executable, str(validator), str(target), '--quiet'],
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def init_state(repo_root, ticket, module, sprint=None):
    """Invoke init-state.py to bootstrap a state file (used by /enrich-us)."""
    initializer = repo_root / 'forge' / 'tools' / 'init-state.py'
    if not initializer.is_file():
        return 2, 'init-state.py not found; cannot bootstrap state'
    if sprint is None:
        return 2, '/enrich-us creating new state requires --sprint=<name>'
    proc = subprocess.run(
        [sys.executable, str(initializer), ticket, module, sprint],
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


# ---------- Pure transition (shared by the CLI + the typed orchestrator API) ----------

def _advance_dict(state, command, fields, timestamp):
    """Mark the step done, merge already-validated `fields`, advance `state`.

    `fields` is a dict {allowed_key: typed_value} (validation is the caller's
    job — cmd_advance prints CLI errors; apply_advance raises). Mutates + returns
    the state dict. This is the single source of the advance transition (the CLI
    and the typed API both go through it — no duplication)."""
    rules = COMMAND_RULES[command]
    step_entry = state.setdefault('steps', {}).setdefault(command, {})
    step_entry['done'] = True
    step_entry['timestamp'] = timestamp
    for k, v in fields.items():
        step_entry[k] = v
    state['state'] = rules['advance_state']
    return state


# ---------- Subcommands (return an exit code; never sys.exit — that is run_cli's job) ----------

def cmd_check(args, repo_root):
    rules = COMMAND_RULES[args.command]
    path = state_path(resolve_artifacts_root(), args.module, args.ticket)

    if path.is_file():
        with _StateLock(path, mode='shared'):
            state = load_state(path)
    else:
        state = load_state(path)

    if state is None:
        if rules['creates_state_if_missing']:
            print(f'OK: state file does not yet exist; /{args.command} will create it via init-state.py.')
            return 0
        print(f'REFUSE: state file missing at {path}', file=sys.stderr)
        print(f'        Run /enrich-us first, or `init-state.py {args.ticket} {args.module} "<sprint>"` manually.',
              file=sys.stderr)
        return 2

    if rules['prereq'](state):
        cur = state.get('state', '(none)')
        print(f'OK: prerequisites met for /{args.command} (current state={cur})')
        return 0

    print(f'REFUSE: {rules["prereq_msg"]}', file=sys.stderr)
    print(f'        current state: {state.get("state")}', file=sys.stderr)
    print(f'        steps:', file=sys.stderr)
    for step_name, step in state.get('steps', {}).items():
        marker = 'DONE' if step.get('done') else '....'
        extras = []
        if 'verdict' in step: extras.append(f'verdict={step["verdict"]}')
        if 'schema_validated' in step: extras.append(f'schema_validated={step["schema_validated"]}')
        suffix = f' ({", ".join(extras)})' if extras else ''
        print(f'          {step_name:<12} {marker}{suffix}', file=sys.stderr)
    return 1


def cmd_advance(args, repo_root):
    rules = COMMAND_RULES[args.command]
    path = state_path(resolve_artifacts_root(), args.module, args.ticket)

    # Bootstrap path: /enrich-us when state file does not yet exist.
    if not path.is_file() and rules['creates_state_if_missing']:
        rc, out = init_state(repo_root, args.ticket, args.module, args.sprint)
        if rc != 0:
            print(f'ERROR: init-state failed (rc={rc})', file=sys.stderr)
            if out: print(out, file=sys.stderr)
            return 2
        print(f'OK: state file created. /{args.command} done. state=enriched.')
        return 0

    with _StateLock(path, mode='exclusive'):
        state = load_state(path)
        if state is None:
            print(f'ERROR: state file missing at {path}; cannot advance.', file=sys.stderr)
            return 2

        if not rules['prereq'](state):
            print(f'REFUSE: cannot advance /{args.command} — {rules["prereq_msg"]}', file=sys.stderr)
            return 1

        # Parse + validate --field args (CLI concern; exact messages preserved).
        fields = {}
        for raw in (args.field or []):
            if '=' not in raw:
                print(f'ERROR: --field expects key=value (got {raw!r})', file=sys.stderr)
                return 2
            k, _, v = raw.partition('=')
            if k not in rules['allowed_fields']:
                print(f'ERROR: field {k!r} not allowed for /{args.command}. '
                      f'Allowed: {rules["allowed_fields"]}', file=sys.stderr)
                return 2
            # <TICKET-ID> framework release layer: bypass type-coercion for string-only fields
            # so numeric SHAs persist as quoted YAML scalars.
            fields[k] = v if k in STRING_ONLY_FIELDS else parse_field_value(v)

        step_key = args.command
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        _advance_dict(state, args.command, fields, timestamp)
        step_entry = state['steps'][step_key]
        save_state(path, state)

    print(f'OK: /{args.command} done. state={state["state"]}. step={step_key}.')
    for k, v in step_entry.items():
        if k in ('done', 'timestamp'): continue
        print(f'    {k}: {v}')

    if not args.no_validate:
        rc, out = run_validator(repo_root, path)
        if rc is None:
            print(f'    {out}')
        elif rc == 0:
            print('    validate-artifact: PASS')
        else:
            print(f'    validate-artifact: FAIL (rc={rc})', file=sys.stderr)
            if out: print(out, file=sys.stderr)
            print('    State file written, but does NOT validate. Investigate before continuing.', file=sys.stderr)
            return 1
    return 0


def cmd_state(args, repo_root):
    path = state_path(resolve_artifacts_root(), args.module, args.ticket)
    if path.is_file():
        with _StateLock(path, mode='shared'):
            state = load_state(path)
    else:
        state = load_state(path)
    if state is None:
        print(f'(no state file at {path})')
        return 2
    print(f'# {path}')
    yaml.safe_dump(state, sys.stdout, sort_keys=False, default_flow_style=False, width=100)
    return 0


# ---------- Typed orchestrator API (<TICKET-ID>; reuses LifecycleState from <TICKET-ID>) ----------

def load_state_typed(path) -> Optional[LifecycleState]:
    """Load a state.yml into the typed model (None if absent). Raises StateParseError on garbage."""
    d = load_state(path)
    return LifecycleState.from_state_dict(d) if d is not None else None


def evaluate_prereq(state, command) -> bool:
    """True if `command`'s prerequisite holds. Accepts a LifecycleState or a raw dict."""
    d = state.to_state_dict() if isinstance(state, LifecycleState) else state
    return bool(COMMAND_RULES[command]['prereq'](d))


def apply_advance(state, command, fields=None, timestamp=None) -> LifecycleState:
    """Pure in-RAM advance for the orchestrator: (LifecycleState) -> LifecycleState.

    Shares the exact transition with the CLI via `_advance_dict`. Validates the
    field keys (raises ValueError on a disallowed field). No disk I/O."""
    rules = COMMAND_RULES[command]
    d = state.to_state_dict() if isinstance(state, LifecycleState) else dict(state)
    fields = fields or {}
    bad = [k for k in fields if k not in rules['allowed_fields']]
    if bad:
        raise ValueError(f'field(s) {bad} not allowed for /{command}; allowed: {rules["allowed_fields"]}')
    ts = timestamp or datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    return LifecycleState.from_state_dict(_advance_dict(d, command, dict(fields), ts))


# ---------- CLI ----------

def run_cli(argv=None):
    """Relocated main(): parse argv, dispatch, RETURN the exit code (0/1/2/75)."""
    ap = argparse.ArgumentParser(
        prog='state-machine',
        description='Lifecycle state machine gate for ai-specs framework commands.',
    )
    sub = ap.add_subparsers(dest='subcommand', required=True)

    cmds = list(COMMAND_RULES.keys())

    pc = sub.add_parser('check', help='Verify prerequisites before running a lifecycle command')
    pc.add_argument('command', choices=cmds)
    pc.add_argument('ticket')
    pc.add_argument('module')

    pa = sub.add_parser('advance', help='Record completion of a lifecycle command in state.yml')
    pa.add_argument('command', choices=cmds)
    pa.add_argument('ticket')
    pa.add_argument('module')
    pa.add_argument('--field', action='append',
                    help='key=value pair to write into the step entry (repeatable). Allowed keys per command listed in --help-fields.')
    pa.add_argument('--sprint',
                    help='Sprint name (required when /enrich-us creates a new state file).')
    pa.add_argument('--no-validate', action='store_true',
                    help='Skip post-advance schema validation')

    ps = sub.add_parser('state', help='Print the current state YAML')
    ps.add_argument('ticket')
    ps.add_argument('module')

    args = ap.parse_args(argv)

    repo_root = find_repo_root(Path.cwd())
    if repo_root is None:
        print('ERROR: could not locate framework repo root (no forge/schemas/ in any parent).',
              file=sys.stderr)
        return 2

    try:
        if args.subcommand == 'check':
            return cmd_check(args, repo_root)
        elif args.subcommand == 'advance':
            return cmd_advance(args, repo_root)
        elif args.subcommand == 'state':
            return cmd_state(args, repo_root)
    except StateParseError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    except LockTimeout:
        return EX_TEMPFAIL
