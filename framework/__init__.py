# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""framework/ — the em-development-framework public package.

Post W64 SCRUM-632: framework is fully self-contained. It holds the public
Framework API class (api.py), the CLI 'baton' (cli/) that drives the compiled
LangGraph brains, and the relocated runtime engine internals (_runtime/).

Public API:
    from framework import Framework
    fw = Framework(output_dir="./my-workspace")

CLI:
    python -m framework.cli.run --mode lifecycle ...
"""

from framework.api import Framework

__all__ = ["Framework"]
