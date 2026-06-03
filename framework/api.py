# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Public API surface for the em-development-framework.

Use Framework as the entrypoint for library consumers; CLI users can use
``python -m framework.cli.run`` directly (it wraps Framework internally).

Example::

    from framework import Framework
    fw = Framework(output_dir="./my-workspace")
    # fw.checkpoints_dir == Path("./my-workspace/checkpoints")
    # fw.sessions_dir == Path("./my-workspace/strategy-sessions")

Configuration precedence (highest to lowest, per ADR-015):

    1. CLI flag: ``--output-dir <path>`` (resolved by framework.cli.run)
    2. Constructor: ``Framework(output_dir="./path")``
    3. Env var: ``EM_FRAMEWORK_OUTPUT_DIR=/path``
    4. Config file: ``forge.config.yml::output_dir`` (dogfood-only)
    5. Default: ``.em-out/`` in current working directory

Legacy-mode trigger: when ``forge.config.yml`` exists at the cwd AND its
``output_dir`` is ``.`` or unset, the framework writes to repo-relative
paths (preserves the operator dogfood workflow for this very repo).
"""

import os
from pathlib import Path
from typing import Optional


# Default location when nothing else is configured.
DEFAULT_OUTPUT_DIRNAME = ".em-out"

# Subdirectory layout under output_dir:
CHECKPOINTS_SUBDIR = "checkpoints"
SESSIONS_SUBDIR = "strategy-sessions"

# Legacy-mode sentinel — when forge.config.yml::output_dir equals this, the
# framework writes to repo-relative paths (operator dogfood backwards-compat).
LEGACY_MODE_SENTINEL = "."

# Env var consulted in the precedence ladder.
ENV_VAR_OUTPUT_DIR = "EM_FRAMEWORK_OUTPUT_DIR"


def _legacy_paths_for_repo(repo_root: Path) -> tuple[Path, Path]:
    """Compute the legacy (pre-W65) checkpoint + session paths used by the
    operator dogfood workflow.

    Post W64 SCRUM-632 relocation, the historical paths
    ``orchestrator/.checkpoints/`` and ``orchestrator/.strategy-sessions/``
    map to ``framework/_runtime/orchestrator/.checkpoints/`` and
    ``framework/_runtime/orchestrator/.strategy-sessions/`` respectively
    (new sessions/checkpoints land at the new location; pre-W64 sessions
    remain at the legacy location per ADR-015 §Consequences).
    """
    orch = repo_root / "framework" / "_runtime" / "orchestrator"
    return orch / ".checkpoints", orch / ".strategy-sessions"


def resolve_output_dir(
    *,
    cli_value: Optional[str] = None,
    ctor_value: Optional[str] = None,
    config_file_value: Optional[str] = None,
    config_file_exists: bool = False,
    cwd: Optional[Path] = None,
) -> Path:
    """Resolve the output directory per the 5-level precedence ladder.

    Returns a Path. Does NOT consult the legacy-mode trigger — that's the
    caller's responsibility (typically the session builder needs to check
    whether to use repo-relative paths).

    Args:
        cli_value: From ``--output-dir`` flag (highest priority).
        ctor_value: From ``Framework(output_dir=...)``.
        config_file_value: From ``forge.config.yml::output_dir`` (use
            ``LEGACY_MODE_SENTINEL`` to signal dogfood mode).
        config_file_exists: Whether forge.config.yml was present at all.
        cwd: Working directory for the default fallback (overridable for tests).

    Returns:
        Resolved Path. Path may not exist yet; caller is responsible for
        ensuring parents exist before writing.
    """
    if cli_value:
        return Path(cli_value)
    if ctor_value:
        return Path(ctor_value)
    env = os.environ.get(ENV_VAR_OUTPUT_DIR)
    if env:
        return Path(env)
    if config_file_value and config_file_value != LEGACY_MODE_SENTINEL:
        return Path(config_file_value)
    base = cwd if cwd is not None else Path.cwd()
    return base / DEFAULT_OUTPUT_DIRNAME


def is_legacy_mode(
    *,
    cli_value: Optional[str] = None,
    ctor_value: Optional[str] = None,
    config_file_value: Optional[str] = None,
    config_file_exists: bool = False,
) -> bool:
    """Detect whether legacy-mode applies (dogfood preservation).

    Legacy mode kicks in when:
      - No CLI override
      - No constructor override
      - No env var override
      - forge.config.yml exists AND its output_dir is ``.`` or unset

    In legacy mode the session builders use repo-relative paths instead
    of the configured output_dir.
    """
    if cli_value or ctor_value:
        return False
    if os.environ.get(ENV_VAR_OUTPUT_DIR):
        return False
    if not config_file_exists:
        return False
    return config_file_value is None or config_file_value == LEGACY_MODE_SENTINEL


class Framework:
    """Entrypoint for em-development-framework operations.

    Constructor performs precedence resolution against (a) the explicit
    ``output_dir`` arg, (b) the env var, (c) the default ``.em-out/`` in cwd.
    CLI flag and forge.config.yml integration happen at the session-builder
    layer (framework.cli._session) which calls ``resolve_output_dir``.

    Args:
        output_dir: Optional explicit path. If None, the env var
            ``EM_FRAMEWORK_OUTPUT_DIR`` is consulted; if also unset,
            defaults to ``Path.cwd() / ".em-out"``.

    Attributes:
        output_dir: The resolved output directory.
        checkpoints_dir: ``output_dir / "checkpoints"``.
        sessions_dir: ``output_dir / "strategy-sessions"``.
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir: Path = resolve_output_dir(ctor_value=output_dir)
        self.checkpoints_dir: Path = self.output_dir / CHECKPOINTS_SUBDIR
        self.sessions_dir: Path = self.output_dir / SESSIONS_SUBDIR

    def __repr__(self) -> str:
        return f"Framework(output_dir={str(self.output_dir)!r})"
