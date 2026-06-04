#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""classify-deviation — FW-005 / framework release layer

Interactive (or scripted) deviation classifier using the 5-question decision
tree from workflow-standards.mdc §8. First YES wins; if all NO, the deviation
is Scope-Gap (blocks merge).

Categories:
  - Accepted-Trivial: cosmetic; no ticket, no block.
  - Accepted-Quality: reduced coverage / skipped test; Jira ticket in current sprint.
  - Accepted-Risk:    affects security; REQUIRES risk justification + user approval.
                      Creates Jira ticket if residual_risk > LOW.
  - Deferred:         postponed intentionally; Jira ticket in backlog.
  - Pre-existing:     bug predates this ticket; Jira ticket in current sprint.
  - Scope-Gap:        unjustified gap; BLOCKS — does not append to state.yml.

Closes the <TICKET-ID> failure mode (Accepted-Trivial self-classified without
passing through the tree) flagged by the architectural audit 2026-05-13.

Usage:
  classify-deviation.py <TICKET> <MODULE> --description "..." [interactive]
  classify-deviation.py <TICKET> <MODULE> --description "..." \\
      --step 5 --ref "verify#deviation-2" \\
      --affects-security=false --reduces-coverage=true \\
      --has-justification=false --postponed=false --pre-existing=false \\
      [--dry-run]

  # For Accepted-Risk (when --affects-security=true):
  classify-deviation.py <TICKET> <MODULE> --description "..." \\
      --affects-security=true \\
      --risk-description "..." \\
      --compensating-controls "..." \\
      --residual-risk HIGH|MEDIUM|LOW|NEGLIGIBLE \\
      --user-approved=true

Exit codes:
  0  classified + recorded (and Jira ticket created if applicable)
  1  blocked (Scope-Gap, Accepted-Risk without approval, etc.)
  2  fatal error (state file missing, bad args)
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import base64
from pathlib import Path

try:
    import yaml
except ImportError:
    print('ERROR: PyYAML not installed. Run: pip install --user pyyaml', file=sys.stderr)
    sys.exit(2)


def _load_taxonomy():
    """Load the deviation taxonomy SSoT (<TICKET-ID>, framework release layer).

    The 6 categories and the 5-question decision tree live in
    `forge/.deviation-taxonomy.yml` (governed by `deviation-taxonomy.schema.yml`).
    Loading at import time rebuilds CATEGORIES + QUESTIONS from that single
    source — eliminating drift between this file and workflow-standards.mdc §8.
    Raises RuntimeError if the data file is unreachable (treat as repo-broken).
    """
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    from _common import find_framework_root  # noqa: E402
    root = find_framework_root()
    if root is None:
        raise RuntimeError("framework root not found; deviation taxonomy unavailable")
    tax_path = root / "forge" / ".deviation-taxonomy.yml"
    if not tax_path.is_file():
        raise RuntimeError(f"deviation taxonomy SSoT missing at {tax_path}")
    with tax_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cats = [c["name"] for c in data.get("categories", [])]
    qs = [(q["key"], q["prompt"], q["category"]) for q in data.get("questions", [])]
    return cats, qs


CATEGORIES, QUESTIONS = _load_taxonomy()

# Default Jira sprint and labels per category. For MVP we don't auto-create
# tickets for Pre-existing/Accepted-Risk; we only do it for Accepted-Quality
# and Deferred as the user requested. The other two can be added later.
JIRA_RULES = {
    'Accepted-Quality': {
        'sprint_target': 'current',
        'labels': ['tech-debt', 'deviation', 'auto-created'],
        'auto_create': True,
    },
    'Deferred': {
        'sprint_target': 'backlog',
        'labels': ['deferred', 'deviation', 'auto-created'],
        'auto_create': True,
    },
    'Pre-existing': {
        'sprint_target': 'current',
        'labels': ['pre-existing-bug', 'deviation', 'auto-created'],
        'auto_create': False,  # FW-005 MVP: scope per user request
    },
    'Accepted-Risk': {
        'sprint_target': 'current',
        'labels': ['accepted-risk', 'deviation', 'auto-created'],
        'auto_create': False,  # only create if residual > LOW; handled separately
    },
}


# ---------- helpers ----------

from framework._runtime.state._common import find_framework_install_root, resolve_artifacts_root, ARTIFACTS_SUBPATH  # noqa: E402
# Reuse the lifecycle's single locked writer + typed model:
# classify shares ONE flock-serialized writer with the state machine instead of
# owning a second, unsynchronized writer to state.yml.
from framework._runtime.state._state_machine import (  # noqa: E402
    _StateLock, StateParseError, LockTimeout,
    load_state as _load_state, save_state as _save_state,
)
from framework._runtime.state._lifecycle_state import Deviation  # noqa: E402


class Cancelled(Exception):
    """An interactive prompt was cancelled (EOF/Ctrl-C). run_cli maps it to exit 1.

    The lib raises; the CLI shell turns the returned int into the process exit
    code — so an importer (the orchestrator) is never killed by a stray exit."""


def state_path(repo_root, module, ticket):
    # Pure function of an explicit root; ARTIFACTS_SUBPATH centralizes the
    # subpath for T2. The CLI feeds the ARTIFACTS root. <TICKET-ID>.
    return repo_root / ARTIFACTS_SUBPATH / module / 'state' / f'{ticket}.yml'


def run_validator(repo_root, target):
    validator = repo_root / 'forge' / 'tools' / 'validate-artifact.py'
    if not validator.is_file():
        return None, 'validate-artifact.py not found; skipping'
    proc = subprocess.run(
        [sys.executable, str(validator), str(target), '--quiet'],
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def parse_bool_flag(raw):
    """For --foo=value form. Accepts true/false/yes/no/y/n/1/0 (case-insensitive)."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ('true', 'yes', 'y', '1'):  return True
    if s in ('false', 'no', 'n', '0'):  return False
    raise ValueError(f'cannot parse bool from {raw!r}')


def prompt_yn(question, default=None):
    """Returns True/False. default is the answer if user hits Enter."""
    suffix = ' [y/N]' if default is False else ' [Y/n]' if default is True else ' [y/n]'
    while True:
        try:
            ans = input(f'{question}{suffix}: ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            raise Cancelled()
        if not ans and default is not None: return default
        if ans in ('y', 'yes'): return True
        if ans in ('n', 'no'):  return False
        print(f'  Answer y or n.')


# ---------- classification ----------

def classify(answers):
    """Apply the decision tree. First YES wins. Returns category string."""
    for key, _, category in QUESTIONS:
        if answers.get(key) is True:
            return category
    return 'Scope-Gap'


def classify_typed(answers, *, description, step=None, ref=None,
                   risk_description=None, compensating_controls=None,
                   residual_risk=None, user_approved=None, jira_ticket=None):
    """Pure, in-RAM classification → a typed `Deviation` (no disk write, no Jira).

    The orchestrator's entry point: classify a deviation as a value object and
    route on it. Raises ValueError for a Scope-Gap (it blocks — the caller turns
    that into a graph edge), mirroring the CLI's refusal."""
    category = classify(answers)
    if category == 'Scope-Gap':
        raise ValueError('Scope-Gap: deviation blocks; implement the step or reclassify.')
    return Deviation(
        category=category,
        description=description,
        step=str(step) if step is not None else None,
        ref=ref,
        jira_ticket=jira_ticket,
        risk_description=risk_description,
        compensating_controls=compensating_controls,
        residual_risk=residual_risk,
        user_approved=user_approved,
    )


def get_current_sprint(jira_email, jira_token, base, board_id=1):
    """Return the active sprint's ID, or None."""
    req = urllib.request.Request(
        f'{base}/rest/agile/1.0/board/{board_id}/sprint?state=active&maxResults=5',
        headers={
            'Accept': 'application/json',
            'Authorization': 'Basic ' + base64.b64encode(
                f'{jira_email}:{jira_token}'.encode()).decode(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f'WARN: could not list active sprints: {e}', file=sys.stderr)
        return None
    sprints = data.get('values', [])
    if not sprints:
        return None
    # If multiple active sprints (e.g., internal cycle+13+14), pick the one with highest ID (most recent).
    return max(sprints, key=lambda s: s['id'])['id']


def create_jira_ticket(category, description, parent_ticket, args, repo_root):
    """Create a Jira sub-ticket for the deviation. Returns the new key or None."""
    email = os.environ.get('JIRA_EMAIL')
    token = os.environ.get('JIRA_TOKEN')
    base = os.environ.get('JIRA_BASE')
    if not email or not token or not base:
        print('WARN: JIRA_EMAIL / JIRA_TOKEN / JIRA_BASE not set; skipping Jira creation. '
              'Set all three environment variables (JIRA_BASE = https://<your-org>.atlassian.net).',
              file=sys.stderr)
        return None

    rules = JIRA_RULES.get(category, {})
    labels = list(rules.get('labels', []))
    labels.append(f'parent-{parent_ticket}')

    short = description[:140] + ('...' if len(description) > 140 else '')
    summary = f'[{category}] {short}'

    desc_doc = {
        'type': 'doc', 'version': 1,
        'content': [
            {'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'Deviation classified by /classify-deviation (FW-005).'}
            ]},
            {'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'Parent ticket: ', 'marks': [{'type': 'strong'}]},
                {'type': 'text', 'text': parent_ticket},
            ]},
            {'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'Category: ', 'marks': [{'type': 'strong'}]},
                {'type': 'text', 'text': category},
            ]},
            {'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'Description: ', 'marks': [{'type': 'strong'}]},
                {'type': 'text', 'text': description},
            ]},
        ],
    }
    if args.step is not None:
        desc_doc['content'].append({'type': 'paragraph', 'content': [
            {'type': 'text', 'text': 'Plan step: ', 'marks': [{'type': 'strong'}]},
            {'type': 'text', 'text': str(args.step)},
        ]})
    if args.ref:
        desc_doc['content'].append({'type': 'paragraph', 'content': [
            {'type': 'text', 'text': 'Reference: ', 'marks': [{'type': 'strong'}]},
            {'type': 'text', 'text': args.ref},
        ]})

    payload = {
        'fields': {
            'project': {'key': 'SCRUM'},
            'issuetype': {'name': 'Task'},
            'summary': summary[:250],
            'description': desc_doc,
            'labels': labels,
        }
    }

    req = urllib.request.Request(
        f'{base}/rest/api/3/issue',
        data=json.dumps(payload).encode(),
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + base64.b64encode(f'{email}:{token}'.encode()).decode(),
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        print(f'ERROR: Jira create returned HTTP {e.code}: {body[:300]}', file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f'ERROR: Jira create failed: {e}', file=sys.stderr)
        return None

    new_key = data.get('key')
    if not new_key:
        print(f'ERROR: Jira create returned no key: {data}', file=sys.stderr)
        return None

    # Assign to sprint if rule says so.
    target = rules.get('sprint_target')
    if target == 'current':
        sprint_id = get_current_sprint(email, token, base)
        if sprint_id:
            req = urllib.request.Request(
                f'{base}/rest/agile/1.0/sprint/{sprint_id}/issue',
                data=json.dumps({'issues': [new_key]}).encode(),
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Authorization': 'Basic ' + base64.b64encode(f'{email}:{token}'.encode()).decode(),
                },
                method='POST',
            )
            try:
                urllib.request.urlopen(req, timeout=10)
            except urllib.error.URLError as e:
                print(f'WARN: could not assign {new_key} to sprint {sprint_id}: {e}', file=sys.stderr)
    # target='backlog' means leave unassigned (Jira backlog).

    return new_key


# ---------- main flow ----------

def run_interactive(parent_ticket):
    """Walk the decision tree. Returns answers dict."""
    print(f'/classify-deviation interactive mode for {parent_ticket}')
    print(f'5-question decision tree (workflow-standards.mdc §8). First YES wins.')
    print(f'Categories: {", ".join(CATEGORIES)}.\n')
    answers = {}
    for i, (key, question, _) in enumerate(QUESTIONS, 1):
        print(f'[{i}/{len(QUESTIONS)}] {question}')
        ans = prompt_yn('    ', default=False)
        answers[key] = ans
        if ans:
            print(f'    -> {QUESTIONS[i-1][2]}')
            # Set remaining to False for completeness.
            for k, _, _ in QUESTIONS[i:]:
                answers[k] = False
            return answers
    return answers


def collect_risk_args(args):
    """For Accepted-Risk, gather (or validate) the risk-related fields."""
    fields = {
        'risk_description': args.risk_description,
        'compensating_controls': args.compensating_controls,
        'residual_risk': args.residual_risk,
        'user_approved': args.user_approved,
    }
    if args.interactive:
        if not fields['risk_description']:
            fields['risk_description'] = input('  Risk description (what is introduced): ').strip()
        if not fields['compensating_controls']:
            fields['compensating_controls'] = input('  Compensating controls in place: ').strip()
        if not fields['residual_risk']:
            while True:
                v = input('  Residual risk [HIGH/MEDIUM/LOW/NEGLIGIBLE]: ').strip().upper()
                if v in ('HIGH', 'MEDIUM', 'LOW', 'NEGLIGIBLE'):
                    fields['residual_risk'] = v
                    break
                print('    answer must be HIGH, MEDIUM, LOW, or NEGLIGIBLE.')
        if fields['user_approved'] is None:
            fields['user_approved'] = prompt_yn('  Has the user explicitly approved this risk?', default=False)
    return fields


def run_cli(argv=None):
    """Pure return-int contract (<TICKET-ID>, steel #5). The library never calls
    sys.exit: it returns an int (0 ok / 1 refusal-or-cancel / 2 usage-or-fatal /
    75 lock timeout) and the hyphen shell turns it into the process exit code, so
    an importer (the orchestrator) is never killed. prompt_yn raises `Cancelled`,
    caught here → exit 1. The state.yml append runs under the lifecycle's
    `_StateLock` (one flock-serialized writer). Manual CLI behavior is unchanged."""
    ap = argparse.ArgumentParser(
        prog='classify-deviation',
        description='Classify a plan deviation per the framework decision tree.',
    )
    ap.add_argument('ticket')
    ap.add_argument('module')
    ap.add_argument('--description', required=True,
                    help='Short description of what deviated (mandatory)')
    ap.add_argument('--step',
                    help='Plan step number or label (e.g., 5 or "Step 5")')
    ap.add_argument('--ref',
                    help='Anchor into verify or record doc (e.g., "verify#deviation-2")')

    # Five tree answers — bool flags.
    for key, q, _ in QUESTIONS:
        flag = '--' + key.replace('_', '-')
        ap.add_argument(flag, default=None,
                        help=f'(scripted) answer to: {q[:60]}...')

    # Accepted-Risk extras
    ap.add_argument('--risk-description', help='(Accepted-Risk) what risk is introduced')
    ap.add_argument('--compensating-controls', help='(Accepted-Risk) existing compensating controls')
    ap.add_argument('--residual-risk', choices=['HIGH', 'MEDIUM', 'LOW', 'NEGLIGIBLE'],
                    help='(Accepted-Risk) residual risk after compensating controls')
    ap.add_argument('--user-approved', help='(Accepted-Risk) explicit user approval (true/false)')

    # Behavior
    ap.add_argument('--interactive', action='store_true',
                    help='Force interactive mode even if some tree flags are provided')
    ap.add_argument('--dry-run', action='store_true',
                    help='Do not create Jira tickets and do not write state.yml; print what would happen.')
    ap.add_argument('--no-jira', action='store_true',
                    help='Skip Jira ticket creation but DO write state.yml')

    args = ap.parse_args(argv)
    try:
        return _classify_run(args)
    except Cancelled:
        print('(cancelled)', file=sys.stderr)
        return 1


def _classify_run(args):
    """Post-parse flow. Returns an int; raises Cancelled on prompt cancel."""
    # Coerce bool flags
    answers = {}
    have_any_flag = False
    for key, _, _ in QUESTIONS:
        # argparse stores --affects-security as args.affects_security
        raw = getattr(args, key)
        if raw is not None:
            have_any_flag = True
            try:
                answers[key] = parse_bool_flag(raw)
            except ValueError as e:
                print(f'ERROR: {e} (flag --{key.replace("_","-")})', file=sys.stderr)
                return 2
    # user-approved flag is separate
    if args.user_approved is not None:
        try:
            args.user_approved = parse_bool_flag(args.user_approved)
        except ValueError as e:
            print(f'ERROR: {e} (flag --user-approved)', file=sys.stderr)
            return 2

    # Decide mode
    if args.interactive or not have_any_flag:
        answers = run_interactive(args.ticket)
        args.interactive = True
    else:
        # Fill missing answers as False
        for key, _, _ in QUESTIONS:
            answers.setdefault(key, False)

    category = classify(answers)
    print(f'\nclassification: {category}')

    # ----- per-category gates -----
    if category == 'Scope-Gap':
        print('REFUSE: Scope-Gap blocks. Either implement the missing step OR reclassify with justification.',
              file=sys.stderr)
        return 1

    if category == 'Accepted-Trivial':
        if not answers.get('has_justification'):
            print('REFUSE: Accepted-Trivial requires has-justification=true.', file=sys.stderr)
            return 1

    risk_fields = None
    if category == 'Accepted-Risk':
        risk_fields = collect_risk_args(args)
        missing = [k for k, v in risk_fields.items()
                   if v is None or (isinstance(v, str) and not v.strip())]
        if missing:
            print(f'REFUSE: Accepted-Risk requires: {missing}', file=sys.stderr)
            print('       Pass --risk-description, --compensating-controls, --residual-risk, --user-approved=true',
                  file=sys.stderr)
            return 1
        if risk_fields['user_approved'] is not True:
            print('REFUSE: Accepted-Risk requires --user-approved=true.', file=sys.stderr)
            return 1

    # ----- locate state.yml (skip in dry-run) -----
    repo_root = None
    sp = None
    if not args.dry_run:
        repo_root = find_framework_install_root(Path.cwd())
        if repo_root is None:
            print('ERROR: framework repo root not found (no forge/schemas/ in any parent of cwd).',
                  file=sys.stderr)
            print('       cd to the framework repo or a subdirectory before running.', file=sys.stderr)
            return 2
        sp = state_path(resolve_artifacts_root(), args.module, args.ticket)
        if not sp.is_file():
            print(f'ERROR: state file missing at {sp}', file=sys.stderr)
            return 2

    # ----- build deviation entry -----
    entry = {
        'category': category,
        'ref': args.ref or f'inline-{datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
    }
    if args.step is not None:
        try:
            entry['step'] = int(args.step)
        except (ValueError, TypeError):
            entry['step'] = args.step  # string OK per schema
    entry['description'] = args.description
    if risk_fields:
        entry['risk_description'] = risk_fields['risk_description']
        entry['compensating_controls'] = risk_fields['compensating_controls']
        entry['residual_risk'] = risk_fields['residual_risk']
        entry['user_approved'] = risk_fields['user_approved']

    # ----- Jira ticket (if applicable) -----
    rules = JIRA_RULES.get(category, {})
    will_create_jira = (
        rules.get('auto_create', False)
        and not args.dry_run
        and not args.no_jira
    )
    # Also auto-create for Accepted-Risk if residual > LOW
    if category == 'Accepted-Risk' and risk_fields and risk_fields['residual_risk'] in ('HIGH', 'MEDIUM'):
        will_create_jira = not args.dry_run and not args.no_jira

    if will_create_jira:
        new_key = create_jira_ticket(category, args.description, args.ticket, args, repo_root)
        if new_key:
            entry['jira_ticket'] = new_key
            print(f'created Jira ticket: {new_key}')
        else:
            print('WARN: Jira ticket could NOT be created. Entry written without jira_ticket field; '
                  'create manually and patch state.yml.', file=sys.stderr)
    else:
        if category in ('Accepted-Quality', 'Deferred') and args.dry_run:
            print(f'(dry-run) would create Jira ticket for {category}')
        if category in ('Pre-existing', 'Accepted-Risk'):
            print(f'(note) {category}: auto-create disabled in FW-005 MVP for this category. '
                  'Create Jira ticket manually if needed.')

    # ----- append to state.yml -----
    if args.dry_run:
        print('(dry-run) deviation entry:')
        print(yaml.safe_dump([entry], sort_keys=False, default_flow_style=False))
        return 0

    # Single locked writer: read-append-write atomically under the lifecycle's
    # _StateLock (no second unsynchronized writer to state.yml).
    try:
        with _StateLock(sp, mode='exclusive'):
            state = _load_state(sp)
            if state is None:
                print(f'ERROR: state file missing at {sp}', file=sys.stderr)
                return 2
            state.setdefault('deviations', [])
            state['deviations'].append(entry)
            _save_state(sp, state)
    except StateParseError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    except LockTimeout:
        return 75
    print(f'state.yml updated: {sp}')

    # ----- validate -----
    rc, out = run_validator(repo_root, sp)
    if rc is None:
        print(f'  {out}')
    elif rc == 0:
        print('  validate-artifact: PASS')
    else:
        print(f'  validate-artifact: FAIL (rc={rc})', file=sys.stderr)
        if out: print(out, file=sys.stderr)
        return 1
    return 0
