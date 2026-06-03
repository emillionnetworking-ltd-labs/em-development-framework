# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""StrategyTools — the work seam for the strategist nodes (framework release layer, <TICKET-ID>).

The four cyclic nodes (archaeologist / consultant / synthesizer / critic) + the
human-review node do their actual WORK through this protocol: reading local code +
debt, researching the market (web), synthesizing competing proposals, critiquing
them (the anti-patch filter), and rendering the executive report. The LLM / web /
filesystem live behind this interface, so the graph is unit-testable with a stub.
The real implementation (an LLM/agent with web access + repo reads) is wired later.
"""

from typing import Protocol

from .strategy_state import StrategyState, Proposal, Critique


class StrategyTools(Protocol):
    def read_local(self, target: str, debt: str) -> str:
        """Archaeologist: examine the current local code + the technical debt on disk."""
        ...

    def research(self, queries: list[str]) -> str:
        """Consultant: pull industry best-practices + up-to-date benchmarks from the web."""
        ...

    def synthesize(self, local: str, market: str, criteria: list[str]) -> list[Proposal]:
        """Synthesizer: cross the local + market findings into competing proposals."""
        ...

    def critique(self, proposals: list[Proposal], criteria: list[str]) -> Critique:
        """Ruthless Critic (anti-patch): veto weak / coupled / insecure plays; force a refine."""
        ...

    def render_report(self, state: StrategyState) -> str:
        """Human-review: render the structured executive report frozen at the interrupt."""
        ...
