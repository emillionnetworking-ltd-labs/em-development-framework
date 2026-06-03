# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""framework.cli — the baton.

Bootstraps the one-way read-only path to orchestrator/ + forge/tools so the CLI
can import the compiled LangGraph brains and the typed lifecycle libs as top-level
modules (the same convention orchestrator/_deps.py uses). Importing any submodule
triggers this bootstrap. Engine dir renamed ai-specs/ → forge/ in <TICKET-ID>.
"""

import sys
from pathlib import Path

# framework/cli/__init__.py -> parents[2] == repo root (em-development-framework/)
REPO_ROOT = Path(__file__).resolve().parents[2]

for _p in (REPO_ROOT / "orchestrator", REPO_ROOT / "forge" / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def repo_root() -> Path:
    return REPO_ROOT
