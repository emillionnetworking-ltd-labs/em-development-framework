#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""init-state — FW-003 (framework release layer) · CLI shell.

Thin CLI entrypoint. All logic lives in the importable library `_init_state.py`
(ADR-006: forge/tools/ is not a package; the hyphen in this filename blocks
`import`, so the logic is a sibling underscore module). Invocation unchanged:
    python3 forge/tools/init-state.py <TICKET> <module> "<sprint>" [--force] ...

Exit codes (preserved): 0 created · 1 refused/bad-args/validation-fail · 2 fatal.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _init_state import run_cli  # noqa: E402

if __name__ == '__main__':
    sys.exit(run_cli(sys.argv[1:]))
