# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""framework.cli — the baton.

Post W64 SCRUM-632: orchestrator and the typed contracts are siblings
under framework._runtime. The framework package is fully self-contained.

Post W68 SCRUM-636: ``framework_install_root()`` replaces the previous
``repo_root()`` function. The new name makes the narrowed semantic explicit:
this function returns the framework's INSTALL location, used ONLY for finding
adjacent read-only resources (e.g. forge/tools/em-cli.py, forge/schemas/).
It is NEVER used as a write target. All writes go through
``Framework.output_dir`` per ADR-015's workspace-isolation absolute boundary.
"""

from pathlib import Path

# framework/cli/__init__.py -> parents[2] == framework install location
FRAMEWORK_INSTALL_ROOT = Path(__file__).resolve().parents[2]


def framework_install_root() -> Path:
    """Return the framework's INSTALL location.

    Used ONLY for finding adjacent read-only resources at runtime
    (forge/tools/em-cli.py, forge/schemas/, etc). NEVER used as a write
    target. See ``Framework.output_dir`` for the write-path boundary.
    """
    return FRAMEWORK_INSTALL_ROOT
