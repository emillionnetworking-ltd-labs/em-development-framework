---
version: 2.0.0
status: active
category: reference
description: Community contribution guide for the em-development-framework public distribution.
last_changed: 2026-06-03
license: MIT
copyright: "Copyright (c) 2026 EMillion Networking LTD"
---

# Contributing

Thank you for your interest in the **em-development-framework**.

This repository is the public **distribution mirror** of the framework — a frozen 148-file snapshot of each tagged release. The development happens in the private source repository, where the operator and AI agents drive the lifecycle workflow that produces these releases.

## License

The framework is released under the [MIT License](LICENSE). You may use, modify, distribute, and build on it freely, including in commercial contexts. By submitting any contribution (idea, bug report, or otherwise) you agree that it is licensed under the same terms.

Upstream attributions live in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## How to contribute

### Pull requests

Pull requests are **not accepted** on this public mirror. The PUBLIC repo's `main` is mechanically restricted to the mirror-bot via branch protection — only release snapshots produced by the private source repo land here.

This is a deliberate design choice from ADR-014: the framework's development workflow assumes a single coherent lifecycle (state machine, integration-state tracking, schema validation, groundedness checks) that cannot accept arbitrary external commits without breaking its invariants.

### Discussions

Open a **GitHub Discussion** to share:
- Ideas for new features, agents, or playbooks.
- Bug reports against a specific release tag.
- Questions about how to adapt the framework for your product.
- Feedback on the operator workflow, lifecycle ergonomics, or strategy engine.

The operator monitors Discussions and cherry-picks community ideas into the private source repo, where they are sequenced through the full lifecycle (enrich-us → plan → develop → verify → commit → update-docs).

### Issues

Issues are enabled on this public mirror for bug reports tied to a specific release. For implementation questions or design feedback, prefer Discussions.

When filing an issue, please include:
- The release tag you are running (`cat VERSION`).
- The exact command or workflow that triggered the bug.
- The full error output or unexpected behavior.

## For operators with source access

If you have access to the private source repository, follow the detailed compliance conventions documented in `CONTRIBUTING-DEV.md` (Plantilla A markdown frontmatter, Plantilla B SPDX headers, the 11 active Open-Core invariants, the §0 Specs Index, the bump-on-edit CI gates, and the 6-step lifecycle workflow). That document is operator-only and lives only in the private repo by design.

## Code of conduct

Be kind, be specific, be patient. The framework is a young project maintained by a small team — substantive feedback is welcome; demands and gatekeeping are not.

---

**Maintained by [EMillion Networking Labs](https://github.com/emillionnetworking-ltd-labs)**
