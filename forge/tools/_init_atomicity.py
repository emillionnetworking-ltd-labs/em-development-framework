# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_init_atomicity.py - Strategy v3 Wave B <TICKET-ID>.

Atomic rollback safety primitives for em-cli init flows. Six provable-by-
construction safety invariants:

(i)   _safe_mkdir early-returns if path.exists() -> operator pre-existing
      dirs NEVER tracked -> NEVER removed on rollback.
(ii)  _safe_write raises FileExistsError if path.exists() -> operator
      pre-existing files NEVER overwritten silently -> NEVER tracked.
(iii) _rollback uses path.rmdir() not shutil.rmtree() -> fails safely on
      non-empty dirs -> operator additions made between create + rollback
      are PRESERVED.
(iv)  Cross-platform via pathlib stdlib. Windows file-lock during unlink
      raises OSError -> caught + logged as partial rollback warning.
(v)   Reverse-order iteration -> files removed before parent dirs -> no
      premature non-empty failures.
(vi)  Single-process rollback runs as same user as init -> no cross-user
      permission issues (out-of-scope).

Usage:
    from _init_atomicity import (
        INSTALLED_FILES, _safe_mkdir, _safe_write, _rollback,
    )

    INSTALLED_FILES.clear()  # fresh tracker per invocation
    try:
        _safe_mkdir(some_dir)
        _safe_write(some_file, content)
        # ... etc
    except (OSError, FileExistsError) as e:
        _rollback(f'{type(e).__name__}: {e}')
        return 3
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

Kind = Literal["dir", "file"]
INSTALLED_FILES: list[tuple[Path, Kind]] = []


def _safe_mkdir(path: Path) -> None:
    """Create dir + register for rollback ONLY if newly created.

    Invariant (i): operator pre-existing dirs NEVER tracked, NEVER removed.
    """
    if path.exists():
        return
    path.mkdir(parents=True, exist_ok=False)
    INSTALLED_FILES.append((path, "dir"))


def _safe_write(path: Path, content: str) -> None:
    """Write file + register ONLY if newly created.

    Invariant (ii): refuses to overwrite operator pre-existing files.
    Caller catches FileExistsError + handles (typically: surface to operator
    with --force pointer).
    """
    if path.exists():
        raise FileExistsError(
            f"{path} pre-exists - refusing overwrite (use em-cli init --force)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    INSTALLED_FILES.append((path, "file"))


def _rollback(reason: str) -> None:
    """Reverse-iterate INSTALLED_FILES + remove ONLY tracked entries.

    Files removed first (unlink). Dirs second (rmdir - fails safely on
    non-empty - operator additions preserved per invariant iii).

    Invariants (iii)-(vi) detailed in module docstring.
    """
    print(f"ROLLBACK: {reason}", file=sys.stderr)
    for path, kind in reversed(INSTALLED_FILES):
        try:
            if kind == "file" and path.is_file():
                path.unlink()
                print(f"  removed file: {path}", file=sys.stderr)
            elif kind == "dir" and path.is_dir():
                path.rmdir()
                print(f"  removed empty dir: {path}", file=sys.stderr)
        except OSError as e:
            print(f"  partial rollback skipped {path}: {e}", file=sys.stderr)
    INSTALLED_FILES.clear()
