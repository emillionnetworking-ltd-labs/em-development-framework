#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""state-machine — FW-004 lifecycle gate · CLI shell.

Thin CLI entrypoint. All logic lives in the importable library `_state_machine.py`
(ADR-006: forge/tools/ is not a package; the hyphen in this filename blocks
`import`, so the logic is a sibling underscore module). Invocation unchanged:
    python3 forge/tools/state-machine.py {check|advance|state} <cmd> <ticket> <module> ...

Exit codes (preserved): 0 OK · 1 refused/prereq/validate-fail · 2 missing/parse/
usage/field-error/no-root · 75 (EX_TEMPFAIL) lock-acquire timeout (LCK-001).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state_machine import run_cli  # noqa: E402

if __name__ == '__main__':
    sys.exit(run_cli(sys.argv[1:]))
