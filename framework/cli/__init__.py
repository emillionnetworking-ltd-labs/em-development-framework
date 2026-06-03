# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""framework.cli — the baton.

Post W64 SCRUM-632: orchestrator and the typed contracts are now siblings
under framework._runtime (relocated from top-level orchestrator/ and
forge/tools/). The framework package is fully self-contained — no sys.path
mutation needed. Imports resolve through normal Python package machinery.
"""

from pathlib import Path

# framework/cli/__init__.py -> parents[2] == repo root (em-development-framework/)
REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return REPO_ROOT
