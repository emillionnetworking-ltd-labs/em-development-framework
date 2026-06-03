# Third-Party Notices

This framework is licensed under the MIT License (see [`LICENSE`](LICENSE)).
The sections below acknowledge upstream attributions and any third-party
content that ships with the distribution.

## Upstream framework template

The framework architecture originated from the **ai-specs** template
created by **LIDR.co** as part of the **AI4Devs** program, released under
the MIT License. The em-development-framework is an adapted and
substantially extended work derived from that template; the original MIT
terms are inherited and respected.

```
Attribution: ai-specs (LIDR.co / AI4Devs), MIT License.
```

The current framework codebase has diverged significantly from the
upstream template; most of the surface area (orchestrator graphs,
LangGraph engine, MCP server, distribution pipeline, audit harness,
state-machine engine, agent / skill / spec governance, CI safety net,
ADR conventions, etc.) is original work authored by EMillion Networking
LTD. This attribution acknowledges the architectural starting point.

## No other third-party content

At the time of v0.20.0, no additional third-party code, assets, fonts,
or media ship with this framework's distribution archive. Any future
addition of third-party dependencies will be recorded here at the time
of introduction with its attribution clause + MIT-compatibility check.

## Why this file exists

Centralized here so the rest of the repository — the README, scripts,
specs, agents, playbooks, and CI workflows — may remain free of
third-party brand references in commercial / active surfaces. The
compliance test suite
([`forge/tools/_tests/test_open_core_compliance.py`](forge/tools/_tests/test_open_core_compliance.py))
enforces this separation mechanically: third-party brand strings are
allowed ONLY in this file plus the test file itself; everywhere else
they fail CI immediately.

This is a design choice for **brand surface clarity**, not a slight
against the upstream attribution — the MIT obligation is fully honored
above. By concentrating the attribution here, contributors browsing the
codebase encounter EMillion's surface consistently, with the upstream
credit one click away in a single canonical location.

---

Copyright (c) 2026 EMillion Networking LTD
SPDX-License-Identifier: MIT
