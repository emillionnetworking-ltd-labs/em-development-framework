# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""GraphState — the LangGraph state schema for the lifecycle orchestrator (<TICKET-ID>).

The state that travels between nodes = the DURABLE LifecycleState (mirror of
state.yml, the single source of truth) + TRANSIENT routing fields that nodes
produce and conditional edges consume but that are never persisted to state.yml.

Disk ⇄ RAM ⇄ Disk:
  state.yml --load_state_typed--> LifecycleState --apply_advance--> (RAM, pure)
            --StateYamlCheckpointer.put (save_state under _StateLock)--> state.yml
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._deps import LifecycleState, Deviation, ValidationResult, load_state_typed, state_path, repo_root


class GraphState(BaseModel):
    """LangGraph state schema. `lifecycle` is durable; the rest is transient."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- DURABLE core: mirror of state.yml ---
    lifecycle: LifecycleState
    repo_root: str
    module: str

    # <TICKET-ID> framework release layer (Pilar 1.2 runtime injection):
    # workspace context loaded mechanically from forge.config.yml at session
    # build time. Exposed in each WorkRequest payload (context dict) so the
    # agent reading the WorkRequest receives workspace symbolically without
    # needing to read the YAML file textually. Optional + default None for
    # backward-compat with existing checkpoints (W25-29).
    workspace: Optional[dict] = None

    # --- TRANSIENT: produced by nodes, read by edges, never persisted ---
    last_validation: Optional[ValidationResult] = None
    last_verdict: Optional[str] = None
    # raw deviation inputs (answers + description) emitted by verify, consumed by classify
    pending_deviation_inputs: list[dict] = Field(default_factory=list)
    # classified results (typed) produced by the classify node
    pending_deviations: list[Deviation] = Field(default_factory=list)
    error: Optional[str] = None
    retries: int = 0

    # ---- helpers ----

    @classmethod
    def from_disk(cls, module: str, ticket: str, root: Optional[str] = None) -> "GraphState":
        """Hydrate from the canonical state.yml (the one graph-entry disk read)."""
        root_path = root or str(repo_root())
        sp = state_path(Path(root_path), module, ticket)
        lifecycle = load_state_typed(sp)
        if lifecycle is None:
            raise FileNotFoundError(f"no state file for {ticket} in module {module} ({sp})")
        return cls(lifecycle=lifecycle, repo_root=root_path, module=module)

    def state_file_path(self):
        return state_path(Path(self.repo_root), self.module, self.lifecycle.ticket)
