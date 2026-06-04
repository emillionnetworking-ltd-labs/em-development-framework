# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Public API surface for the em-development-framework.

Use Framework as the entrypoint for library consumers; CLI users can use
``python -m framework.cli.run`` directly (it wraps Framework internally).

Example::

    from framework import Framework
    fw = Framework(output_dir="./my-workspace")
    # fw.artifact_root == Path("./my-workspace")
    # fw.checkpoints_dir == Path("./my-workspace/checkpoints")
    # fw.sessions_dir == Path("./my-workspace/strategy-sessions")
    # state.yml writes land at:
    #   ./my-workspace/.lifecycle/artifacts/<module>/state/<ticket>.yml

Workspace isolation absolute boundary (W68 SCRUM-636):

The framework's INSTALL directory is treated as read-only at runtime.
Every write triggered by framework execution — state.yml, plan/verify/record
artifacts, langgraph checkpoints, strategy session snapshots — lands inside
the user-controlled ``output_dir``. There is no asymmetric behavior between
dogfood and end-user environments; the same logic applies everywhere.

Configuration precedence (highest → lowest):

    1. CLI flag: ``--output-dir <path>``
    2. Constructor: ``Framework(output_dir="./path")``
    3. Env var: ``EM_FRAMEWORK_OUTPUT_DIR=/path``
    4. Config file: ``forge.config.yml::output_dir``
    5. Default: ``.em-out/`` in current working directory
"""

import os
from pathlib import Path
from typing import Optional


# Default location when nothing else is configured.
DEFAULT_OUTPUT_DIRNAME = ".em-out"

# Subdirectory layout under output_dir.
CHECKPOINTS_SUBDIR = "checkpoints"
SESSIONS_SUBDIR = "strategy-sessions"

# Env var consulted in the precedence ladder.
ENV_VAR_OUTPUT_DIR = "EM_FRAMEWORK_OUTPUT_DIR"


def resolve_output_dir(
    *,
    cli_value: Optional[str] = None,
    ctor_value: Optional[str] = None,
    config_file_value: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> Path:
    """Resolve the absolute output directory per the precedence ladder.

    Args:
        cli_value: From ``--output-dir`` flag (highest priority).
        ctor_value: From ``Framework(output_dir=...)``.
        config_file_value: From ``forge.config.yml::output_dir``.
        cwd: Working directory for the default fallback (overridable for tests).

    Returns:
        Resolved Path. Caller is responsible for ensuring parents exist
        before writing.
    """
    if cli_value:
        return Path(cli_value)
    if ctor_value:
        return Path(ctor_value)
    env = os.environ.get(ENV_VAR_OUTPUT_DIR)
    if env:
        return Path(env)
    if config_file_value:
        return Path(config_file_value)
    base = cwd if cwd is not None else Path.cwd()
    return base / DEFAULT_OUTPUT_DIRNAME


class Framework:
    """Entrypoint for em-development-framework operations.

    ``output_dir`` is the ABSOLUTE root for all generated state. Every write
    triggered by framework execution lands inside ``output_dir``. The framework
    installation directory is read-only at runtime.

    Args:
        output_dir: Optional explicit path. If None, the env var
            ``EM_FRAMEWORK_OUTPUT_DIR`` is consulted; if also unset,
            defaults to ``Path.cwd() / ".em-out"``.

    Attributes:
        output_dir: The resolved output directory.
        artifact_root: Alias of output_dir; used downstream by paths that
            treat it as the root for the ``.lifecycle/artifacts/...`` tree.
        checkpoints_dir: ``output_dir / "checkpoints"``.
        sessions_dir: ``output_dir / "strategy-sessions"``.

    Raises:
        OSError: If the resolved ``output_dir``'s parent directory is not
            writable (early-fail pre-flight check).
    """

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir: Path = resolve_output_dir(ctor_value=output_dir)
        # Pre-flight: parent must be writable. Fail loudly at construction.
        parent = self.output_dir.parent if self.output_dir.parent != Path("") else Path.cwd()
        if parent.exists() and not os.access(parent, os.W_OK):
            raise OSError(
                f"output_dir parent {parent!s} is not writable. "
                f"Framework cannot persist state. Choose a writable location "
                f"or chmod the parent."
            )
        self.artifact_root: Path = self.output_dir
        self.checkpoints_dir: Path = self.output_dir / CHECKPOINTS_SUBDIR
        self.sessions_dir: Path = self.output_dir / SESSIONS_SUBDIR

    def __repr__(self) -> str:
        return f"Framework(output_dir={str(self.output_dir)!r})"
