---
id: ADR-013
title: Open-Core licensing transition — MIT adoption, SPDX convention, frontmatter retirement
status: accepted
date: 2026-06-02
supersedes: null
superseded_by: null
---

# ADR-013: Open-Core Licensing Transition

## Status

**Accepted** (2026-06-02, SCRUM-617 Wave 49, Sprint 24 Open-Core MIT). The 7-wave execution roadmap (W49 → W55) is unlocked.

## Context

The framework — initially developed as a closed internal toolchain for the EM Ecosystem (NexaCore + Satellites) — has progressively shed its product-specific coupling over Sprints 20–23. Three strategy debates (`framework-product-decoupling-v2-multi-agent-gateway`, `framework-distribution-layer`, `framework-clean-packaging`) and 22 consecutive CI-clean waves (W27 → W48) brought the codebase to a distributable state: workspace contract via `forge.config.yml`, distribution layer with installer + clean-archive, multi-agent gateway via `AGENTS.md` / `CLAUDE.md` / `.cursorrules` / etc.

However, the framework's **legal metadata still encodes proprietary semantics**:

1. **Root LICENSE**: contains `Copyright (c) 2026 EMillion Networking LTD. All rights reserved.` — incompatible with any public distribution.
2. **Active markdown frontmatter** (~38 files across `forge/specs/`, `forge/.playbooks/`, `forge/.agents/`): carries `owner: EM Ecosystem`, `legal: "Copyright (c) 2026 EMillion Networking LTD. All rights reserved."`, `security_level: L1-Internal`. These fields signal restricted-distribution semantics and contradict any OSS adoption path.
3. **Code files** (~120 across `framework/`, `orchestrator/`, `scripts/`, `forge/tools/`, `.github/workflows/`): carry no license header at all. Per OSS convention (SPDX standard, Linux Foundation OpenSSF, REUSE compliance), every distributable code file should declare its license via `SPDX-License-Identifier`.
4. **No CI gates** prevent regression to proprietary language. Future contributors could re-introduce "L1-Internal" or "All rights reserved" without mechanical alarm.

The framework architecturally targets Open-Core distribution: a permissively-licensed core surface plus future Premium plugins under separate proprietary license. Without a formal licensing decision, the Strategy v2/v3/v4 stack landed in Sprints 21–23 has no legal anchor — distribution-ready code paired with restrictive metadata is contradictory.

This ADR is the gate: it formalizes the licensing decision and authorizes the 7-wave Sprint 24 execution sequence.

## Decision

Adopt the following Open-Core compliance posture for the framework core:

### Decision 1 — Adopt the **MIT License**

Replace the root `LICENSE` file's proprietary text with the canonical OSI MIT License text. Copyright holder remains **EMillion Networking LTD**; year is **2026** (the current annual snapshot; renewable annually).

### Decision 2 — SPDX-License-Identifier convention on code files

Every code file (`.py`, `.sh`, `.ps1` repo-wide minus exempted directories; `.yml`/`.yaml` only inside `.github/workflows/`) MUST carry a 2-line header within its first 1024 bytes:

```
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
```

For files with a shebang, the SPDX block follows immediately after the shebang and before any module docstring.

Data YAMLs elsewhere (`forge/registers/`, `forge/schemas/`, `forge/.framework-modules.yml`, `forge.config.yml`) are **not code** and rely on the root LICENSE umbrella. Empty `__init__.py` markers (<100 bytes) are exempt.

### Decision 3 — Frontmatter migration on markdown surfaces (specs + playbooks + agents)

Retire three proprietary fields and replace with two public-friendly fields:

| Removed | Replaced by |
|---|---|
| `owner: EM Ecosystem` | (subsumed into `copyright`) |
| `legal: "Copyright (c) 2026 EMillion Networking LTD. All rights reserved."` | `license: MIT` |
| `security_level: L1-Internal` | `copyright: "Copyright (c) 2026 EMillion Networking LTD"` |

The new frontmatter target shape is:

```yaml
---
version: X.Y.Z
status: active                                    # active|stable|draft|deprecated|parked
category: spec                                    # spec|skill|agent|reference
title: Human-readable title
description: One-line summary
last_changed: YYYY-MM-DD
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
alwaysApply: true|false                           # preserved on .mdc files
globs: []                                         # preserved on .mdc files
---
```

ADRs (`forge/specs/adrs/*.md`) are historical documents and retain their existing convention (`id/title/status/date/supersedes/superseded_by`); they rely on the root LICENSE umbrella.

### Decision 4 — CI compliance gates (three invariants)

Author `forge/tools/_tests/test_open_core_compliance.py` enforcing three orthogonal invariants:

1. **Frontmatter license invariant** — every active spec/playbook/agent has `license: MIT` and `copyright` without "All rights reserved".
2. **SPDX header invariant** — every code file (scoped per Decision 2) contains `SPDX-License-Identifier: MIT` in its first 1024 bytes.
3. **Confidentiality drift invariant** — no public-core file contains forbidden strings: `All rights reserved`, `L[0-9]-Internal`, `Confidential`, `Proprietary`, `Internal use only`. Allowlist exceptions: `LICENSE`, `CHANGELOG.md`, `forge/_parked/**`, historical ADRs (`adr-003-*`), `.lifecycle/**`, `.git/**`, the test file itself.

Phased activation via `pytest.mark.xfail(strict=True)` during W51; xfails removed incrementally as W52/W53/W54 complete.

### Decision 5 — Premium plugin boundary deferred

The Open-Core monetization model envisions Premium plugins under separate proprietary license. ADR-013 does **not** define that boundary; a future ADR-N (post-Sprint 24) will document how Premium plugins co-exist with the MIT core (separate repo vs `forge-premium/` subtree with its own LICENSE).

## Alternatives Considered

### A. Apache License 2.0

**Pro**: explicit patent grant; widely used in enterprise contexts (Apache Foundation, Google projects). Includes NOTICE file convention for attribution.

**Con**: more verbose than MIT; NOTICE file adds a maintenance vector; patent grant is meaningful only if EMillion Networking LTD holds patents in framework's technical domain (it does not).

**Verdict**: rejected. MIT is simpler, more widely understood by individual contributors, and the patent grant is non-load-bearing here.

### B. BSD-3-Clause

**Pro**: similar permissive semantics to MIT; well-respected lineage (Berkeley).

**Con**: includes a "no-endorsement" clause that constrains how downstream marketing can reference EMillion. Adds friction without meaningful protection.

**Verdict**: rejected. MIT is functionally equivalent without the endorsement clause.

### C. Mozilla Public License 2.0

**Pro**: file-level copyleft — modifications to MPL files stay under MPL even when bundled into proprietary applications. Protects against pure fork-and-close while still allowing commercial use.

**Con**: file-level copyleft creates friction for the Open-Core model: Premium plugins would need to avoid modifying MPL files or else become MPL themselves. MPL is the right answer when the goal is *content protection* of the core itself; here the goal is *adoption acceleration* of the core with monetization via Premium *separate-file* plugins.

**Verdict**: rejected. The Open-Core boundary lives at the file boundary anyway (core files vs premium files), not inside individual files; MPL's protection vector adds no value and constrains plugin design.

### D. Dual MIT + Commercial license

**Pro**: maximum optionality — open users get MIT, commercial users buy a commercial license that grants additional warranties / support.

**Con**: meaningful only when there is a customer base willing to pay for the commercial track instead of using MIT for free. Today's framework has no such customer base. Adopting dual-license now is premature optimization.

**Verdict**: deferred. Future ADR-N may add a dual-license track if customer demand emerges. For Sprint 24, single MIT license is the right scope.

### E. Status quo (continue proprietary)

**Pro**: zero work; legal posture unchanged.

**Con**: Strategy v2/v3/v4 stack landed in Sprints 21–23 (workspace contract, multi-agent gateway, clean distribution archive) becomes architectural dead-letter — distribution-ready code cannot legally distribute. Wastes ~50+ Waves of decoupling work.

**Verdict**: rejected. The cost of preparation has been paid; the unlock is one Sprint of metadata migration.

## Consequences

### Positive

1. **Open-Core distribution unlocked**. Framework can ship via npm / pip / GitHub Releases under MIT terms, accepting community contributions.
2. **Standards-compliant**. SPDX adoption enables REUSE compliance, GitHub Linguist license detection, OpenSSF tooling integration.
3. **Reduced metadata maintenance**. Frontmatter shrinks 3 fields → 2 fields (`owner`/`legal`/`security_level` → `license`/`copyright`).
4. **Mechanical drift prevention**. Three CI invariants make regression to proprietary language fail-fast.
5. **Premium plugin track viable**. Open-Core boundary becomes a feature, not a contradiction.

### Negative

1. **Point of no return at W50**. Once LICENSE is swapped + pushed + a third party clones the snapshot, they hold perpetual MIT rights for that revision. Reverting future commits cannot revoke those rights.
2. **Frontmatter surface migration touches ~38 files in one PR (W53)**. Coordination window required to avoid merge conflicts with in-flight skill/spec edits.
3. **Code surface migration touches ~120 files in one PR (W52)**. Same coordination concern; mitigated by bulk-script + single atomic commit per phase.
4. **Premium plugin boundary remains TBD**. ADR-013 does not constrain Premium plugin design; future ADR-N must close that gap before Premium ships.

### Neutral

- Copyright holder remains EMillion Networking LTD. Authorship is not redistributed by MIT — the copyright notice persists in every file's header and in the LICENSE file.
- Existing internal users (operator-driven sessions) experience no functional change.

## CI Invariants (specification)

```python
# Invariant 1: Frontmatter license=MIT
def test_frontmatter_license_is_mit(spec_path):
    fm = extract_frontmatter(spec_path)
    assert fm.get("license") == "MIT"
    assert "All rights reserved" not in fm.get("copyright", "")

# Invariant 2: SPDX header on code files (anchor regex)
SPDX_RE = re.compile(rb"^[^\n]*#[^\n]*SPDX-License-Identifier:\s+MIT", re.MULTILINE)

def test_code_file_has_spdx_header(path):
    head = path.read_bytes()[:1024]
    assert SPDX_RE.search(head)

# Invariant 3: No confidentiality drift
FORBIDDEN_PATTERNS = [
    rb"\bAll rights reserved\b",
    rb"\bL[0-9]-Internal\b",
    rb"\bConfidential\b",
    rb"\bProprietary\b",
    rb"Internal use only",  # case-insensitive
]

def test_no_confidentiality_drift_in_public_core():
    violations = scan_repo(FORBIDDEN_PATTERNS, allowlist=ALLOWLIST_GLOBS)
    assert not violations
```

Full implementation lives in W51 (`forge/tools/_tests/test_open_core_compliance.py`).

## Execution Roadmap (Sprint 24)

ADR-013 authorizes the 7-wave Sprint 24 sequence (SCRUM-617 → SCRUM-623). Dependencies are strictly serial — each wave removes one or more `xfail` markers added by W51:

| Wave | Ticket | Scope | Removes xfail |
|------|--------|-------|---------------|
| **W49** | SCRUM-617 | THIS ADR; paper-only | — |
| **W50** | SCRUM-618 | LICENSE swap (proprietary → MIT) + README badge | — (W51 not yet authored) |
| **W51** | SCRUM-619 | Author `test_open_core_compliance.py` with all 3 invariants xfail-strict | — (xfails activated for first time) |
| **W52** | SCRUM-620 | Bulk inject SPDX headers on ~120 code files | Invariant 2 xfail removed |
| **W53** | SCRUM-621 | Migrate ~38 markdown frontmatters; update `test_specs_structure.py` | Invariant 1 xfails removed |
| **W54** | SCRUM-622 | Confidentiality marker scrub (body text residuals) | Invariant 3 xfail removed |
| **W55** | SCRUM-623 | CONTRIBUTING.md + Sprint 24 closure | — (all xfails already removed) |

### Coordination window

W52 + W53 + W54 each touch many files in single atomic commits. Operator should pause non-essential edits on the affected surfaces during the migration sequence (estimated 1–3 days):

- W52: `framework/`, `orchestrator/`, `scripts/`, `forge/tools/`, `.github/workflows/`.
- W53: `forge/specs/`, `forge/.playbooks/`, `forge/.agents/`.
- W54: any markdown/yaml/python/shell file in repo (regex sweep with allowlist).

### Per-wave rollback

Each wave is one squash-merge PR. `git revert <merge-sha>` restores the prior state cleanly. **EXCEPTION**: W50 LICENSE swap is **legally irreversible for any snapshot that was cloned post-merge** (MIT rights are perpetual for that revision). The git revert restores the LICENSE file but does not revoke rights already granted.

## References

- **SPDX standard**: https://spdx.dev/ — license identifier convention.
- **OSI MIT License**: https://opensource.org/licenses/MIT — canonical text and metadata.
- **REUSE compliance**: https://reuse.software/ — Linux Foundation specification for file-level licensing.
- **Strategy v2** (framework-product-decoupling-v2-multi-agent-gateway): closed-out report in `.strategy-sessions/`.
- **Strategy v3** (framework-distribution-layer): closed-out report in `.strategy-sessions/`.
- **Strategy v4** (framework-clean-packaging): closed-out report in `.strategy-sessions/`.
- **ADR-001 → ADR-012**: prior architectural decisions, lineage of `forge/` governance evolution.

## Future ADRs anticipated

- **ADR-014** (post-W55, deferred): Premium plugin license boundary. Defines whether premium plugins co-exist in `forge-premium/` subtree (monorepo with dual LICENSE) or live in a separate repository.
- **ADR-015** (deferred): Trademark / branding policy. MIT does not grant trademark rights; explicit policy needed if the framework gains brand recognition.

---

*This ADR is the architectural authorization for the Sprint 24 sequence. Without it, the 6 downstream tickets (SCRUM-618 → SCRUM-623) lack legal justification.*
