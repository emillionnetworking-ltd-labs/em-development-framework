# Orchestrator

The framework's **lifecycle orchestrator** — a LangGraph `StateGraph` over the
typed lifecycle libs in `ai-specs/tools/`. framework release layer.

> **Architecture boundary.** `ai-specs/` is specs + metadata (no app code).
> `orchestrator/` is application code, with its own isolated `requirements.txt`
> (`langgraph`). The dependency is **one-way**: `orchestrator` imports the
> read-only typed libs from `ai-specs/tools/`; `ai-specs` never imports
> `orchestrator`. Same pattern as `control-plane/`.

## What's here (<TICKET-ID> — Foundation)

| File | Role |
|---|---|
| `graph_state.py` | `GraphState` — the LangGraph state schema: durable `LifecycleState` (mirror of `state.yml`) + transient routing fields (validation, verdict, pending deviations, error, retries). |
| `checkpointer.py` | `StateYamlCheckpointer` — the **hybrid** `BaseCheckpointSaver`. |
| `_deps.py` | one-way `sys.path` bootstrap to `ai-specs/tools`. |

| `nodes.py` | The 7 lifecycle nodes (enrich_us/plan/develop/verify/classify/commit/update_docs) over a `WorkLayer`. |
| `edges.py` | Pure conditional-edge routers (`route_after_verify`/`route_after_classify`) + the bounded self-correction loop (`MAX_RETRIES`). |
| `lifecycle_graph.py` | `build_graph(work, checkpointer)` — the compiled `StateGraph` wiring all nodes/edges + the hybrid checkpointer. |

## Running the graph (with a work layer)

```python
from lifecycle_graph import build_graph
from checkpointer import StateYamlCheckpointer

app = build_graph(my_work_layer, StateYamlCheckpointer())
final = app.invoke(initial_graph_state, {"configurable": {"thread_id": "<TICKET-ID>"}})
```

`build_graph` drives `START → enrich_us → plan → develop → verify → (commit | develop | classify) → … → update_docs → END`, checkpointing the durable `LifecycleState` to the canonical `state.yml` (+ snapshot history) at each super-step. The end-to-end smoke (`tests/test_graph_e2e.py`) proves it with a stub work layer; a real LLM/agent `WorkLayer` is a later program.

## The hybrid checkpointer

On every `put`, inside ONE exclusive `_StateLock` acquisition:

1. **Canonical `state.yml`** — the durable `LifecycleState` carried in the graph
   state is written to the native `state.yml` path via `save_state`, so the
   lifecycle CLI (`state-machine.py`) and the Streamlit dashboard keep reading
   the canonical file unchanged.
2. **Snapshot history** — the full LangGraph checkpoint is serialized (via the
   graph serde) to `orchestrator/.checkpoints/<thread_id>/<seq>-<id>.json`,
   enabling LangGraph's native **resume** and step-level **time-travel / audit**.

`thread_id` carries the ticket; `module` + `repo_root` ride in the graph state so
the checkpointer can resolve the canonical `state_path`.

## Install / test

```bash
pip install -r orchestrator/requirements.txt
pytest orchestrator/tests
```

Runs in its own scope (needs `langgraph`, intentionally NOT an ai-specs dep);
`pytest.ini` does not collect this dir, so the ai-specs suite is unaffected.
