# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""_sprint_cleanup.py — pure logic for /sprint-cleanup.

<TICKET-ID> (framework release layer). Closes the loop of the pending-improvements register:
classify-deviation OPENS debts; audit-coupling-check VIGILA; check-pending
REPORTS waiting; sprint-cleanup CLOSES with evidence trail.

Three sources evaluated per entry (always all three — diagnostic visibility):
  A1 trigger-state         — re-evaluates trigger.check; DIAGNOSTIC ONLY.
                             The existing triggers in pending-improvements.yml
                             are ELIGIBILITY signals (rc=0 → 'work is ready'),
                             NOT closure signals. Reporting A1 helps the
                             operator see if the trigger condition changed,
                             but it never auto-promotes an entry to candidate.
  A2 jira-ticket-done      — entry.jira_ticket has status=Done in Jira → CANDIDATE
  A3 operator-approved     — note prose contains 'resolved in <sprint>'  → CANDIDATE

is_candidate(eval) := A2.done OR A3.marked.
winning_source(eval) := priority A2 > A3 (verifiable evidence over self-report).

Approval is operator-typed per entry. Tool NEVER writes to Jira.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable, Literal, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pending_improvements import (  # noqa: E402
    PendingImprovementEntry, ResolutionEvidence, EvidenceSourceLiteral,
)


# ----- evidence types -----


class EvidenceSource(Enum):
    # Note: AUTO_TRIGGER_FAILED removed in <TICKET-ID> design review. The existing
    # triggers in pending-improvements.yml signal eligibility ('ready to work'),
    # not closure ('work is done'). A1 stays in SourceEvaluation as diagnostic
    # but never wins is_candidate.
    JIRA_TICKET_DONE = "jira-ticket-done"
    OPERATOR_APPROVED = "operator-approved"


@dataclass
class A1Eval:
    state: Literal["fired", "still-pending", "n-a-manual", "n-a-no-check", "error"]
    detail: str = ""


@dataclass
class A2Eval:
    state: Literal["done", "open", "skipped-no-creds", "skipped-no-ticket",
                   "skipped-by-flag", "error"]
    detail: str = ""


@dataclass
class A3Eval:
    state: Literal["marked", "unmarked"]
    detail: str = ""


@dataclass
class SourceEvaluation:
    """One per entry; carries the 3 source verdicts. ALL THREE always populated
    (even if A1 wins) so the report can show diagnostic visibility per entry."""
    entry_id: str
    a1: A1Eval
    a2: A2Eval
    a3: A3Eval

    @property
    def is_candidate(self) -> bool:
        # A1 is diagnostic only; closure requires verifiable evidence (A2) or
        # explicit operator intent (A3).
        return self.a2.state == "done" or self.a3.state == "marked"

    @property
    def winning_source(self) -> Optional[EvidenceSource]:
        if self.a2.state == "done":
            return EvidenceSource.JIRA_TICKET_DONE
        if self.a3.state == "marked":
            return EvidenceSource.OPERATOR_APPROVED
        return None


# ----- Jira credentials -----


class JiraCredsMissing(Exception):
    """Raised when --jira-creds was requested but env vars are absent."""


def resolve_jira_credentials(force: bool, skip_by_flag: bool) -> Optional[dict]:
    """Return creds dict if available; None if intentionally skipped.

    - skip_by_flag=True → return None (--no-jira; silent)
    - force=True and any var missing → raise JiraCredsMissing (--jira-creds)
    - default → WARN to stderr loudly, then return None
    """
    if skip_by_flag:
        return None

    required = ["JIRA_EMAIL", "JIRA_TOKEN", "JIRA_BASE_URL"]
    present = {k: os.environ.get(k) for k in required}
    missing = [k for k, v in present.items() if not v]

    if missing:
        if force:
            raise JiraCredsMissing(
                f"--jira-creds set but missing env: {', '.join(missing)}. "
                f"Source ~/.atlassian-credentials or pass --no-jira."
            )
        # Default: noisy warn — operator must SEE why A2 is skipped.
        print(
            f"WARN: A2 (jira-ticket-done) source SKIPPED — env not set: "
            f"{', '.join(missing)}. Affected entries flagged in report. "
            f"To force A2, use --jira-creds (exits 2 if still absent). "
            f"To silence this warning, use --no-jira.",
            file=sys.stderr,
        )
        return None

    return present


def make_jira_query(creds: Optional[dict]) -> Optional[Callable[[str], Optional[str]]]:
    """Return a query(ticket_id)->status_name callable, or None if no creds.
    The callable returns None on lookup failure (network, 404, etc.).
    """
    if creds is None:
        return None

    import urllib.request
    import urllib.error
    import base64
    import json

    base = creds["JIRA_BASE_URL"].rstrip("/")
    auth_raw = f"{creds['JIRA_EMAIL']}:{creds['JIRA_TOKEN']}".encode()
    auth_header = "Basic " + base64.b64encode(auth_raw).decode()

    def query(ticket: str) -> Optional[str]:
        url = f"{base}/rest/api/3/issue/{ticket}?fields=status"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Authorization": auth_header,
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            return data.get("fields", {}).get("status", {}).get("name")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return None

    return query


# ----- evaluation -----


def _run_trigger_check(check_cmd: str, timeout: int, cwd: Path) -> tuple[int, str]:
    """Returns (rc, summary). rc==0 means trigger STILL fires; rc!=0 means it
    no longer fires → A1 evidence."""
    try:
        r = subprocess.run(
            check_cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(cwd),
        )
        return r.returncode, f"rc={r.returncode}"
    except subprocess.TimeoutExpired:
        return -1, f"timeout after {timeout}s"
    except Exception as e:
        return -1, f"error: {e}"


def evaluate_entry(
    entry: PendingImprovementEntry,
    framework_root: Path,
    jira_query: Optional[Callable[[str], Optional[str]]],
    has_jira_creds: bool,
    skip_jira_by_flag: bool,
) -> SourceEvaluation:
    """Run all 3 evidence sources independently. Never short-circuits."""

    # A1: auto-trigger re-eval
    if entry.trigger.type == "manual":
        a1 = A1Eval(state="n-a-manual", detail="trigger.type=manual")
    elif not entry.trigger.check:
        a1 = A1Eval(state="n-a-no-check", detail="trigger.check is empty")
    else:
        timeout = entry.trigger.timeout_seconds or 10
        rc, summary = _run_trigger_check(entry.trigger.check, timeout, framework_root)
        if rc < 0:
            a1 = A1Eval(state="error", detail=summary)
        elif rc != 0:
            a1 = A1Eval(state="fired", detail=f"re-eval {summary} (no longer firing)")
        else:
            a1 = A1Eval(state="still-pending", detail=f"re-eval {summary} (still fires)")

    # A2: jira ticket status
    if skip_jira_by_flag:
        a2 = A2Eval(state="skipped-by-flag", detail="--no-jira")
    elif not entry.jira_ticket:
        a2 = A2Eval(state="skipped-no-ticket", detail="entry.jira_ticket unset")
    elif jira_query is None:
        a2 = A2Eval(state="skipped-no-creds",
                    detail=f"{entry.jira_ticket} → [SKIPPED — MISSING CREDS]")
    else:
        status = jira_query(entry.jira_ticket)
        if status == "Done":
            a2 = A2Eval(state="done", detail=f"{entry.jira_ticket} → Done")
        elif status is None:
            a2 = A2Eval(state="error", detail=f"{entry.jira_ticket} → lookup failed")
        else:
            a2 = A2Eval(state="open", detail=f"{entry.jira_ticket} → {status}")

    # A3: operator-marked in note
    note = (entry.note or "").lower()
    if "resolved in" in note:
        a3 = A3Eval(state="marked", detail="note contains 'resolved in ...' marker")
    else:
        a3 = A3Eval(state="unmarked", detail="no 'resolved in ...' marker in note")

    return SourceEvaluation(entry_id=entry.id, a1=a1, a2=a2, a3=a3)


# ----- transition -----


def close_entry(
    entry: PendingImprovementEntry,
    source: EvidenceSource,
    sprint: str,
    today: date,
    note: Optional[str] = None,
) -> PendingImprovementEntry:
    """Pure transition: returns a NEW entry with status=done + resolution_evidence.
    The original is unchanged. Caller persists."""
    new = entry.model_copy(update={
        "status": "done",
        "resolution_evidence": ResolutionEvidence(
            closed_at=today,
            closed_by=source.value,  # type: ignore[arg-type]
            closed_at_sprint=sprint,
            note=note or _default_note(source),
        ),
    })
    return new


def _default_note(source: EvidenceSource) -> str:
    return {
        EvidenceSource.JIRA_TICKET_DONE:
            "Linked Jira ticket reached status=Done.",
        EvidenceSource.OPERATOR_APPROVED:
            "Operator-approved closure via /sprint-cleanup.",
    }[source]


# ----- selection -----


def select_entries(
    entries: list[PendingImprovementEntry],
    sprint: str,
    include_backlog: bool = False,
) -> tuple[list[PendingImprovementEntry], list[PendingImprovementEntry]]:
    """Returns (in_scope, backlog). Two distinct buckets so the report can label
    each candidate's provenance."""
    if sprint == "backlog":
        return ([], [e for e in entries if e.sprint is None])

    in_scope = [e for e in entries if e.sprint == sprint]

    if include_backlog:
        backlog = [e for e in entries if e.sprint is None]
        return (in_scope, backlog)

    return (in_scope, [])
