# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""StrategySnapshotSaver — a lightweight checkpointer for the strategist graph
(framework release layer, <TICKET-ID>).

Unlike the lifecycle's StateYamlCheckpointer (which writes the canonical state.yml),
the strategist is PRE-TICKET: it must NOT touch the lifecycle's operational state.
This saver persists the debate sessions purely as atomic JSON snapshots under
orchestrator/.strategy-sessions/<thread>/<seq>-<id>.json, enabling LangGraph's
interrupt/resume (the human-in-the-loop freeze) and audit time-travel of the
self-refine iterations.

(It mirrors the snapshot mechanics of StateYamlCheckpointer minus the canonical
write; a shared _SnapshotSaver base is a LOW follow-up.)
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

# W68 SCRUM-636: __file__-relative fallback REMOVED. Constructor REQUIRES
# sessions_dir to be passed.

# The strategist's own Pydantic models. Registering them with the serde's msgpack
# allowlist silences LangGraph's "Deserializing unregistered type" warning on
# snapshot round-trips (and is forward-safe once strict-msgpack becomes the default).
STRATEGY_MSGPACK_MODULES = [
    # Post W64 SCRUM-632: module paths now under framework._runtime.*
    ("framework._runtime.orchestrator.strategy_state", "StrategyState"),
    ("framework._runtime.orchestrator.strategy_state", "Proposal"),
    ("framework._runtime.orchestrator.strategy_state", "Critique"),
]


def strategy_serde() -> JsonPlusSerializer:
    """The serde for strategist snapshots — explicitly allows Proposal/Critique."""
    return JsonPlusSerializer(allowed_msgpack_modules=STRATEGY_MSGPACK_MODULES)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _atomic_write(path: Path, text: str) -> None:
    # UNIQUE temp name per call: LangGraph's executor drives put_writes concurrently
    # on the same target, and a shared temp name races on os.replace.
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_snap(f: Path) -> Optional[dict]:
    try:
        txt = f.read_text(encoding="utf-8")
        return json.loads(txt) if txt.strip() else None
    except (json.JSONDecodeError, OSError):
        return None


class StrategySnapshotSaver(BaseCheckpointSaver):
    """Snapshot-only saver for strategist debate sessions. Never writes state.yml."""

    def __init__(self, *, sessions_dir: Optional[Path] = None, serde=None) -> None:
        super().__init__(serde=serde or strategy_serde())
        if sessions_dir is None:
            raise TypeError(
                "sessions_dir is required (W68 SCRUM-636: __file__-relative "
                "default removed). Use framework.cli._session.build_strategy_session "
                "which derives it from Framework.output_dir, or pass an explicit Path."
            )
        self.sessions_dir = Path(sessions_dir)

    # ---- storage helpers ----

    def _thread_dir(self, thread_id: str) -> Path:
        d = self.sessions_dir / thread_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _snapshots(self, thread_id: str) -> list[Path]:
        d = self.sessions_dir / thread_id
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob("*.json") if not p.name.endswith(".tmp"))

    @staticmethod
    def _thread_id(config: dict) -> str:
        return config["configurable"]["thread_id"]

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
            "thread_id": thread_id, "checkpoint_id": cp_id, "seq": seq,
            "ts": checkpoint.get("ts"), "parent_checkpoint_id": parent_id,
            "checkpoint": {"type": cp_type, "b64": _b64(cp_bytes)},
            "metadata": {"type": md_type, "b64": _b64(md_bytes)},
            "writes": [],
        }
        _atomic_write(d / f"{seq:06d}-{cp_id}.json", json.dumps(snapshot))
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
                                           "channel": channel, "value": {"type": vt, "b64": _b64(vb)}})
                _atomic_write(f, json.dumps(snap))
                return

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
        for f in reversed(snaps):
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
        for f in reversed(self._snapshots(thread_id)):
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
