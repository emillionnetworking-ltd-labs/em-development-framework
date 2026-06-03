---
id: ADR-014
title: Repo bifurcation — private dev / public clean mirror (P1-StandardSplit)
status: accepted
date: 2026-06-03
supersedes: null
superseded_by: null
---

# ADR-014: Repo Bifurcation — Private Dev / Public Clean Mirror

## Status

**Accepted** (2026-06-03, SCRUM-626 Wave 58, Sprint 27 Repo Bifurcation). The 5-wave execution roadmap (W58 → W62) is fully unlocked.

## Context

The framework's public GitHub repo (`emillionnetworking-ltd-labs/em-development-framework`, public, MIT) currently exposes 86% of file surface that the operator does NOT want public-visible. Operator decision (2026-06-03): the public repo must become EXCLUSIVELY a distribution-facing surface for end users; all internal development artifacts must be hidden from public view.

### Current state (post-Sprint 26 / W57)

- Single public repo with 1073 files via `git clone`
- Only 144 files actually ship in the distribution archive (via `.gitattributes export-ignore` on tag push)
- 929 files are dev-internal but PUBLICLY VISIBLE via `git clone`:
  - 613 lifecycle wave artifacts (`.lifecycle/**`)
  - 55 strategy session debates (`orchestrator/.strategy-sessions/**`)
  - 59 test files (`forge/tools/_tests/**`, `forge/evals/**`, `framework/tests/**`, `orchestrator/tests/**`)
  - 17 parked content (`forge/_parked/**`)
  - 8 misc (`.github/`, `scripts/`, `.claude/`, `forge/registers/`)
- v0.5.0 through v0.20.0 (10 release tags) already published publicly under MIT (irrevocable for clones)
- 31 consecutive waves CI-clean
- 10 compliance invariants ACTIVE post-W57 white-label scrub
- ZERO stars / forks / issues / community PRs at decision time (clean window for architectural change)

### The single-repo + export-ignore baseline

The current setup correctly produces clean DISTRIBUTION TARBALLS via `git archive` + `.gitattributes export-ignore`. The Wave 56 forensic audit verified the v0.20.0 tarball ships only 144 files. This is robust for the distribution channel.

The baseline FAILS only on the new operator requirement: "public repo must be exclusively distribution-facing for end users". GitHub has no native mechanism to hide directories from the repo browser. `git clone` exposes the full tree regardless of `.gitattributes`.

This architectural mismatch cannot be resolved by additional sanitization within the single-repo model. A structural change is required.

### Why bifurcation now

The decision window is uniquely favorable: zero stars, zero forks, zero PRs at this moment. Any history-rewrite, force-push, or fresh-public-repo strategy carries near-zero community impact today. This window will narrow as the framework gains adoption.

## Decision

Adopt **P1-StandardSplit-Refined** (approved by operator in `/strategy` session `framework-distribution-architecture-bifurcation`, 2026-06-03, after 1 self-refine cycle and Critic verdict STRONG).

### Architecture

Two physical GitHub repositories:

```
PRIVATE: emillionnetworking-ltd-labs/em-development-framework-dev
  ├─ Full kitchen (1073 files, operator+agent workflow)
  ├─ All dev activity, lifecycle artifacts, strategy sessions
  ├─ Internal issues/PRs/Discussions
  ├─ Full CI (ci.yml + install-matrix.yml + release.yml)
  └─ On tag-push of vX.Y.Z, triggers distro-mirror.yml workflow

                  ↓ filtered mirror (via git archive + .gitattributes export-ignore)

PUBLIC: emillionnetworking-ltd-labs/em-development-framework
  ├─ Clean 144 files only
  ├─ One commit per release tag (append style on main)
  ├─ Preserves existing GitHub Releases UI (v0.5.0 .. v0.20.0)
  ├─ Issues/Discussions enabled for community (PRs NOT accepted; via Discussions)
  ├─ Minimal CI (install-matrix.yml + release.yml only)
  └─ Branch protection: mirror Action is the only authorized writer to main
```

### Key technical decisions

1. **Authentication**: GitHub App with OIDC trusted publishing between repos. No static tokens, no PATs.
2. **Trigger**: `tags: ['v*.*.*']` regex filter on PRIVATE. Excludes local checkpoint tags.
3. **Granularity**: one commit per release on PUBLIC main (append style, not orphan force-push).
4. **Manifest validation**: NEW `forge/.distribution-manifest.yml` frozen list of expected files. Validated pre-push + post-push in mirror workflow.
5. **Drift detection**: cron-scheduled `tag-mirror-validator.yml` runs every 6h, opens GitHub issue on PRIVATE if PUBLIC tree diverges.
6. **Recontamination prevention**: NEW Invariant 11 (`test_no_forbidden_paths_in_distribution`) asserts manifest matches archive output deterministically.
7. **Issue/PR policy**: community PUBLIC issues + Discussions; internal Jira + PRIVATE issues for dev work. PRs not accepted on PUBLIC (community contributes via Discussions; operator cherry-picks ideas into PRIVATE).

## Alternatives Considered

### A. E2 — Snapshot-per-release (one orphan commit per release, force-push)

**Pro**: stricter separation; PUBLIC commit history is purely synthetic; no intermediate metadata leak via commit messages between releases.

**Con**: force-push on every release destabilizes any future fork (irrelevant today); changes commit SHAs every release (breaks external pinners, uncommon for tarball-based distribution); psychological perception in OSS ('force-push' has bad connotations).

**Verdict**: rejected. P1's append-commit style is more conventional and equally clean.

### B. E3 — Flip current public to private + create new public with same slug

**Pro**: clean slate for PUBLIC.

**Con**: at decision time this was framed as social-signal preservation; with zero stars/forks/issues, the social cost is nil. However, E3 conflates two operations (privatize + create new) that P1 handles more cleanly via rename.

**Verdict**: subsumed by P1 (P1's cutover effectively flips current to private via rename + creates fresh public).

### C. E4 — In-place history rewrite via `git filter-repo`

**Pro**: single repo, no mirror infrastructure.

**Con**: DESTRUCTIVE — rewrites all commit SHAs (including v0.20.0 tag SHA), invalidates signatures, breaks GRD-002a SHA audit trail, destroys the framework's own audit posture. Recontamination scenario: the framework lifecycle skills CONTINUOUSLY generate `.lifecycle/` artifacts as the operator works; a pre-commit hook blocking those paths would force the operator to disable the hook (defeating the purpose) or stop using the framework's own lifecycle workflow.

**Verdict**: vetoed in Critic round 1 of strategy session. Structurally incompatible with the framework's runtime architecture.

### D. E5 — Git submodule/subtree split

**Pro**: maintains single-repo aparente.

**Con**: anti-pattern in OSS. Users hate submodules. Authentication complexity. Friction at every clone.

**Verdict**: rejected.

### E. E6 — Branch-based with default swap

**Pro**: single repo. PUBLIC main is clean by default.

**Con**: `dev` branch still accessible via GitHub branch switcher. Does NOT satisfy operator requirement ("not visible to public").

**Verdict**: rejected (insufficient).

### F. P4 — Hybrid: filter-repo cleanup + then split

**Pro**: PRIVATE history is retroactively clean.

**Con**: filter-repo invalidates GRD-002a audit trail (all retroactive SHA citations in lifecycle records / ADRs / integration-state.md become non-reachable). Marginal incremental benefit over P1 at substantial additional risk + complexity. Hedges against low-probability future PRIVATE permission misconfiguration.

**Verdict**: rejected by Critic in final review. P1 is the right tier of investment.

## Consequences

### Positive

1. **Clean public face**: PUBLIC repo shows only 144 distributable files; professional appearance.
2. **Preserves audit trail**: no history rewrite on PRIVATE; GRD-002a discipline intact.
3. **Scaling foundation**: same pattern works for future Premium plugin track (additional repos with similar mirror).
4. **Recontamination resistance**: Invariant 11 mechanical guard + cron drift detector + branch protection on PUBLIC.
5. **Existing release artifacts preserved**: v0.5.0 .. v0.20.0 Releases UI page persists independent of source surface.
6. **Reversible**: pre-cutover backup tarball + revert mirror push restore original.

### Negative

1. **Operational overhead**: 2 repos to administer (GitHub settings, branch protection, secrets).
2. **Mirror sync failure risk**: requires cron validator + manifest check to detect silent drift.
3. **Lost OSS transparency**: community sees only releases, not dev process.
4. **Community PR flow**: replaced by Discussions; operator cherry-picks ideas into PRIVATE.

### Neutral

- License (MIT) unchanged.
- Existing 10 compliance invariants intact on PRIVATE.
- Operator + agent workflow unchanged on PRIVATE.

## Roadmap

ADR-014 authorizes the 5-wave Sprint 27 sequence:

| Wave | Ticket | Scope |
|------|--------|-------|
| **W58** | SCRUM-626 | THIS ADR + backup tarball + operator GitHub App runbook (paper-only) |
| **W59** | SCRUM-627 | Mirror workflow infrastructure on PRIVATE (workflow_dispatch only) |
| **W60** | SCRUM-628 | NEW Invariant 11 + `forge/.distribution-manifest.yml` |
| **W61** | SCRUM-629 | **CUTOVER**: rename + fresh PUBLIC + first mirror push + branch protection |
| **W62** | SCRUM-630 | Comms (READMEs) + CI separation + CONTRIBUTING fork + Sprint 27 SEAL |

### Per-wave rollback

Each wave produces a single squash-merge PR. `git revert <merge-sha>` restores the pre-wave state cleanly. EXCEPTION: W61 cutover is partially irreversible at the GitHub admin level (rename + force-push); the backup tarball from W58 is the recovery anchor.

## Sub-Decision Resolutions (10 from strategy session)

1. **Public commit history granularity**: one commit per release (append style on PUBLIC main).
2. **Issue tracker policy**: PUBLIC issues + Discussions for community; PRIVATE issues + internal Jira for dev.
3. **Stars/forks preservation strategy**: zero today; rename current public to PRIVATE keeps existing star count (zero); fresh PUBLIC starts at zero.
4. **First public-clean push semantics**: force-push reset on fresh PUBLIC (zero-fork window makes this safe).
5. **Mirror workflow trigger**: on tag push only, with regex filter `^v[0-9]+\.[0-9]+\.[0-9]+$`.
6. **Disaster recovery**: backup tarball + cron drift detector + manual override runbook.
7. **Contributor onboarding**: community via Discussions; PRs not accepted on PUBLIC; operator may cherry-pick into PRIVATE.
8. **Migration timeline**: 5 waves, atomic cutover in Wave 61.
9. **CI architecture**: full CI on PRIVATE (`ci.yml` + `install-matrix.yml` + `release.yml`); PUBLIC has ONLY `install-matrix.yml` + `release.yml`.
10. **License + NOTICES**: ship on both repos; identical content via mirror.

## References

- **Strategy session executive report**: `orchestrator/.strategy-sessions/framework-distribution-architecture-bifurcation/000009-*.json` (final checkpoint).
- **ADR-013**: `forge/specs/adrs/adr-013-open-core-licensing-transition.md` — Open-Core licensing decision that enabled bifurcation viability.
- **ADR convention**: `forge/specs/adrs/README.md`.
- **Operator runbook**: `forge/secrets-policy.md` — GitHub App provisioning steps.
- **Backup tarball**: `/tmp/em-framework-pre-bifurcation-backup.tar.gz` (operator-local, not in repo).
- **Distribution manifest**: `forge/.distribution-manifest.yml` (created in W60).

## Future ADRs Anticipated

- **ADR-015** (post-cutover, optional): Premium plugin license boundary. Defines whether Premium plugins co-exist in `forge-premium/` subtree (monorepo with dual LICENSE) or live in a separate repository.

---

*This ADR is the architectural authorization for the Sprint 27 sequence. Without it, the 4 downstream tickets (SCRUM-627 → SCRUM-630) lack legal justification. The operator has approved the P1-StandardSplit-Refined architecture in the strategy session human gate (2026-06-03).*
