#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""classify-deviation — FW-005 / framework release layer · CLI shell.

Thin CLI entrypoint. All logic lives in the importable library
`_classify_deviation.py` (ADR-006: forge/tools/ is not a package; the hyphen
in this filename blocks `import`, so the logic is a sibling underscore module).
Invocation unchanged: `python3 forge/tools/classify-deviation.py ...`.

This tool is interactive and creates Jira tickets; `run_cli` keeps the historical
CLI sys.exit semantics internally and returns None (→ exit 0) on success.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _classify_deviation import run_cli  # noqa: E402


def _print_taxonomy():
    """<TICKET-ID>: pretty-print the deviation taxonomy SSoT for operator inspection."""
    import yaml
    from _common import find_framework_root
    root = find_framework_root()
    if root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 1
    tax_path = root / "forge" / ".deviation-taxonomy.yml"
    if not tax_path.is_file():
        print(f"ERROR: deviation taxonomy SSoT missing at {tax_path}", file=sys.stderr)
        return 1
    with tax_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    print("== Deviation Taxonomy SSoT ==")
    print(f"   source: {tax_path.relative_to(root)}")
    print(f"   schema: forge/schemas/deviation-taxonomy.schema.yml")
    print()
    print("Categories (6):")
    for c in data.get("categories", []):
        block = "BLOCKS" if c["blocks_merge"] else "no-block"
        ticket = "ticket" if c["creates_ticket"] else "no-ticket"
        approval = " (operator approval required)" if c["requires_user_approval"] else ""
        print(f"  - {c['name']} [{block}, {ticket}, sprint={c['sprint_target']}]{approval}")
        print(f"      {c['criteria']}")
    print()
    print("Decision tree (5 questions; first YES wins; fallthrough -> Scope-Gap):")
    for i, q in enumerate(data.get("questions", []), 1):
        print(f"  {i}. [{q['key']}] -> {q['category']}")
        print(f"      {q['prompt']}")
    print()
    print("Anti-patterns:")
    for ap in data.get("anti_patterns", []):
        print(f"  - {ap}")
    print()
    print("Audit-standards.mdc mapping:")
    for m in data.get("audit_mapping", []):
        print(f"  - {m['verify_category']} -> {m['audit_class']}")
        print(f"      {m['why']}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--print-taxonomy':
        sys.exit(_print_taxonomy())
    sys.exit(run_cli(sys.argv[1:]))
