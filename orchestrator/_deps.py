# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Bootstrap for the orchestrator (framework release layer, <TICKET-ID>).

orchestrator/ is application code. It depends on the engine (forge/) ONE WAY
ONLY: it imports the read-only typed lifecycle libs from forge/tools and never
the reverse. forge/ stays specs/metadata; this dir is the app (like control-plane).
Engine dir renamed ai-specs/ → forge/ in <TICKET-ID>.

Resolves the repo root from this file's location (robust regardless of cwd) and
puts forge/tools on sys.path so the typed libs import cleanly.
"""

import sys
from pathlib import Path

# orchestrator/_deps.py -> parents[1] == repo root (em-development-framework/)
REPO_ROOT = Path(__file__).resolve().parents[1]
FORGE_TOOLS = REPO_ROOT / "forge" / "tools"

if str(FORGE_TOOLS) not in sys.path:
    sys.path.insert(0, str(FORGE_TOOLS))

# Read-only typed surface from forge/tools (one-way dependency).
from _lifecycle_state import LifecycleState, Deviation  # noqa: E402,F401
from _state_machine import (  # noqa: E402,F401
    load_state_typed, save_state, state_path,
    _StateLock, StateParseError, LockTimeout,
    apply_advance, evaluate_prereq,
)
from _validate_artifact import ValidationResult  # noqa: E402,F401


def repo_root() -> Path:
    return REPO_ROOT
