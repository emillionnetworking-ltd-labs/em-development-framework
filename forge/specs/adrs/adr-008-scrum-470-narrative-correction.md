---
id: ADR-008
title: SCRUM-470 narrative correction (F4 archeology resolution)
status: accepted
date: 2026-05-17
supersedes: null
superseded_by: null
---

# ADR-008: SCRUM-470 narrative correction (F4 archeology resolution)

## Context

The 2026-05-17 re-audit identified F4 — a persistent test failure in `ai-specs/tools/_tests/test_state_machine.py::test_cli_advance_enrich_us_accepts_arbitrary_field`. The test asserted that `state-machine.py advance enrich-us ... --field bogus_field=bogus_value` should return exit code 0 (success). The live code returned exit code 2 with the error `"field 'bogus_field' not allowed for /enrich-us. Allowed: ['jira_hash']"`. The mismatch had been observed four times across SCRUM-478 + SCRUM-479 + F4-resolution and consistently classified `Pre-existing — to fix in a future ticket`.

SCRUM-480 ran the archeology that should have happened at the first observation. Single command tells the story:

```
$ git log --follow -S "jira_hash" --oneline ai-specs/tools/state-machine.py
da1590c feat(SCRUM-415): FW-004 — state-machine.py + 6 lifecycle commands wired
```

**Only one commit ever touched the line `'allowed_fields': ['jira_hash']`**. That commit is `da1590c` (SCRUM-415), the FW-004 origin commit. The whitelist has existed in its current single-element form since `state-machine.py` first appeared. There was no tightening at any point — there was no "before" to tighten from.

The F4 test was introduced by SCRUM-470 (commit `57774f8`) with the docstring "advance enrich-us is intentionally permissive on --field arguments. Bootstrap step accepts any key=value pair from the caller (SCRUM-470 documented as design)." That commit also rebautized the test from `test_cli_advance_disallowed_field_rejected` to `test_cli_advance_enrich_us_accepts_arbitrary_field` and inverted its assertion from `rc != 0` to `rc == 0`.

The SCRUM-470 commit message itself contains the claim:

> Decision: state-machine.py advance enrich-us IS intentionally permissive on --field arguments (bootstrap step, accepts arbitrary fields). Other advance commands (commit, update-docs) enforce strict whitelists via COMMAND_RULES. Asymmetry is by design.

The claim is **factually wrong**. The code that SCRUM-470 was supposedly ratifying never matched the claim. SCRUM-470 did not change `COMMAND_RULES`; it changed only the test (rename + assertion inversion). The "asymmetry by design" never existed in code; it existed only in SCRUM-470's misreading of code that had already existed for weeks prior.

## Decision

Ratify the current code (`COMMAND_RULES['enrich-us']['allowed_fields'] = ['jira_hash']` as the correct, intentional, longstanding design — established at SCRUM-415, never modified since).

### CI-revealed nuance (added 2026-05-17 after PR #24 first push)

The first iteration of this ADR claimed "all 6 commands enforce whitelists; there is no permissive bootstrap asymmetry". CI Job 5 on PR #24 surfaced that this framing was **incomplete**. The asymmetry is real, but for a different reason than SCRUM-470 claimed:

`cmd_advance` for `/enrich-us` has **two distinct code paths**:

- **Bootstrap path** (state.yml does NOT exist) — `state-machine.py:cmd_advance` lines 274-289 — delegates to `init-state.py` BEFORE field validation runs. `--field` args are **silently dropped** on this path. The shortcut returns `rc=0` and never inspects `args.field`. This is a side-effect of the bootstrap delegation, not design-intentional permissiveness.
- **Existing-state path** (state.yml exists) — line 297+ — runs the field-whitelist validation. Unknown `--field` args produce `rc=2` with `"field 'X' not allowed for /enrich-us. Allowed: ['jira_hash']"` on stderr.

**SCRUM-470's observational claim was correct**: bogus `--field` invocations on /enrich-us advance return `rc=0`. **SCRUM-470's causal claim was wrong**: this is not "intentional permissiveness on --field whitelisting"; it is the bootstrap path bypassing validation entirely. Two very different things.

The initial first-pass ADR-008 (pre-CI) over-corrected by denying the asymmetry. The accurate framing acknowledges both: the asymmetry IS real (between bootstrap and existing-state paths); the SCRUM-470 narrative was wrong about WHY it exists.

### Correctives applied in SCRUM-480

1. **Test split** (revised after CI feedback): the original "one test asserting rc=2" replaced with TWO tests:
   - `test_cli_advance_enrich_us_bootstrap_ignores_unknown_field`: exercises bootstrap path with sentinel ticket `PYTEST-3` (with explicit pre-cleanup of stale state.yml). Asserts `rc=0` + `--field` is silently dropped.
   - `test_cli_advance_enrich_us_existing_state_rejects_unknown_field`: pre-creates state.yml via bootstrap, then exercises existing-state path with sentinel ticket `PYTEST-2`. Asserts `rc=2` + stderr substring + whitelist `['jira_hash']` reported.
2. **Inline comments in `state-machine.py`**:
   - Above `COMMAND_RULES` declaration (around line 56): a 14-line NOTE block declaring the two-path asymmetry + cross-reference to the two tests + this ADR.
   - Inside `cmd_advance` bootstrap branch (line 274): NOTE clarifying the bootstrap shortcut delegates to init-state.py and silently drops `--field` (replaces the prior misleading SCRUM-470 comment).
3. **CI workflow update**: `.github/workflows/ci.yml` pytest job adds `fetch-depth: 0` to `actions/checkout@v6` so `git cat-file -e` resolves long-form SHAs that appear in records. Without full history, GRD-002a SHA-existence checks produce false positives on CI for SHAs that exist in the framework's main branch but aren't in the shallow tree. This caused `test_corpus_no_new_violations_vs_snapshot` to fail on CI even though local environments (full history) pass.
4. **This ADR** as the canonical correction. Per `adrs/README.md` convention, the body of this ADR can be amended **during the same PR cycle** that introduces it (ADR-008 lands at SCRUM-480 merge; the CI-revised content above is part of the same merge). Post-merge the body is immutable per convention.

## Consequences

- F4 closes. Two replacement tests (`bootstrap_ignores_unknown_field` + `existing_state_rejects_unknown_field`) pass against current code, and the suite returns to fully PASS for the first time in the Phase 3 → 4.1 wave.
- The framework's audit trail now contains an explicit correction of a prior record's narrative error. This is the first ADR of its kind in the framework — prior ADRs documented design decisions, not corrections.
- New norm established (codified in this ADR's References + reinforced in SCRUM-480 record §10 Lessons Learned): **when a test-detector fires, the first observation must run archeology before classifying Pre-existing.** Compound deferral of a test failure is a smell; archeology is cheap; do it.
- **Second norm established (CI-revealed in SCRUM-480)**: **archeology alone is insufficient if the test environment masks the failure mode.** Local environments with leftover sentinel state files (PYTEST-2.yml gitignored per SCRUM-463) or full git history can pass tests that fail on CI's fresh shallow checkout. `/verify` Step 4c "build + tests PASS" must include "tests pass in a CI-equivalent environment" — operator should run pytest after `rm -f ai-specs/changes/framework/state/PYTEST-*.yml` to simulate fresh checkout before claiming verify PASS.
- The SCRUM-470 record body remains unchanged (immutable per `adrs/README.md` convention). Readers of that record should follow the ADR-008 cross-reference for the corrected narrative.
- No production code path is affected. `enrich-us` whitelist behavior is unchanged; only the test that misrepresented it changes.

## Alternatives Considered

- **(A) Widen `enrich-us` allowed_fields to accept arbitrary fields** — rejected. This would invalidate the SCRUM-415 origin design and create the asymmetry SCRUM-470 wrongly claimed already existed. No caller of `state-machine.py advance enrich-us` has ever needed fields beyond `jira_hash`; widening serves no purpose other than retroactively making SCRUM-470's narrative true. That is exactly the wrong reason to make a code change.
- **(B) Ratify with ADR without correcting SCRUM-470 narrative** — rejected. Leaves the SCRUM-470 commit message + record + test docstring in the corpus as the canonical record of "the design", with no in-repo signal that they are wrong. Future readers (human or AI) would re-derive the same incorrect narrative.
- **(D) Edit SCRUM-470 record in place to fix the narrative** — rejected. Records are immutable per `adrs/README.md` ADR convention. Editing them undermines the principle that frozen artifacts stay frozen. ADRs are the canonical correction instrument.

## References

- **SCRUM-415** (`da1590c`) — origin of `state-machine.py` with `'allowed_fields': ['jira_hash']` for /enrich-us. Single source of truth for the design.
- **SCRUM-470** (`57774f8`) — the misdocumentation; commit message + test docstring contain the factually incorrect "permissive design" claim.
- **`ai-specs/changes/framework/records/backlog/SCRUM-470_backend.md`** — immutable record body retained as-is per ADR convention. Reader should cross-reference this ADR for the corrected narrative.
- **`ai-specs/changes/framework/audits/2026-05-17-re-audit/F4-resolution.md`** — the deferral record that observed the issue at LOW severity prior to archeology. This ADR closes F4.
- **SCRUM-480 record §9 Audit Finding Verification + §10 Lessons Learned** — implementation context + new norm "run archeology on first test-detector observation".
- **`adrs/README.md`** convention: record bodies immutable; ADRs are the canonical correction instrument.
- **`ai-specs/tools/state-machine.py`** lines 56-61 — inline comment added by SCRUM-480 referencing this ADR.
- **`ai-specs/tools/_tests/test_state_machine.py`** — `test_cli_advance_enrich_us_rejects_unknown_field` (renamed + inverted by SCRUM-480).
