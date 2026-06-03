# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Bootstrap for the orchestrator runtime (framework release layer).

orchestrator is application code that depends on the engine state contracts
ONE WAY ONLY: it imports the read-only typed lifecycle libs from
framework._runtime.state and never the reverse.

Post W64 SCRUM-632 relocation: orchestrator moved from top-level orchestrator/
to framework/_runtime/orchestrator/. Typed contracts moved from forge/tools/
into framework/_runtime/state/. The sys.path mutation that previously added
forge/tools/ to path is REMOVED — framework is now self-contained.
"""

from pathlib import Path

# framework/_runtime/orchestrator/_deps.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

# Read-only typed surface from the sibling state subpackage.
from framework._runtime.state._lifecycle_state import LifecycleState, Deviation  # noqa: F401
from framework._runtime.state._state_machine import (  # noqa: F401
    load_state_typed, save_state, state_path,
    _StateLock, StateParseError, LockTimeout,
    apply_advance, evaluate_prereq,
)
from framework._runtime.state._validate_artifact import ValidationResult  # noqa: F401


def repo_root() -> Path:
    return REPO_ROOT
