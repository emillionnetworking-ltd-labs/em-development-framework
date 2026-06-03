#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Command catalog loader (<TICKET-ID>, framework release layer).

Typed reader for forge/commands.catalog.yml — the single machine-readable
source of the command surface + deviation taxonomy. Consumers: /help-framework
(reads via this lib indirectly through the catalog YAML), the MCP server, and
test_catalog.py which keeps the YAML and COMMANDS_REFERENCE.md in sync.

This is framework tooling (import-only lib, ADR-006-safe). No app code lives here.
"""

import sys
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

try:
    import yaml
except ImportError:  # pragma: no cover
    print('ERROR: PyYAML not installed.', file=sys.stderr)
    raise

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_repo_root  # noqa: E402

_STRICT = ConfigDict(extra='forbid')

CommandKind = Literal['skill', 'tool', 'lib']
CommandCategory = Literal['lifecycle', 'utility', 'audit', 'framework', 'support']
# Mirrors DeviationCategory in _lifecycle_state.py (kept here to avoid a hard import
# coupling; the schema enum is the contract, the round-trip test guards both).
TaxonomyCategory = Literal[
    'Accepted-Trivial', 'Accepted-Quality', 'Accepted-Risk',
    'Deferred', 'Pre-existing', 'Scope-Gap',
]


class Command(BaseModel):
    model_config = _STRICT
    name: str
    kind: CommandKind
    category: CommandCategory
    purpose: str
    invocation: Optional[str] = None
    gated_by: Optional[str] = None
    notes: Optional[str] = None
    user_invocable: Optional[bool] = None  # <TICKET-ID> framework release layer — operator visibility flag


class CategoryMeta(BaseModel):
    model_config = _STRICT
    category: TaxonomyCategory
    criteria: str
    blocks_merge: bool
    creates_ticket: bool
    sprint_target: Optional[Literal['current', 'backlog', 'none']] = None


class Catalog(BaseModel):
    model_config = _STRICT
    version: str
    commands: list[Command]
    taxonomy: list[CategoryMeta]

    def skills(self) -> list[Command]:
        return [c for c in self.commands if c.kind == 'skill']

    def tools(self) -> list[Command]:
        return [c for c in self.commands if c.kind == 'tool']

    def libs(self) -> list[Command]:
        return [c for c in self.commands if c.kind == 'lib']


def catalog_path(repo_root: Optional[Path] = None) -> Path:
    root = repo_root or find_repo_root(Path.cwd())
    if root is None:
        raise FileNotFoundError(
            'framework repo root not found (no forge/schemas/ in any parent of cwd).')
    return root / 'forge' / 'commands.catalog.yml'


def load_catalog(path: Optional[Path] = None) -> Catalog:
    """Read + validate the catalog into typed models. Raises on missing/invalid."""
    p = path or catalog_path()
    if not p.is_file():
        raise FileNotFoundError(f'catalog not found at {p}')
    with p.open(encoding='utf-8') as fh:
        data = yaml.safe_load(fh)
    return Catalog.model_validate(data)
