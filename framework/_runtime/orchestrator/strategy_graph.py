# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""The compiled strategy StateGraph (framework release layer, <TICKET-ID> — loop closure).

Wires the 5 cyclic nodes (<TICKET-ID>) + the pure routing edges (<TICKET-ID>) into a
LangGraph StateGraph over StrategyState, compiled with the disk-backed
StrategySnapshotSaver (debate sessions) and a MANDATORY human interrupt before
human_review. The graph owns routing + checkpointing; mutation stays in the nodes.

    START → archaeologist → consultant → synthesizer → critic ─┬─(STRONG | budget out)→ human_review ─┬─(approve|abort)→ END
                                              ▲                 └─(WEAK/COMPLACENT/INSECURE & budget)→ ┘  └─(refine)→ synthesizer
                                              └──────────────────────────────────────────────────────────────────────┘

`interrupt_before=["human_review"]` halts the run before the human verdict so the
operator can inspect the snapshot and resume with a decision (approve/refine/abort).
"""

from langgraph.graph import StateGraph, START, END

from .strategy_state import StrategyState
from .strategy_nodes import build_strategy_nodes
from .strategy_edges import route_after_critique, route_after_human
from .strategy_checkpointer import StrategySnapshotSaver


def build_strategy_graph(tools, checkpointer=None):
    """Build + compile the strategy StateGraph bound to a StrategyTools impl.

    Defaults to the disk-backed StrategySnapshotSaver (debate sessions under
    .strategy-sessions/, never the lifecycle's state.yml). Compiled with the
    mandatory human interrupt before human_review.
    """
    nodes = build_strategy_nodes(tools)
    g = StateGraph(StrategyState)
    for name, fn in nodes.items():
        g.add_node(name, fn)

    g.add_edge(START, "archaeologist")
    g.add_edge("archaeologist", "consultant")
    g.add_edge("consultant", "synthesizer")
    g.add_edge("synthesizer", "critic")
    g.add_conditional_edges("critic", route_after_critique,
                            {"synthesizer": "synthesizer", "human_review": "human_review"})
    g.add_conditional_edges("human_review", route_after_human,
                            {"synthesizer": "synthesizer", END: END})

    return g.compile(checkpointer=checkpointer or StrategySnapshotSaver(),
                     interrupt_before=["human_review"])
