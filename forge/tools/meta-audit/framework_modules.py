#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""meta-audit/framework_modules.py — framework meta-audit for MODULE BOUNDARIES.

The 2nd meta-audit subsystem (<TICKET-ID> / framework release layer). Walks the entries in
`forge/.framework-modules.yml` and verifies each declared module's boundaries
against the actual source tree via Python `ast` analysis.

LangGraph patterns (State / Nodes / Edges) modeled as PURE FUNCTIONS — the
`langgraph` library is NOT imported.

Invoked by path (ADR-006):

    python3 forge/tools/meta-audit/framework_modules.py [--json] [--module <name>]

Exit codes:
    0  CLEAN / WARNING / INFO — fit for warn-only CI
    1  one or more BROKEN (block-severity) findings
    2  usage / data-file / repo not found
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
from _common import find_framework_root  # noqa: E402


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_SEV_RANK = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}


@dataclass
class Finding:
    node: str
    module: str
    kind: str
    severity: Severity
    message: str


@dataclass
class ModuleResult:
    name: str
    findings: list = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.findings:
            return "CLEAN"
        worst = max(_SEV_RANK[f.severity] for f in self.findings)
        if worst >= _SEV_RANK[Severity.HIGH]:
            return "BROKEN"
        if worst >= _SEV_RANK[Severity.MEDIUM]:
            return "WARNING"
        return "INFO"


@dataclass
class AuditState:
    started_at: str
    framework_root: str
    modules: dict = field(default_factory=dict)

    def overall_status(self) -> str:
        statuses = [m.status for m in self.modules.values()]
        if any(s == "BROKEN" for s in statuses):
            return "BROKEN"
        if any(s == "WARNING" for s in statuses):
            return "WARNING"
        if any(s == "INFO" for s in statuses):
            return "INFO"
        return "CLEAN"

    def all_findings(self) -> list:
        out = []
        for m in self.modules.values():
            out.extend(m.findings)
        return out


def load_modules(path: Path) -> list:
    if not path.is_file():
        raise RuntimeError(f"framework-modules data file missing at {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    mods = data.get("modules")
    if not isinstance(mods, list) or not mods:
        raise RuntimeError(f"{path} has no `modules` list")
    return mods


def _module_files(repo_root: Path, entry: dict) -> list:
    """Resolve the `files` field to existing Path objects. Missing files are silently skipped here;
    Node A reports them via a separate `path-not-found` finding when ALL declared files miss."""
    out = []
    for rel in entry.get("files", []):
        p = repo_root / rel
        if p.is_file():
            out.append(p)
    return out


def _module_exports(py_file: Path) -> set:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except Exception:
        return set()
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
    return names


def _module_imports(py_file: Path) -> list:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, None))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                out.append((mod, alias.name))
    return out


NETWORK_MODULES = {
    "socket", "http", "urllib", "requests", "httpx",
    "ftplib", "smtplib", "telnetlib", "websocket", "aiohttp",
}


ACCEPTED_NETWORK_IO = {
    "forge/tools/_classify_deviation.py": "Jira REST for deviation enrichment (top-level urllib import).",
    "forge/tools/_sprint_cleanup.py": "Jira REST for sprint-entry close polling (in-function urllib import).",
}


def node_a_check_exports(state, modules, repo_root):
    for entry in modules:
        name = entry["name"]
        result = state.modules[name]
        files = _module_files(repo_root, entry)
        if not files:
            result.findings.append(Finding(
                node="A", module=name, kind="path-not-found",
                severity=Severity.MEDIUM,
                message=f"Module path does not resolve: {entry.get('path', '?')}",
            ))
            continue
        file_symbols = {}
        for py in files:
            file_symbols[py.stem] = _module_exports(py)
        for export in entry.get("public_exports", []):
            if "." not in export:
                if not any(export in syms for syms in file_symbols.values()):
                    result.findings.append(Finding(
                        node="A", module=name, kind="export-symbol-not-found",
                        severity=Severity.LOW,
                        message=f"public_export '{export}' not found in module files",
                    ))
                continue
            file_stem, sym = export.split(".", 1)
            sym = sym.split(".")[0]
            if file_stem not in file_symbols:
                continue
            if sym not in file_symbols[file_stem]:
                result.findings.append(Finding(
                    node="A", module=name, kind="export-symbol-not-found",
                    severity=Severity.LOW,
                    message=f"public_export '{export}' not defined in {file_stem}.py",
                ))
    return state


def node_b_check_imports(state, modules, repo_root):
    stem_owner = {}
    for entry in modules:
        files = _module_files(repo_root, entry)
        if not files:
            continue
        for py in files:
            stem_owner[py.stem] = entry["name"]
    for entry in modules:
        name = entry["name"]
        allowed = set(entry.get("allowed_imports", []))
        result = state.modules[name]
        files = _module_files(repo_root, entry)
        if not files:
            continue
        seen = set()
        for py in files:
            for mod_name, _ in _module_imports(py):
                top = mod_name.split(".")[0] if mod_name else ""
                if not top:
                    continue
                owner = stem_owner.get(top)
                if owner is None or owner == name:
                    continue
                if owner not in allowed:
                    key = (py.name, owner, top)
                    if key in seen:
                        continue
                    seen.add(key)
                    result.findings.append(Finding(
                        node="B", module=name, kind="import-out-of-allowlist",
                        severity=Severity.MEDIUM,
                        message=f"{py.name} imports from {owner!r} (via `{top}`) not in allowed_imports",
                    ))
    return state


def node_c_check_network_io(state, modules, repo_root):
    for entry in modules:
        name = entry["name"]
        policy = entry.get("network_io_policy", "none")
        if policy in ("rest-allowlisted", "general"):
            continue
        result = state.modules[name]
        files = _module_files(repo_root, entry)
        if not files:
            continue
        seen = set()
        for py in files:
            rel = py.relative_to(repo_root).as_posix()
            if rel in ACCEPTED_NETWORK_IO:
                continue
            for mod_name, _ in _module_imports(py):
                top = mod_name.split(".")[0] if mod_name else ""
                if top in NETWORK_MODULES:
                    key = (py.name, top)
                    if key in seen:
                        continue
                    seen.add(key)
                    sev = Severity.MEDIUM if policy == "subprocess-only" else Severity.HIGH
                    result.findings.append(Finding(
                        node="C", module=name, kind="network-io-policy-violation",
                        severity=sev,
                        message=f"{py.name} imports `{top}` but module policy is {policy}",
                    ))
    return state


def node_d_check_cycles(state, modules, repo_root):
    graph = {m["name"]: list(m.get("allowed_imports", [])) for m in modules}
    visited = set()
    on_stack = set()
    cycles = []
    cur = []

    def dfs(node):
        if node in on_stack:
            i = cur.index(node)
            cycles.append(cur[i:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        on_stack.add(node)
        cur.append(node)
        for nxt in graph.get(node, []):
            dfs(nxt)
        cur.pop()
        on_stack.discard(node)

    for n in list(graph.keys()):
        dfs(n)

    for cycle in cycles:
        owner = cycle[0]
        if owner not in state.modules:
            continue
        state.modules[owner].findings.append(Finding(
            node="D", module=owner, kind="import-cycle",
            severity=Severity.HIGH,
            message=f"Import cycle detected: {' -> '.join(cycle)}",
        ))
    return state


PIPELINE = (node_a_check_exports, node_b_check_imports, node_c_check_network_io, node_d_check_cycles)


def run_audit(repo_root: Path, only_module: Optional[str] = None) -> AuditState:
    data_path = repo_root / "forge" / ".framework-modules.yml"
    modules = load_modules(data_path)
    if only_module is not None:
        modules = [m for m in modules if m["name"] == only_module]
        if not modules:
            raise RuntimeError(f"module {only_module!r} not declared in {data_path}")
    state = AuditState(
        started_at=datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        framework_root=str(repo_root),
        modules={m["name"]: ModuleResult(name=m["name"]) for m in modules},
    )
    for node in PIPELINE:
        state = node(state, modules, repo_root)
    return state


def render_report(state: AuditState) -> None:
    print("== Meta-Audit: framework-modules subsystem ==")
    print(f"   framework_root: {state.framework_root}")
    print(f"   started_at:     {state.started_at}\n")
    header = f"{'module':<28} {'findings':>8}  status"
    print(header)
    print("-" * len(header))
    for name, m in state.modules.items():
        print(f"{name:<28} {len(m.findings):>8}  {m.status}")
    findings = state.all_findings()
    if findings:
        print("\nFindings:")
        for f in findings:
            print(f"  [{f.severity.value}/Node {f.node}] {f.module}: {f.message}")
    overall = state.overall_status()
    exit_code = 1 if overall == "BROKEN" else 0
    print(f"\nOverall: {overall}  ->  exit {exit_code}")


def overall_verdict(state: AuditState) -> int:
    return 1 if state.overall_status() == "BROKEN" else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="meta-audit-framework-modules",
                                 description="Audit framework module boundaries (<TICKET-ID> framework release layer).")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--module", help="Audit a single module instead of all.")
    args = ap.parse_args(argv)

    repo_root = find_framework_root()
    if repo_root is None:
        print("ERROR: framework root not found", file=sys.stderr)
        return 2
    try:
        state = run_audit(repo_root, args.module)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "started_at": state.started_at,
            "overall": state.overall_status(),
            "modules": {
                name: {
                    "status": m.status,
                    "findings": [
                        {"node": f.node, "kind": f.kind, "severity": f.severity.value, "message": f.message}
                        for f in m.findings
                    ],
                }
                for name, m in state.modules.items()
            },
        }, indent=2))
    else:
        render_report(state)
    return overall_verdict(state)


if __name__ == "__main__":
    sys.exit(main())
