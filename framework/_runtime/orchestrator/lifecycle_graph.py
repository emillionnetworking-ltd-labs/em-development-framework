# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""The compiled lifecycle StateGraph (framework release layer, <TICKET-ID> — loop closure).

Wires all seven nodes + the conditional edges (with the bounded self-correction
loop) into a LangGraph StateGraph over GraphState, compiled with the hybrid
StateYamlCheckpointer. The graph owns routing (via the pure edge functions on the
structured verdict + evaluate_prereq); each super-step checkpoints the durable
LifecycleState to the canonical state.yml + the snapshot history.

    enrich_us → plan → develop → verify ─┬─(PASS)→ commit → update_docs → END
                          ▲              ├─(BLOCKED-GAP/BUILD)→ develop   (bounded)
                          └──────────────┤
                                         ├─(BLOCKED-RISK)→ classify ─┬→ (commit|develop|END)
                                         └─(error)→ END
"""

from langgraph.graph import StateGraph, START, END

from .graph_state import GraphState
from .nodes import build_nodes
from .edges import route_after_verify, route_after_classify
from .checkpointer import StateYamlCheckpointer


def build_graph(work, checkpointer=None):
    """Build + compile the lifecycle StateGraph bound to a WorkLayer."""
    nodes = build_nodes(work)
    g = StateGraph(GraphState)
    for name, fn in nodes.items():
        g.add_node(name, fn)

    g.add_edge(START, "enrich_us")
    g.add_edge("enrich_us", "plan")
    g.add_edge("plan", "develop")
    g.add_edge("develop", "verify")
    g.add_conditional_edges("verify", route_after_verify,
                            {"commit": "commit", "develop": "develop",
                             "classify": "classify", "halt": END})
    g.add_conditional_edges("classify", route_after_classify,
                            {"commit": "commit", "develop": "develop", "halt": END})
    g.add_edge("commit", "update_docs")
    g.add_edge("update_docs", END)

    return g.compile(checkpointer=checkpointer or StateYamlCheckpointer())
