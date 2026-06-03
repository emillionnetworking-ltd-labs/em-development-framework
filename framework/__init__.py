# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""framework/ — the unified entrypoint app dir (framework release layer, El Despertar de la Maquinaria).

The 4th sibling app dir (after ai-specs/, control-plane/, orchestrator/). It holds
the CLI 'baton' that drives the compiled LangGraph brains (lifecycle + strategy)
and translates their interrupts into console exit-codes for an autonomous agent.
One-way read-only dependency on orchestrator/ + ai-specs/tools; nothing upstream
imports framework/.
"""
