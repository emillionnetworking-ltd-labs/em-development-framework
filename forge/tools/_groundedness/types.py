# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""Shared types for the groundedness validation package (<TICKET-ID>)."""

from dataclasses import dataclass
from typing import Literal, Optional

Severity = Literal["WARN", "FAIL"]
RuleId = Literal["GRD-001", "GRD-002a", "GRD-002b", "GRD-003"]


@dataclass(frozen=True)
class Violation:
    rule_id: RuleId
    severity: Severity
    file: str
    line: Optional[int]
    ref: str
    message: str
