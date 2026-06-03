# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_common.py — shared helpers for forge/tools/ scripts.

Centralizes `find_framework_root()` (formerly duplicated as 26 local
definitions across 26 tools). <TICKET-ID> / Phase 8 follow-up of <TICKET-ID> T-5.

Default `start=None` uses this module's parent directory (i.e. the
`forge/tools/` directory), making invocation cwd-independent.

Backward-compat: `find_repo_root = find_framework_root` is exported as
an alias so existing imports under either name keep working. Engine dir
renamed `ai-specs/` → `forge/` in <TICKET-ID>.
"""

import os
from pathlib import Path
from typing import Optional


def find_framework_root(start: Optional[Path] = None) -> Optional[Path]:
    """Find the em-development-framework root directory.

    Args:
        start: Directory to start walking upward from. If None, uses
            this module's parent directory (cwd-independent default).

    Returns:
        Path to the framework root (the directory containing
        `forge/schemas/`), or None if not found.

    Behavior:
        1. Walk upward looking for `forge/schemas/` (matches the
           framework root directly).
        2. If a parent is itself named `forge` AND has a `schemas/`
           subdirectory, return its parent (handles invocation from
           inside `forge/`).
        3. Fallback: check the canonical install path
           `~/projects/em-development-framework`.
        4. Return None if nothing matches.
    """
    if start is None:
        start = Path(__file__).resolve().parent
    p = Path(start).resolve()
    for parent in [p] + list(p.parents):
        if (parent / 'forge' / 'schemas').is_dir():
            return parent
        if parent.name == 'forge' and (parent / 'schemas').is_dir():
            return parent.parent
    canonical = Path.home() / 'projects' / 'em-development-framework'
    if (canonical / 'forge' / 'schemas').is_dir():
        return canonical
    return None


find_repo_root = find_framework_root


# --- Artifacts root (<TICKET-ID> / framework release layer; renamed <TICKET-ID>) --------------
#
# The engine location (find_framework_root, above) and the location of the
# governed project's artifacts are DISTINCT concepts. Artifacts (plans/records/
# verify/state) are the project's DATA — they live in `.lifecycle/artifacts/`,
# separate from the engine dir `forge/`. <TICKET-ID> renamed the data dir from
# the prior `.ai-specs/changes/` → `.lifecycle/artifacts/` and the env var
# `AI_SPECS_ROOT` → `LIFECYCLE_ROOT` for orthogonal naming.
ARTIFACTS_SUBPATH = Path('.lifecycle') / 'artifacts'

# Env var to point the artifacts root at a governed project explicitly.
ARTIFACTS_ROOT_ENV = 'LIFECYCLE_ROOT'


def resolve_artifacts_root(start: Optional[Path] = None) -> Optional[Path]:
    """Resolve the root under which the governed project's `artifacts/` lives.

    Resolution order:
      1. Explicit env `LIFECYCLE_ROOT` — used verbatim if set.
      2. Marker walk — nearest ancestor of `start` containing a `.lifecycle/`
         directory.
      3. Fallback — `find_framework_root()` (dogfood default; coincides with
         the engine root, so the default path is unchanged).

    Distinct from `find_framework_root()`, which locates the ENGINE
    (schemas/tools). This locates the DATA.
    """
    env = os.environ.get(ARTIFACTS_ROOT_ENV)
    if env:
        return Path(env).expanduser().resolve()
    if start is None:
        start = Path.cwd()
    p = Path(start).resolve()
    for parent in [p] + list(p.parents):
        if (parent / '.lifecycle').is_dir():
            return parent
    return find_framework_root()


def _atomic_write(path: Path, content: str) -> None:
    """POSIX-atomic file write via .tmp + os.replace.

    Write to sibling .tmp, then os.replace to target. Mid-write kill
    leaves orphan .tmp but target is unchanged until rename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(content, encoding='utf-8')
    os.replace(tmp, path)
