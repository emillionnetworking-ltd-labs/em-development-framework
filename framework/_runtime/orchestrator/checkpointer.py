# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""StateYamlCheckpointer — the hybrid LangGraph checkpointer (<TICKET-ID>).

Two persistence layers, ONE locked writer:

  1. CANONICAL state.yml — on every `put`, the durable LifecycleState carried in
     the graph state is written to the native `state.yml` path under `_StateLock`,
     so the lifecycle CLI (`state-machine.py`) and the Streamlit dashboard keep
     reading the canonical file. Nothing about the existing surface breaks.

  2. SNAPSHOT history — the FULL LangGraph checkpoint is serialized (via the
     graph's serde) to `orchestrator/.checkpoints/<thread_id>/<seq>-<id>.json`,
     enabling LangGraph's native resume + step-level time-travel / audit.

The two writes happen together, inside the same exclusive lock acquisition.
"""

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ._deps import (
    LifecycleState, save_state, state_path, _StateLock, repo_root,
)

CHECKPOINTS_DIR = Path(__file__).resolve().parent / ".checkpoints"

# The lifecycle types carried in the graph channels. Registering them with the
# serde's msgpack allowlist silences LangGraph's "Deserializing unregistered type"
# warning on checkpoint round-trips (surfaced once the graph checkpoints mid-flight,
# e.g. at a dynamic interrupt). Same forward-safe pattern as strategy_serde (<TICKET-ID>).
LIFECYCLE_MSGPACK_MODULES = [
    # Post W64 SCRUM-632: module paths now under framework._runtime.*
    ("framework._runtime.orchestrator.graph_state", "GraphState"),
    ("framework._runtime.state._lifecycle_state", "LifecycleState"),
    ("framework._runtime.state._lifecycle_state", "Deviation"),
    ("framework._runtime.state._validate_artifact", "ValidationResult"),
]


def lifecycle_serde() -> JsonPlusSerializer:
    """The serde for lifecycle checkpoints — explicitly allows the lifecycle types."""
    return JsonPlusSerializer(allowed_msgpack_modules=LIFECYCLE_MSGPACK_MODULES)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _atomic_write(path: Path, text: str) -> None:
    """Write via temp + rename so a reader never sees a half-written file. The temp
    name is UNIQUE per call (uuid) because LangGraph's executor drives put_writes
    concurrently on the SAME target file — a shared temp name races on os.replace
    (one thread consumes the temp the other is about to rename) → FileNotFoundError."""
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_snap(f: Path) -> Optional[dict]:
    """Tolerant read: skip an empty / mid-write / invalid snapshot file."""
    try:
        txt = f.read_text(encoding="utf-8")
        return json.loads(txt) if txt.strip() else None
    except (json.JSONDecodeError, OSError):
        return None


class StateYamlCheckpointer(BaseCheckpointSaver):
    """Hybrid saver: canonical state.yml (locked) + chronological snapshot history."""

    def __init__(self, *, checkpoints_dir: Optional[Path] = None, root: Optional[str] = None,
                 serde=None) -> None:
        super().__init__(serde=serde or lifecycle_serde())
        self.checkpoints_dir = Path(checkpoints_dir) if checkpoints_dir else CHECKPOINTS_DIR
        self.root = root or str(repo_root())

    # ---- storage helpers ----

    def _thread_dir(self, thread_id: str) -> Path:
        d = self.checkpoints_dir / thread_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _snapshots(self, thread_id: str) -> list[Path]:
        d = self.checkpoints_dir / thread_id
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob("*.json") if not p.name.endswith(".tmp"))  # seq-prefixed → chronological

    @staticmethod
    def _thread_id(config: dict) -> str:
        return config["configurable"]["thread_id"]

    # ---- the hybrid canonical write ----

    def _write_canonical_state(self, checkpoint: Checkpoint) -> None:
        """Extract the LifecycleState from the checkpoint's channels and write the
        canonical state.yml under _StateLock. Tolerant: a no-op if absent."""
        cv = checkpoint.get("channel_values") or {}
        lc = cv.get("lifecycle")
        module = cv.get("module")
        if lc is None or not module:
            return  # generic checkpoint (no lifecycle channel) → snapshot only
        if isinstance(lc, LifecycleState):
            state_dict = lc.to_state_dict()
            ticket = lc.ticket
        elif isinstance(lc, dict):
            state_dict = LifecycleState.from_state_dict(lc).to_state_dict()
            ticket = state_dict["ticket"]
        else:
            return
        sp = state_path(Path(self.root), module, ticket)
        with _StateLock(sp, mode="exclusive"):
            save_state(sp, state_dict)

    # ---- BaseCheckpointSaver interface (sync) ----

    def put(self, config: dict, checkpoint: Checkpoint, metadata: CheckpointMetadata,
            new_versions) -> dict:
        thread_id = self._thread_id(config)
        cp_id = checkpoint["id"]
        d = self._thread_dir(thread_id)
        seq = len(self._snapshots(thread_id))
        parent_id = config.get("configurable", {}).get("checkpoint_id")

        cp_type, cp_bytes = self.serde.dumps_typed(checkpoint)
        md_type, md_bytes = self.serde.dumps_typed(metadata)
        snapshot = {
            "thread_id": thread_id,
            "checkpoint_id": cp_id,
            "seq": seq,
            "ts": checkpoint.get("ts"),
            "parent_checkpoint_id": parent_id,
            "checkpoint": {"type": cp_type, "b64": _b64(cp_bytes)},
            "metadata": {"type": md_type, "b64": _b64(md_bytes)},
            "writes": [],
        }
        _atomic_write(d / f"{seq:06d}-{cp_id}.json", json.dumps(snapshot))

        # HYBRID: keep the canonical state.yml authoritative for CLI + dashboard.
        self._write_canonical_state(checkpoint)

        return {"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id}}

    def put_writes(self, config: dict, writes: Sequence[tuple[str, Any]], task_id: str,
                   task_path: str = "") -> None:
        thread_id = self._thread_id(config)
        cp_id = config["configurable"]["checkpoint_id"]
        for f in self._snapshots(thread_id):
            snap = _read_snap(f)
            if snap and snap["checkpoint_id"] == cp_id:
                for channel, value in writes:
                    vt, vb = self.serde.dumps_typed(value)
                    snap["writes"].append({"task_id": task_id, "task_path": task_path,
                                           "channel": channel,
                                           "value": {"type": vt, "b64": _b64(vb)}})
                _atomic_write(f, json.dumps(snap))
                return

    def _load_tuple(self, snap: dict) -> CheckpointTuple:
        checkpoint = self.serde.loads_typed((snap["checkpoint"]["type"], _unb64(snap["checkpoint"]["b64"])))
        metadata = self.serde.loads_typed((snap["metadata"]["type"], _unb64(snap["metadata"]["b64"])))
        config = {"configurable": {"thread_id": snap["thread_id"], "checkpoint_id": snap["checkpoint_id"]}}
        parent_config = None
        if snap.get("parent_checkpoint_id"):
            parent_config = {"configurable": {"thread_id": snap["thread_id"],
                                              "checkpoint_id": snap["parent_checkpoint_id"]}}
        pending = [(w["task_id"], w["channel"],
                    self.serde.loads_typed((w["value"]["type"], _unb64(w["value"]["b64"]))))
                   for w in snap.get("writes", [])]
        return CheckpointTuple(config, checkpoint, metadata, parent_config, pending)

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        thread_id = self._thread_id(config)
        snaps = self._snapshots(thread_id)
        if not snaps:
            return None
        wanted = config.get("configurable", {}).get("checkpoint_id")
        if wanted:
            for f in snaps:
                snap = _read_snap(f)
                if snap and snap["checkpoint_id"] == wanted:
                    return self._load_tuple(snap)
            return None
        for f in reversed(snaps):  # latest valid
            snap = _read_snap(f)
            if snap:
                return self._load_tuple(snap)
        return None

    def list(self, config: Optional[dict], *, filter: Optional[dict] = None,
             before: Optional[dict] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        if config is None:
            return
        thread_id = self._thread_id(config)
        before_id = (before or {}).get("configurable", {}).get("checkpoint_id")
        seen_before = before_id is None
        count = 0
        for f in reversed(self._snapshots(thread_id)):  # newest first
            snap = _read_snap(f)
            if snap is None:
                continue
            if not seen_before:
                if snap["checkpoint_id"] == before_id:
                    seen_before = True
                continue
            yield self._load_tuple(snap)
            count += 1
            if limit and count >= limit:
                return
