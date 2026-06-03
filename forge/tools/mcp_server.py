#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""mcp_server.py — Framework MCP server (framework release layer, <TICKET-ID>, Pilar 2.2 FINAL).

Exposes framework resources (workspace + standards) and tools (validate-artifact +
doctor + em-cli init) over MCP 2026-07-28 protocol via the anthropic mcp-sdk
FastMCP reference implementation.

Default transport: stdio (local-only, single-client-per-process). Operator
opts into network exposure via `em-cli serve-mcp --transport http`.

Strategy v2 must_fix #8: NO custom MCP from scratch; anthropic mcp-sdk only.

Subprocess delegation for tools keeps mcp_server.py decoupled from internal
Python APIs — any MCP client in any language can re-implement the wrappers.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    print(
        f"ERROR: missing dependency ({e.name}). "
        "Install with: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(2)


SERVER_NAME = "em-development-framework"
# forge/tools/mcp_server.py → forge/tools → forge → repo root
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_workspace_config() -> dict:
    """Load forge.config.yml from FRAMEWORK_ROOT. Fail-open: returns {} on absent/parse-error."""
    config_path = FRAMEWORK_ROOT / "forge.config.yml"
    if not config_path.is_file():
        return {}
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}


def _read_standards_file(custom_standards_key: str) -> str:
    """Read a standards file pointed to by config['custom_standards'][key]. Empty string if missing."""
    config = _read_workspace_config()
    rel = (config.get("custom_standards") or {}).get(custom_standards_key)
    if not rel:
        return ""
    path = FRAMEWORK_ROOT / rel
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _run_subprocess(args: list, cwd: Optional[str] = None) -> dict:
    """Run a subprocess + return structured dict. Timeout: 120s. Internal helper for MCP tool delegates."""
    try:
        r = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {
            "rc": -1, "stdout": "", "stderr": "subprocess timeout (120s)",
            "valid": False, "healthy": False, "config_path": None,
        }
    return {
        "rc": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
        "valid": r.returncode == 0,
        "healthy": r.returncode == 0,
        "config_path": _parse_init_config_path(r.stdout),
    }


def _parse_init_config_path(stdout: str) -> Optional[str]:
    """Best-effort: extract the forge.config.yml path from em-cli init stdout."""
    for line in stdout.splitlines():
        if "forge.config.yml" in line and any(tok in line for tok in ("WROTE", "Created", "wrote")):
            for token in line.split():
                if token.endswith("forge.config.yml"):
                    return token
    return None


def build_server() -> FastMCP:
    """Build the FastMCP server with resources + tools registered.

    Factored out for test introspection: tests can call build_server() without
    actually running the transport.
    """
    mcp = FastMCP(SERVER_NAME)

    # ---------- Resources (read-only) ----------

    @mcp.resource("forge://workspace/config")
    def workspace_config() -> str:
        """Current forge.config.yml contents as JSON."""
        return json.dumps(_read_workspace_config(), indent=2, sort_keys=True)

    @mcp.resource("forge://standards/workflow")
    def standards_workflow() -> str:
        """Workflow standards file content (from forge.config.yml custom_standards.workflow)."""
        return _read_standards_file("workflow")

    @mcp.resource("forge://standards/audit")
    def standards_audit() -> str:
        """Audit standards file content (from forge.config.yml custom_standards.audit)."""
        return _read_standards_file("audit")

    # ---------- Tools (callable, side-effecting) ----------

    @mcp.tool()
    def validate_artifact(path: str) -> dict:
        """Validate a lifecycle artifact against its schema.

        Delegates to forge/tools/validate-artifact.py via subprocess. Any client
        in any language can re-implement this wrapper; we keep the protocol surface
        decoupled from internal Python APIs.

        Args:
            path: absolute or repo-relative path to artifact (plan / verify / record / state).

        Returns:
            {rc: int, stdout: str, stderr: str, valid: bool}
        """
        return _run_subprocess([
            sys.executable,
            str(FRAMEWORK_ROOT / "forge" / "tools" / "validate-artifact.py"),
            path,
        ])

    @mcp.tool()
    def doctor(
        check_groundedness: bool = False,
        check_hook: bool = False,
        check_gateway: bool = False,
    ) -> dict:
        """Audit forge.config.yml ↔ filesystem coherence.

        Delegates to em-cli doctor.

        Args:
            check_groundedness: also run anti-rot baseline check.
            check_hook: verify pre-commit-grd002a hook installation.
            check_gateway: warn if any gateway artifact is stale vs forge.config.yml.

        Returns:
            {rc: int, stdout: str, stderr: str, healthy: bool}
        """
        args = [
            sys.executable,
            str(FRAMEWORK_ROOT / "forge" / "tools" / "em-cli.py"),
            "doctor",
        ]
        if check_groundedness:
            args.append("--check-groundedness")
        if check_hook:
            args.append("--check-hook")
        if check_gateway:
            args.append("--check-gateway")
        return _run_subprocess(args)

    @mcp.tool()
    def em_cli_init(
        product_name: str,
        language: str,
        framework: str,
        backend_root: str = "null",
        frontend_root: str = "null",
        target: Optional[str] = None,
    ) -> dict:
        """Scaffold framework into a target repo (greenfield mode).

        Delegates to em-cli init --mode=greenfield --non-interactive.

        Args:
            product_name: slug (lowercase, alphanumeric + hyphens).
            language: typescript | python | go | rust | java | ruby | kotlin | swift | mixed.
            framework: stack framework label (free-form).
            backend_root: relative path or 'null'.
            frontend_root: relative path or 'null'.
            target: absolute target dir (default: cwd). MCP clients should supply this explicitly.

        Returns:
            {rc: int, stdout: str, stderr: str, config_path: str | None}
        """
        args = [
            sys.executable,
            str(FRAMEWORK_ROOT / "forge" / "tools" / "em-cli.py"),
            "init", "--mode=greenfield", "--non-interactive",
            f"--product-name={product_name}",
            f"--language={language}",
            f"--framework={framework}",
            f"--backend-root={backend_root}",
            f"--frontend-root={frontend_root}",
        ]
        return _run_subprocess(args, cwd=target)

    return mcp


def main(argv: Optional[list] = None) -> int:
    """Entry point for direct invocation. Default transport: stdio (local-only).

    Stdio transport: a single MCP client connects via the calling process's
    stdin/stdout. Stdout is RESERVED for MCP protocol messages — any other
    output to stdout breaks the protocol. Library-internal logging is handled
    by FastMCP and routed to stderr.

    Streamable-HTTP transport (opt-in): operator explicitly passes --transport http.
    MCP 2026-07-28 spec mandates stateless core (FastMCP default) + OAuth/OIDC
    auth — auth is deferred to the operator's config (no default provider shipped).
    """
    ap = argparse.ArgumentParser(
        prog="mcp_server",
        description=f"{SERVER_NAME} MCP server (framework release layer <TICKET-ID>)",
    )
    ap.add_argument(
        "--transport", choices=["stdio", "http"], default="stdio",
        help="Transport (default: stdio = local-only, single-client-per-process)",
    )
    ap.add_argument(
        "--port", type=int, default=8765,
        help="Port for streamable-http transport (default: 8765; ignored for stdio)",
    )
    args = ap.parse_args(argv)

    mcp = build_server()
    if args.transport == "stdio":
        mcp.run()  # stdio default
    elif args.transport == "http":
        mcp.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    sys.exit(main())
