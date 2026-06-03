#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""pre-bash-guard — Claude Code PreToolUse hook on Bash.
Phase 2 hardening / <TICKET-ID> / observability gap 3.

Reads hook payload from stdin per Claude Code hook protocol:
    {"tool_name": "Bash", "tool_input": {"command": "..."}, "session_id": "..."}

Exit codes:
    0  = allow tool call (optional stderr message shown but non-blocking)
    2  = block tool call (stderr shown to user + agent)
    other = treated as hook error; tool proceeds (fail-open by Claude Code convention)

Rules (additive — extend the GUARDS list to add more):

| Rule | Pattern | Effect |
|---|---|---|
| no-verify-without-bypass | --no-verify on git commit/push | block unless /tmp/claude-bypass-marker-<sid> exists |
| force-push | git push --force OR --force-with-lease  | warn (allow, stderr message) |
| destructive-rm | rm -rf in writable paths (not /tmp) | warn |
| sudo-in-cwd | sudo within home or project dirs | warn |

Bypass mechanism: the operator manually `touch
/tmp/claude-bypass-marker-<session-id>` before re-running the bypassed
command. This guard checks for the marker, consumes it (one-shot), and
allows the next --no-verify. Without marker → block. The manual step is
intentional: --no-verify should be a deliberate per-incident decision.
"""

import json
import os
import re
import sys
from pathlib import Path


MARKER_DIR = Path('/tmp')


def read_payload():
    try:
        return json.loads(sys.stdin.read() or '{}')
    except json.JSONDecodeError:
        return {}


def check_no_verify(command, session_id):
    """Return (block, message). block=True → exit 2."""
    if '--no-verify' not in command:
        return False, None
    if not re.search(r'\bgit\s+(commit|push|merge|rebase)', command):
        return False, None
    marker = MARKER_DIR / f'claude-bypass-marker-{session_id}'
    if marker.is_file():
        # One-shot consume.
        try:
            marker.unlink()
        except OSError:
            pass
        return False, (
            f'pre-bash-guard: --no-verify ALLOWED — bypass marker consumed '
            f'({marker.name}). Marker is one-shot; subsequent --no-verify '
            f'in this session will be blocked unless a new marker is touched.'
        )
    return True, (
        'pre-bash-guard: --no-verify BLOCKED.\n'
        'Reason: framework requires explicit bypass justification.\n'
        f'Action: manually `touch /tmp/claude-bypass-marker-{session_id}`\n'
        '  BEFORE re-running this command. Marker is one-shot.\n'
        'Reference: workflow-standards.mdc §15 (AUTH change-control) explicitly\n'
        '  forbids --no-verify on AUTH commits even with bypass.'
    )


def check_force_push(command):
    """Return warning message if force push, else None."""
    if re.search(r'\bgit\s+push\b.*(--force\b|--force-with-lease\b|-f\b)', command):
        return ('pre-bash-guard: WARNING — git push --force / --force-with-lease detected. '
                'Force-pushing to main/master is forbidden; for branch pushes verify the '
                'remote is the right one. Continuing.')
    return None


def check_destructive_rm(command):
    if not re.search(r'\brm\b.*-r[fF]?[fF]?', command):
        return None
    # Allow obvious /tmp + ad-hoc dirs.
    if re.search(r'rm\s+-r[fF]+\s+(/tmp/|tmp/|node_modules\b|\.next\b|coverage\b|dist\b|build\b)',
                 command):
        return None
    return ('pre-bash-guard: WARNING — rm -rf detected outside /tmp/build-dirs. '
            'Verify the path before allowing. Continuing.')


def check_sudo(command):
    if not re.search(r'\bsudo\b', command):
        return None
    return ('pre-bash-guard: WARNING — sudo detected. Verify this is an authorised '
            'system operation. Continuing.')


def main():
    payload = read_payload()
    tool_name = payload.get('tool_name', '')
    if tool_name != 'Bash':
        sys.exit(0)
    command = (payload.get('tool_input') or {}).get('command', '')
    if not command:
        sys.exit(0)
    session_id = payload.get('session_id') or os.environ.get('CLAUDE_SESSION_ID', 'unknown')

    # Rule 1: --no-verify (blocking unless bypass marker).
    block, msg = check_no_verify(command, session_id)
    if block:
        print(msg, file=sys.stderr)
        sys.exit(2)
    if msg:
        print(msg, file=sys.stderr)

    # Rule 2-4: warnings (non-blocking).
    for check in (check_force_push, check_destructive_rm, check_sudo):
        warn = check(command)
        if warn:
            print(warn, file=sys.stderr)

    sys.exit(0)


if __name__ == '__main__':
    main()
