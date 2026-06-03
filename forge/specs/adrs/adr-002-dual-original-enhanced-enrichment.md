---
id: ADR-002
title: Dual [original]/[enhanced] Enrichment
status: accepted
date: 2026-05-16
supersedes: null
superseded_by: null
---

# ADR-002: Dual `[original]` / `[enhanced]` Enrichment

## Context

`/enrich-us` is the first skill in the lifecycle. Its job is to take an operator-authored Jira ticket — typically terse, sometimes underspecified — and produce a complete technical specification with acceptance criteria, file paths, out-of-scope items, follow-ups, and SLA targets.

Two failure modes loomed:

1. **AI hallucination or over-specification**. The AI might enrich the ticket with paths that don't exist, files that aren't relevant, or scope creep the operator never intended. The operator needs a way to compare AI output against the original intent without leaving Jira.
2. **Loss of operator authorship**. If `/enrich-us` overwrites the operator's description, the operator's voice and the original framing disappear. That makes follow-up discussions ("but I asked for X, not Y") harder to ground.

We needed an enrichment pattern that was inspectable, reversible, and supportive of iterative re-enrichment (since `/enrich-us` may run more than once per ticket as scope evolves).

## Decision

`/enrich-us` PRESERVES the operator's original description and APPENDS the AI-generated content as a second section, with explicit headers separating the two:

- An H2 heading `[original]` marks the operator-authored content (verbatim, never edited).
- An H2 heading `[enhanced]` marks the AI-generated content immediately following.

Updates go in `[enhanced]`. Re-runs of `/enrich-us` replace `[enhanced]` in full while leaving `[original]` untouched. The operator can always recover the starting point.

## Consequences

### Positive

- **Reversibility**. The operator can fall back to the original intent at any time. Useful when the AI mis-scoped or hallucinated.
- **Auditability**. AI-generated text is clearly bounded by the H2 marker. Anyone reading the ticket post-hoc can see exactly what the AI added.
- **Iterative re-enrichment**. `/enrich-us` can be re-run when scope evolves; `[enhanced]` gets replaced cleanly without risking the original.
- **Grounded discussions**. When the operator pushes back ("but I asked for X"), `[original]` is the citation.

### Negative

- **Long ticket descriptions**. Most Jira tickets in this framework grow to 200-400 lines of description because the `[enhanced]` section carries the entire technical spec. The mobile Jira UX is awkward for that volume.
- **Two-section semantics confuse new contributors**. Anyone unfamiliar with the convention may edit `[original]` thinking they're updating the spec. Mitigated by the H2 marker being explicit and by `/enrich-us` itself being the only thing that writes `[enhanced]`.

### Operational

Every enriched ticket from 2026-04 onward uses this pattern. Examples: SCRUM-461, SCRUM-462, SCRUM-463, SCRUM-471, SCRUM-472, SCRUM-473. The pattern survives REST API enrichment (via ADF) and MCP enrichment equally — the `[original]/[enhanced]` markers are content-level, not transport-level.

## Alternatives Considered

- **Overwrite the original** — rejected. Information loss; no audit trail; operator cannot recover starting intent. The cost (long descriptions) of dual-section is much smaller than the cost (lost intent) of overwriting.
- **Store the original in a Jira comment, replace the description with `[enhanced]`** — rejected. Comments are less discoverable than descriptions; comment threads can be reordered; comments don't surface in Jira search the same way.
- **Use Jira labels or a custom field to store the original** — rejected. Not all Jira instances have those configured; portability suffers. Labels have length limits; custom fields require admin to set up.
- **External diff store** (commit the pre-enrichment ticket to a separate repo or file) — rejected. Two sources of truth; risk of drift. The Jira ticket should be self-contained.

## References

- `~/.claude/commands/enrich-us.md` — skill source of truth; Step 5 mandates `[original]` + `[enhanced]` H2 markers.
- Live tickets demonstrating the pattern: SCRUM-461 (Cap 5 hardening), SCRUM-462 (Phase 8 install), SCRUM-471 (evals harness), SCRUM-472 (backup + DR), SCRUM-473 (ADRs + CODEOWNERS — this ticket).
- ADR-001 (`adr-001-fw-004-state-machine.md`) — `state-machine.py advance enrich-us` writes `jira_hash` for drift detection between the local state and the Jira description.
