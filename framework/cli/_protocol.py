# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""The console protocol: exit-codes + the WorkRequest the baton emits at each stop.

LangGraph interrupts become console exit-codes so an autonomous agent (Claude Code)
can drive the framework with plain shell calls:
  - 0  done        : the graph reached END.
  - 10 work        : a cognitive node needs the agent to produce an artifact.
  - 20 human/gate  : a human-in-the-loop interrupt (e.g. human_review) or a
                     governance hard-limit — the agent must pause for the operator.
  - 1  error       : an unrecoverable CLI/state error.

At a 10/20 stop the baton prints a WorkRequest (JSON) to stdout describing what the
graph is waiting for; the agent fulfills it and resumes via run.py --resume.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

EXIT_DONE = 0
EXIT_ERROR = 1
EXIT_WORK = 10
EXIT_HUMAN = 20

# Nodes that represent a human decision gate (the graph's interrupt_before targets).
# Anything else the graph stops before is cognitive WORK for the agent. The set is
# the single place T2/T4 extend as cognitive interrupts are added.
HUMAN_NODES = {"human_review"}

# ---- Governance: the operator's hard-limits, mechanized (<TICKET-ID>) ----
# The canonical single-source list of operator-gated actions. A WorkRequest carrying
# a `gate` means: the agent does the phase prep, but the gated action requires EXPLICIT
# operator authorization before resuming (see operation-protocol.mdc). This codifies
# the operator's durable feedback rules so a fresh agent (no chat history) also pauses.
HARD_LIMITS = {"push", "jira-post", "auth-15", "scope-gap", "strategic-choice"}

# Lifecycle phases whose work crosses a hard-limit → the WorkRequest is flagged.
PHASE_GATES = {"enrich-us": "jira-post", "commit": "push"}


class WorkRequest(BaseModel):
    """What the baton hands the agent at a non-terminal stop."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["work", "human"]
    mode: Literal["lifecycle", "strategy"]
    thread_id: str
    node: str               # the node the graph is about to run (the ask)
    needs: list[str]        # fields/artifacts the agent should feed back
    context: dict           # serializable slice of state for the agent
    gate: Optional[str] = None  # a hard-limit (HARD_LIMITS) this phase crosses → operator stop

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


def classify_stop(next_nodes: tuple) -> str:
    """Classify a graph stop from its pending `next` tuple: done | human | work."""
    if not next_nodes:
        return "done"
    if any(n in HUMAN_NODES for n in next_nodes):
        return "human"
    return "work"


def exit_code_for(stop: str) -> int:
    return {"done": EXIT_DONE, "work": EXIT_WORK, "human": EXIT_HUMAN}[stop]
