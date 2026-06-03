# Architecture

How the framework works under the hood. This document is the engine room; the
[Commands Reference](COMMANDS_REFERENCE.md) is the operator's map, and the
[ADRs](forge/specs/adrs/) record *why* each decision was made.

> **Scope (v1): Lifecycle Internals.** This first revision documents the ticket
> lifecycle after the framework release layer "steel foundations" refactor. It is intentionally
> extensible — sections for the audit subsystem, the meta-audit, and the future
> LangGraph orchestrator will be added as those mature. It cites *symbol names*,
> never line numbers, so it does not rot as the code moves.

---

## Lifecycle Internals (v1)

The ticket lifecycle (`/enrich-us` → `/plan` → `/develop` → `/verify` →
`/commit` → `/update-docs`) is gated by a small set of Python support tools.
After framework release layer, each tool is split into a **pure importable library** (`_<tool>.py`)
plus a **thin CLI shell** (the hyphenated `<tool>.py`). Three invariants hold:

- **Disk is the single durable source of truth** — the per-ticket state lives in
  `.lifecycle/artifacts/<module>/state/<TICKET>.yml`.
- **Engine vs data (<TICKET-ID>)** — `forge/` is the ENGINE (tools, schemas,
  specs, `.playbooks`), distributable and product-agnostic. `.lifecycle/artifacts/`
  is the governed project's DATA (plans/records/verify/state), committed in that
  project's repo and excluded from the engine's distribution. The tools locate
  data via `_common.resolve_artifacts_root()` (env `AI_SPECS_ROOT` > nearest
  `.lifecycle/` marker > framework fallback) + `CHANGES_SUBPATH`, so the engine
  can write a project's trail into THAT project's own tree.
- **Cross-repo separation (<TICKET-ID>)** — the governed product's governance data
  (module trails + product specs + the product architecture map) lives in the PRODUCT
  repo at `<your-product>/.lifecycle/`, not here. This framework repo keeps only its
  engine + its own dogfood (`.lifecycle/artifacts/{framework,orchestrator,ci,backlog}`)
  + its wave changelog (`forge/specs/integration-state.md`). Operate the product's
  tickets with `AI_SPECS_ROOT=~/projects/<your-product>`.
- **`state.schema.yml` is the single source of truth for the *schema*** — the
  on-disk shape is authoritative; the in-memory model mirrors it.
- **RAM holds a transient typed mirror** — `LifecycleState` (Pydantic), never
  authoritative, rebuilt from disk on every read.

### 1. State flow — Disk ⇄ RAM ⇄ Disk

The state object travels through three stages.

**(a) Hydration (disk → RAM).** One read on entry:

```
state.yml (text)
  └─ load_state(path)                       → dict   (yaml.safe_load; raises StateParseError if corrupt)
       └─ LifecycleState.from_state_dict(d) → LifecycleState (Pydantic, in RAM)
```

`load_state_typed(path)` chains both. `from_state_dict` resolves the hyphenated
step keys (`enrich-us`, `update-docs`) and applies `extra="forbid"` — an unknown
field on disk fails hydration instead of being silently absorbed.

**(b) Transition (RAM → RAM, pure, no I/O).** The core is `_advance_dict` — a
pure function that marks the step `done`, sets the timestamp, merges the
validated fields, and advances the `state` enum. The typed API wraps it:

```
apply_advance(state: LifecycleState, command, fields, timestamp) -> LifecycleState
   1. d = state.to_state_dict()                       # model_dump(by_alias, exclude_none)
   2. validate fields against COMMAND_RULES.allowed_fields (raise ValueError otherwise)
   3. d = _advance_dict(d, command, fields, ts)        # the pure transition
   4. return LifecycleState.from_state_dict(d)         # a new typed state
```

No disk is touched. Multiple advances chain in RAM. `evaluate_prereq(state, command)`
decides gates equally purely, accepting either a model or a raw dict.

**(c) Checkpoint (RAM → disk), under a lock.** Writing is the only step that
touches disk, and it is serialized:

```
with _StateLock(path, mode="exclusive"):              # fcntl.flock — cross-process/agent mutual exclusion
    save_state(path, state.to_state_dict())           # yaml.safe_dump(sort_keys=False, width=100)
```

`save_state` is a pure write (it does **not** lock); the caller holds the lock
(this is how the CLI's `cmd_advance` works). The bootstrap (`/enrich-us`) creates
the file via template-fill (with comments); the first subsequent advance rewrites
it via `save_state` (clean YAML thereafter).

**Why disk stays immutable-as-truth:** every read re-hydrates from disk; every
write is schema-validated (the same `validate-artifact` runs over the file) and
`flock`-serialized. If a process dies with `LifecycleState` half-built in RAM, the
disk is unchanged — the write happens only at the checkpoint. RAM is a disposable
mirror, never authoritative.

See **ADR-001** (the state machine as a code-enforced gate) and **ADR-004**
(schema-driven validation).

### 2. Lib + CLI-shell anatomy (example: `state-machine`)

Two files, one sharp boundary:

```
state-machine.py        (hyphen)      →  CLI SHELL   (~22 lines)
_state_machine.py       (underscore)  →  LIBRARY     (all logic, importable)
```

**The shell** receives console arguments and delegates — nothing else:

```python
# state-machine.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _state_machine import run_cli
if __name__ == "__main__":
    sys.exit(run_cli(sys.argv[1:]))
```

The invocation path (`python3 forge/tools/state-machine.py …`) is unchanged —
every skill still calls it the same way. The hyphen in the filename blocks
`import` (`import state-machine` is a `SyntaxError`), which is exactly why the
logic lives in the underscore sibling `_state_machine.py` (the `_common.py`
convention). This is **ADR-006** (`forge/tools/` is not a package).

**The library** separates *pure logic* from *I/O*:

| In `_state_machine.py` | Kind | Touches disk/process |
|---|---|---|
| `COMMAND_RULES`, predicates | data / pure logic | no |
| `_advance_dict`, `evaluate_prereq`, `apply_advance` | **pure logic `(state)->state`** | **no** |
| `load_state` (raises `StateParseError`) | I/O read | reads disk |
| `_StateLock` (`fcntl.flock`; raises `LockTimeout`) | **I/O — the lock** | yes (flock) |
| `save_state` | I/O write | writes disk |
| `run_cli(argv) -> int` | CLI glue (argparse + dispatch) | orchestrates |

- **The `flock` lives in `_StateLock`, inside the library.** `cmd_advance` wraps
  read + mutate + write in `with _StateLock(path, mode="exclusive")`; `cmd_check`
  and `cmd_state` use `mode="shared"`. The lock is the I/O boundary, not logic.
- **The pure logic lives in `_advance_dict` and `evaluate_prereq`** — no I/O, no
  `sys.exit`, no `print`. This is what the orchestrator imports.
- **Exit contract:** `run_cli` returns an `int` (0/1/2). Library exceptions map
  there — `StateParseError → 2`, `LockTimeout → 75` (rule LCK-001). The library
  *raises*; the shell *exits*. An importer (the orchestrator) is never killed by
  a stray `sys.exit`.

All four support tools follow this pattern — and all four are now pure return-int
with a single `_StateLock`-guarded writer: `_validate_artifact.py` exposes
`validate_typed() -> ValidationResult`; `_init_state.py`; `_classify_deviation.py`
exposes `classify_typed() -> Deviation` and (since <TICKET-ID>) returns an int from
`run_cli`, appending to `state.yml` under the shared `_StateLock` — no second
unsynchronized writer. See **ADR-006**.

### 3. The anti-drift shield

`_lifecycle_state.py` (`LifecycleState`) is a Pydantic **mirror** of
`state.schema.yml`. Two sources of truth risk drifting; the defence is that the
**schema is authoritative** and a *test-judge* verifies the mirror against it on
every pytest/CI run. In `test_lifecycle_state.py`:

```
test_lifecycle_state_round_trips_through_schema
    build a representative LifecycleState
      → .to_state_dict()  →  YAML
      → validate-artifact <yaml> --schema state.schema.yml
      → assert PASS
```

It runs the *model's output* through the *same validator that runs over disk*. If
the model adds, renames, or mistypes a field relative to the schema,
`validate-artifact` fails → the test goes red. Two companions catch enum and
step-key drift directly (`test_state_enum_matches_schema`,
`test_step_keys_match_schema`).

The mechanism in one line: the on-disk schema is the single source of truth, and
the in-memory model is *verified against it by a test that turns red on any
divergence* — chosen over code-generation to avoid a build step. See **ADR-004**
and **ADR-009** (Pydantic for the typed model).

### 4. LangGraph orchestrator mockup (the immediate future)

The future orchestrator imports these pure functions and `LifecycleState`
directly — no subprocesses, no console parsing:

```python
# orchestrator/lifecycle_graph.py  (future — conceptual)
import sys; sys.path.insert(0, "forge/tools")
from _lifecycle_state import LifecycleState
from _state_machine import (
    load_state_typed, apply_advance, evaluate_prereq, save_state, state_path, _StateLock,
)
from _validate_artifact import validate_typed, ValidationResult

# A LangGraph node = (State) -> State, where State = LifecycleState (typed, in RAM).
def verify_node(state: LifecycleState) -> LifecycleState:
    if not evaluate_prereq(state, "verify"):          # typed decision, not a parsed exit code
        raise PrereqNotMet("verify")                  # → a conditional graph edge
    result: ValidationResult = validate_typed(verify_path)   # typed, in-process (no subprocess)
    if result.verdict != "PASS":
        return route_to_fix(state, result)            # route on the object, not on stdout
    return apply_advance(state, "verify", {           # PURE in-RAM transition; disk untouched
        "verdict": result.verdict, "path": str(verify_path), "schema_validated": True,
    })

# Graph driver
path = state_path(find_framework_root(), module, ticket)
state = load_state_typed(path)            # the ONLY disk read (graph entry)
state = plan_node(state)                  # RAM (sub-millisecond)
state = develop_node(state)               # RAM
state = verify_node(state)                # RAM
with _StateLock(path, mode="exclusive"):  # the ONLY disk write, flock-serialized
    save_state(path, state.to_state_dict())   # durable checkpoint
```

In production, `LifecycleState` becomes the `StateGraph` state schema and
`save_state` the checkpointer. The contrast with the pre-Wave-1 model: previously
every step spawned a subprocess (~100 ms cold-start), read/wrote `state.yml`, and
parsed `stdout`/exit codes; now transitions are in-RAM calls (sub-ms) on a typed
object, and disk is touched only at entry (one read) and checkpoints (locked
writes). The orchestrator's self-correction loop lives in RAM; disk keeps the
durable truth at boundaries.

---

## References

- [ADR-001](forge/specs/adrs/adr-001-fw-004-state-machine.md) — the state machine as a code-enforced gate.
- [ADR-004](forge/specs/adrs/adr-004-schema-driven-validation.md) — schema-driven validation.
- [ADR-006](forge/specs/adrs/adr-006-ai-specs-tools-not-a-package.md) — `forge/tools/` is not a package (the lib + CLI-shell pattern).
- [ADR-009](forge/specs/adrs/adr-009-pydantic-for-meta-audit.md) — Pydantic as a runtime dependency (the typed model).
- [Commands Reference](COMMANDS_REFERENCE.md) — skills vs tools, and how to invoke them.
