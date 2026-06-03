#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""validate-artifact — FW-002 / framework release layer · CLI shell.

Thin CLI entrypoint. All logic lives in the importable library
`_validate_artifact.py` (ADR-006: forge/tools/ is not a package; the hyphen
in this filename blocks `import`, so the logic is a sibling underscore module).
Invocation is unchanged: `python3 forge/tools/validate-artifact.py <file> ...`.

Exit codes (preserved):
  0   PASS / SKIP
  1   FAIL (schema errors)
  2   ERROR (parse error, missing schema, file not found, etc.)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _validate_artifact import run_cli  # noqa: E402

if __name__ == '__main__':
    sys.exit(run_cli(sys.argv[1:]))
