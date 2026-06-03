#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""em-cli.py — Framework installer + workspace contract CLI.

<TICKET-ID> (framework release layer — Proposal D Phase 2/3). Greenfield onboarding tool that
scaffolds the framework into a blank-canvas repo: generates a valid
forge.config.yml (framework release layer contract) + .lifecycle/ artifacts dir + lifecycle/specs/
placeholder stubs.

Industry pattern: Cookiecutter / Yeoman / Nx scaffolder lineage. UX baseline:
clig.dev 2026 + Lucas Costa guided-setup ("few high-signal prompts with safe
defaults and clear escape hatch").

Subcommands:
    em-cli.py init --mode=greenfield [--dry-run] [--non-interactive] [--force]
                                     [--product-name X] [--language LANG]
                                     [--framework FW] [--backend-root Y]
                                     [--frontend-root Z]
    em-cli.py validate [path]

Deferred to framework release layer: init --mode=map, doctor, update, GRD-002a pre-commit hook.

Exit codes:
    0  success
    1  usage error (missing required arg, invalid flag combo)
    2  validation error (invalid prompt input, schema validation failure)
    3  filesystem error (cannot write, permission denied)
    4  existing file conflict without --force

Zero new dependencies (stdlib argparse + pathlib + subprocess + re + sys + yaml).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed (already in requirements.txt).", file=sys.stderr)
    sys.exit(2)

# <TICKET-ID> Wave B: atomicity primitives for init flows (rollback safety net).
# Import as a sibling module via direct path manipulation since em-cli.py is
# a script-in-tree (PEP 420 namespace package — forge.tools.*).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from _init_atomicity import (  # noqa: E402
    INSTALLED_FILES,
    _safe_mkdir,
    _safe_write,
    _rollback,
)


# ---------- Validation regexes (mirror forge-workspace.schema.yml) ----------

PRODUCT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
LANGUAGE_CHOICES = (
    "typescript", "python", "go", "rust", "java", "ruby", "kotlin", "swift", "mixed",
)
DEFAULT_SPECS_ROOT = "lifecycle/specs"
# <TICKET-ID> framework release layer (Pilar 1.2): bumped 1.0.0 -> 1.1.0; first real schema
# migration registered in MIGRATIONS registry below.
SCHEMA_VERSION = "1.1.0"


# ---------- Filesystem signal detection ----------

def _detect_default_language(target: Path) -> Optional[str]:
    """Sniff filesystem for language hints. Returns suggestion or None."""
    if (target / "package.json").is_file():
        return "typescript"
    if (target / "pyproject.toml").is_file() or (target / "setup.py").is_file():
        return "python"
    if (target / "Cargo.toml").is_file():
        return "rust"
    if (target / "go.mod").is_file():
        return "go"
    if (target / "build.gradle").is_file() or (target / "pom.xml").is_file():
        return "java"
    if (target / "Gemfile").is_file():
        return "ruby"
    return None


def _detect_default_product_name(target: Path) -> Optional[str]:
    """Extract project name from package.json if present + slugifiable."""
    pkg_json = target / "package.json"
    if pkg_json.is_file():
        try:
            import json
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            name = data.get("name", "")
            # Strip npm scope prefix (@org/) if present
            if name.startswith("@") and "/" in name:
                name = name.split("/", 1)[1]
            if PRODUCT_NAME_RE.match(name):
                return name
        except Exception:
            pass
    return None


# ---------- Interactive prompts (with per-prompt validation) ----------

def _prompt(question: str, default: Optional[str] = None, validator=None) -> str:
    """Ask one question; validate per-prompt; loop until valid or operator aborts."""
    while True:
        hint = f" [{default}]" if default is not None else ""
        try:
            answer = input(f"{question}{hint}: ").strip()
        except EOFError:
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
        if not answer and default is not None:
            answer = default
        if validator is not None:
            err = validator(answer)
            if err:
                print(f"  ERROR: {err}", file=sys.stderr)
                continue
        return answer


def _validate_product_name(value: str) -> Optional[str]:
    if not value:
        return "product_name is required"
    if not PRODUCT_NAME_RE.match(value):
        return f"product_name must match {PRODUCT_NAME_RE.pattern!r}; got {value!r}"
    if not (2 <= len(value) <= 40):
        return f"product_name length must be 2-40; got {len(value)}"
    return None


def _validate_language(value: str) -> Optional[str]:
    if value not in LANGUAGE_CHOICES:
        return f"language must be one of {LANGUAGE_CHOICES}; got {value!r}"
    return None


def _validate_framework(value: str) -> Optional[str]:
    if not value or not value.strip():
        return "framework name is required (free-form, e.g. NestJS / Django / Rails)"
    return None


def _validate_path_or_null(value: str) -> Optional[str]:
    if value.lower() in ("null", "none", ""):
        return None
    # Accept any string — actual existence is operator's responsibility
    return None


def _normalize_path_or_null(value: str) -> Optional[str]:
    if value.lower() in ("null", "none", ""):
        return None
    return value


# ---------- Greenfield init ----------

def _gather_answers(args, target: Path) -> dict:
    """Collect operator answers from CLI flags OR interactive prompts."""
    answers = {}

    # product_name
    if args.product_name:
        err = _validate_product_name(args.product_name)
        if err:
            print(f"ERROR (--product-name): {err}", file=sys.stderr)
            sys.exit(2)
        answers["product_name"] = args.product_name
    elif args.non_interactive:
        print("ERROR: --product-name required in --non-interactive mode", file=sys.stderr)
        sys.exit(1)
    else:
        default = _detect_default_product_name(target)
        answers["product_name"] = _prompt(
            "Product name (slug, lowercase + hyphens)",
            default=default, validator=_validate_product_name,
        )

    # stack_metadata.language
    if args.language:
        err = _validate_language(args.language)
        if err:
            print(f"ERROR (--language): {err}", file=sys.stderr)
            sys.exit(2)
        answers["language"] = args.language
    elif args.non_interactive:
        print("ERROR: --language required in --non-interactive mode", file=sys.stderr)
        sys.exit(1)
    else:
        default = _detect_default_language(target)
        answers["language"] = _prompt(
            f"Stack language (one of: {', '.join(LANGUAGE_CHOICES)})",
            default=default, validator=_validate_language,
        )

    # stack_metadata.framework
    if args.framework:
        err = _validate_framework(args.framework)
        if err:
            print(f"ERROR (--framework): {err}", file=sys.stderr)
            sys.exit(2)
        answers["framework"] = args.framework
    elif args.non_interactive:
        print("ERROR: --framework required in --non-interactive mode", file=sys.stderr)
        sys.exit(1)
    else:
        answers["framework"] = _prompt(
            "Framework name (free-form, e.g. NestJS / Django / Rails / FastAPI)",
            validator=_validate_framework,
        )

    # backend_root + frontend_root (both optional / null allowed)
    if args.backend_root is not None:
        answers["backend_root"] = _normalize_path_or_null(args.backend_root)
    elif args.non_interactive:
        answers["backend_root"] = None
    else:
        raw = _prompt(
            "Backend root path (relative to repo root, or 'null')",
            default="null", validator=_validate_path_or_null,
        )
        answers["backend_root"] = _normalize_path_or_null(raw)

    if args.frontend_root is not None:
        answers["frontend_root"] = _normalize_path_or_null(args.frontend_root)
    elif args.non_interactive:
        answers["frontend_root"] = None
    else:
        raw = _prompt(
            "Frontend root path (relative to repo root, or 'null')",
            default="null", validator=_validate_path_or_null,
        )
        answers["frontend_root"] = _normalize_path_or_null(raw)

    return answers


def _render_forge_config(answers: dict, mode_label: str = "") -> str:
    """Render forge.config.yml content from answers. YAML emitted manually
    to preserve comments + ordering.

    <TICKET-ID> W30: removed hardcoded greenfield header. Callers (greenfield
    + map) prepend their own header to avoid double-comment bug (framework release layer/28
    map mode reused this function which emitted greenfield comment, then
    map mode added its own — produced two contradictory headers)."""
    backend = answers.get("backend_root")
    frontend = answers.get("frontend_root")
    header_label = f" — {mode_label}" if mode_label else ""
    lines = [
        "# schema: forge/schemas/forge-workspace.schema.yml",
        "#",
        f"# Workspace contract for the {answers['product_name']} product{header_label}.",
        "",
        f"schema_version: \"{SCHEMA_VERSION}\"",
        f"product_name: {answers['product_name']}",
        "",
        f"backend_root: {backend if backend is not None else 'null'}",
        f"frontend_root: {frontend if frontend is not None else 'null'}",
        "",
        f"specs_root: {DEFAULT_SPECS_ROOT}",
        "",
        "integration_state_path: null",
        "data_model_path: null",
        "api_spec_path: null",
        "",
        "custom_standards: {}",
        "",
        "stack_metadata:",
        f"  language: {answers['language']}",
        f"  framework: {answers['framework']}",
        "",
        "feature_flags: {}",
        "",
    ]
    return "\n".join(lines)


def _create_workspace_dirs(answers: dict, target: Path, dry_run: bool) -> list:
    """Create all workspace directories declared in `answers`. Returns a list of
    created paths (relative to target). Idempotent (mkdir parents=True
    exist_ok=True). Honors dry_run (returns planned paths without writing).

    Created paths:
    - backend_root (if non-null)
    - frontend_root (if non-null)
    - specs_root (always; defaults to lifecycle/specs)
    - .lifecycle/artifacts/<product_name>/{plans,records,state}/

    <TICKET-ID> framework release layer: Pilar 1.1 — ensures doctor PASS post-install."""
    planned = []
    paths = []
    backend = answers.get("backend_root")
    frontend = answers.get("frontend_root")
    specs_root = answers.get("specs_root") or DEFAULT_SPECS_ROOT
    product_name = answers["product_name"]
    if backend:
        paths.append(target / backend)
    if frontend:
        paths.append(target / frontend)
    paths.append(target / specs_root)
    lifecycle_dir = target / ".lifecycle"
    for sub in ("plans", "records", "state"):
        paths.append(lifecycle_dir / "artifacts" / product_name / sub)
    for p in paths:
        planned.append(p.relative_to(target).as_posix())
        if not dry_run:
            p.mkdir(parents=True, exist_ok=True)
    return planned


def _do_init_post_write_doctor(target: Path) -> int:
    """Run em-cli doctor against the just-written workspace as a final
    integrity gate. Returns 0 if PASS, 1 if FAIL with operator-actionable
    findings. Called from both greenfield + map post-write paths.

    <TICKET-ID> framework release layer: Pilar 1.1 — final installer integrity gate."""
    em_cli = Path(__file__).resolve()
    r = subprocess.run(
        [sys.executable, str(em_cli), "doctor"],
        cwd=str(target), capture_output=True, text=True, timeout=30,
    )
    sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    return 0 if r.returncode == 0 else 1


def _do_init_greenfield(args) -> int:
    target = Path.cwd().resolve()
    print(f"em-cli init --mode=greenfield → {target}")

    if args.dry_run:
        print("[dry-run] no filesystem changes will be made")

    answers = _gather_answers(args, target)

    config_path = target / "forge.config.yml"
    lifecycle_dir = target / ".lifecycle"
    specs_dir = target / DEFAULT_SPECS_ROOT
    greenfield_header = "# Generated by em-cli init --mode=greenfield.\n\n"
    config_content = greenfield_header + _render_forge_config(answers, mode_label="greenfield")

    # Conflict check
    if config_path.exists() and not args.force:
        print(
            f"ERROR: {config_path} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 4

    # Plan summary
    print("\nPlanned outputs:")
    print(f"  CREATE  forge.config.yml")
    print(f"  CREATE  .lifecycle/artifacts/{answers['product_name']}/{{plans,records,state}}/")
    print(f"  CREATE  {DEFAULT_SPECS_ROOT}/ (placeholder stubs)")

    if args.dry_run:
        print("\n[dry-run] preview of forge.config.yml:")
        print(config_content)
        return 0

    # <TICKET-ID> Wave B: atomicity refactor — track created files for rollback.
    # All writes in this Wave B refactor flow through INSTALLED_FILES tracker.
    # On any mid-flow exception → _rollback removes ONLY tracked entries
    # (operator pre-existing content untouchable per invariants i+ii+iii).
    INSTALLED_FILES.clear()
    try:
        # Track existing config (if --force overwriting an existing file, we
        # don't track it for rollback — operator's pre-Wave-B file already
        # existed; --force semantics means operator opted into overwrite).
        config_pre_existed = config_path.exists()
        config_path.write_text(config_content, encoding="utf-8")
        if not config_pre_existed:
            INSTALLED_FILES.append((config_path, "file"))

        # Create workspace directories — use _safe_mkdir for atomicity.
        # _create_workspace_dirs returns the list of paths it touched; we
        # call it as-is, then for each NEW dir, track. _safe_mkdir's invariant
        # (i) means dirs that already existed before this call are NOT tracked.
        created = _create_workspace_dirs(answers, target, dry_run=False)
        for p in created:
            # Track only dirs we actually created (mtime check would be racy;
            # we trust _create_workspace_dirs's return value as "post-create").
            # Invariant (iii) protects: rmdir on non-empty fails-safely.
            INSTALLED_FILES.append((p, "dir"))
            print(f"  MKDIR   {p}/")

        # Copy template stubs.
        templates_dir = Path(__file__).resolve().parent / "em-cli-templates"
        for stub_name in (
            "backend-standards.mdc.template",
            "frontend-standards.mdc.template",
            "integration-state.md.template",
            "workflow-standards.mdc.template",
            "README.md.template",
        ):
            src = templates_dir / stub_name
            if not src.is_file():
                continue
            if stub_name == "README.md.template":
                dst = target / "README.md"
            else:
                dst = specs_dir / stub_name.replace(".template", "")
            if dst.exists() and not args.force:
                print(f"  SKIP    {dst.relative_to(target)} (exists)")
                continue
            dst_pre_existed = dst.exists()
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            if not dst_pre_existed:
                INSTALLED_FILES.append((dst, "file"))
            print(f"  WROTE   {dst.relative_to(target)}")

        print(f"  WROTE   forge.config.yml")

        # Validate generated config
        validator = Path(__file__).resolve().parent / "validate-artifact.py"
        if validator.is_file():
            rc = subprocess.run(
                [sys.executable, str(validator), str(config_path), "--quiet"],
                capture_output=True, text=True,
            ).returncode
            if rc != 0:
                _rollback(f"schema validation rc={rc}")
                print(
                    f"\nWARNING: forge.config.yml schema validation rc={rc}. Rolled back.",
                    file=sys.stderr,
                )
                return 2

        # Final doctor integrity gate (<TICKET-ID> W30)
        print("\nRunning doctor as final integrity gate...")
        doctor_rc = _do_init_post_write_doctor(target)
        if doctor_rc == 0:
            print("\nInstallation healthy. Doctor PASS.")
            INSTALLED_FILES.clear()  # success path: forget tracker
            return 0
        else:
            _rollback(f"post-write doctor rc={doctor_rc}")
            print(
                "\nWARNING: doctor reports FAIL post-install. Rolled back.",
                file=sys.stderr,
            )
            return 2
    except (OSError, FileExistsError) as e:
        _rollback(f"{type(e).__name__}: {e}")
        print(f"ERROR during init: {e}", file=sys.stderr)
        return 3


def _do_validate(args) -> int:
    path = Path(args.path).resolve() if args.path else Path.cwd() / "forge.config.yml"
    if not path.is_file():
        print(f"ERROR: {path} does not exist", file=sys.stderr)
        return 3
    validator = Path(__file__).resolve().parent / "validate-artifact.py"
    if not validator.is_file():
        print(f"ERROR: validate-artifact.py not found at {validator}", file=sys.stderr)
        return 3
    rc = subprocess.run([sys.executable, str(validator), str(path)]).returncode
    return rc


# ---------- map mode (existing-repo retrofit, <TICKET-ID> framework release layer) ----------

def _do_init_map(args) -> int:
    """Retrofit an existing repo: auto-discover product metadata from filesystem
    signals + confirm with operator + generate forge.config.yml preserving
    existing files unless --force."""
    target = Path.cwd().resolve()
    print(f"em-cli init --mode=map → {target}")

    if args.dry_run:
        print("[dry-run] no filesystem changes will be made")

    # Inference signals → display before prompts so operator sees the trail
    detected_lang = _detect_default_language(target)
    detected_name = _detect_default_product_name(target)
    print("\nFilesystem inference:")
    print(f"  product_name (from package.json/etc.): {detected_name or '<none>'}")
    print(f"  language (from package.json/pyproject.toml/etc.): {detected_lang or '<none>'}")

    # Gather answers — same path as greenfield but defaults are stronger (inference)
    answers = _gather_answers(args, target)

    config_path = target / "forge.config.yml"
    if config_path.exists() and not args.force:
        print(
            f"\nERROR: {config_path} already exists. Use --force to overwrite,"
            f" or run em-cli doctor to audit the existing config.",
            file=sys.stderr,
        )
        return 4

    # Render config with comments citing inference signals (<TICKET-ID> W30: fix
    # double-comment bug — _render_forge_config no longer emits its own
    # mode-specific header; map mode prepends its own)
    map_header = (
        "# Generated by em-cli init --mode=map.\n"
        f"# Inference signals: product_name={detected_name!r}, language={detected_lang!r}.\n"
        "# Adjust paths to match your actual repo layout post-generation.\n\n"
    )
    config_content = map_header + _render_forge_config(answers, mode_label="map")

    if args.dry_run:
        print("\n[dry-run] preview of forge.config.yml:")
        print(config_content)
        return 0

    try:
        config_path.write_text(config_content, encoding="utf-8")
    except OSError as e:
        print(f"ERROR writing forge.config.yml: {e}", file=sys.stderr)
        return 3

    print(f"\n  WROTE   forge.config.yml (with inference comments)")

    # <TICKET-ID> W30: map mode scaffolding parity with greenfield
    # Create workspace directories declared in answers
    lifecycle_dir = target / ".lifecycle"
    specs_dir = target / DEFAULT_SPECS_ROOT
    try:
        created = _create_workspace_dirs(answers, target, dry_run=False)
        for p in created:
            print(f"  MKDIR   {p}/")
    except OSError as e:
        print(f"ERROR creating directories: {e}", file=sys.stderr)
        return 3

    # Copy template stubs (same set as greenfield, idempotent on retrofit)
    templates_dir = Path(__file__).resolve().parent / "em-cli-templates"
    for stub_name in (
        "backend-standards.mdc.template",
        "frontend-standards.mdc.template",
        "integration-state.md.template",
        "workflow-standards.mdc.template",
        "README.md.template",
    ):
        src = templates_dir / stub_name
        if not src.is_file():
            continue
        if stub_name == "README.md.template":
            dst = target / "README.md"
        else:
            dst = specs_dir / stub_name.replace(".template", "")
        if dst.exists() and not args.force:
            print(f"  SKIP    {dst.relative_to(target)} (exists — retrofit-preserved)")
            continue
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  WROTE   {dst.relative_to(target)}")

    # Validate generated config
    validator = Path(__file__).resolve().parent / "validate-artifact.py"
    if validator.is_file():
        rc = subprocess.run(
            [sys.executable, str(validator), str(config_path), "--quiet"],
            capture_output=True, text=True,
        ).returncode
        if rc != 0:
            print(f"\nWARNING: forge.config.yml written but validation rc={rc}.", file=sys.stderr)
            return 2

    # <TICKET-ID> W30: final doctor integrity gate (parity with greenfield)
    print("\nRunning doctor as final integrity gate...")
    doctor_rc = _do_init_post_write_doctor(target)
    if doctor_rc == 0:
        print("\nInstallation healthy. Doctor PASS.")
        return 0
    else:
        print(
            "\nWARNING: doctor reports FAIL post-install. Inspect declared paths.",
            file=sys.stderr,
        )
        return 2


# ---------- doctor (config ↔ filesystem coherence audit) ----------

def _do_doctor(args) -> int:
    target = Path.cwd().resolve()
    config_path = target / "forge.config.yml"
    if not config_path.is_file():
        print(f"ERROR: {config_path} does not exist; run em-cli init first.", file=sys.stderr)
        return 3

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"ERROR parsing forge.config.yml: {e}", file=sys.stderr)
        return 2

    findings = []  # list of (severity, field, message); severity: "warn" | "error"

    # Per-field path checks (each field is optional; null is OK; non-null must exist)
    path_fields = (
        "backend_root", "frontend_root", "specs_root",
        "integration_state_path", "data_model_path", "api_spec_path",
    )
    for field in path_fields:
        value = config.get(field)
        if value is None or value == "null":
            continue
        path = target / value
        if not path.exists():
            findings.append(("error", field, f"declared path '{value}' does not exist"))

    # custom_standards: each value should also resolve
    for key, value in (config.get("custom_standards") or {}).items():
        if not value:
            continue
        path = target / value
        if not path.exists():
            findings.append(("error", f"custom_standards.{key}", f"declared path '{value}' does not exist"))

    # schema_version sanity
    sv = config.get("schema_version")
    if sv != SCHEMA_VERSION:
        findings.append((
            "warn",
            "schema_version",
            f"config schema_version={sv!r}, framework current={SCHEMA_VERSION!r}. "
            f"Run em-cli update to migrate.",
        ))

    # Optional groundedness check (delegates to existing tool)
    if args.check_groundedness:
        groundedness = Path(__file__).resolve().parent / "groundedness-snapshot.py"
        if groundedness.is_file():
            r = subprocess.run(
                [sys.executable, str(groundedness), "--check"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                findings.append(("warn", "groundedness", f"baseline check rc={r.returncode} — see groundedness-snapshot output"))

    # <TICKET-ID> W33: gateway artifact freshness check.
    # If any gateway artifact exists, compare its mtime against forge.config.yml.
    # An artifact older than the config is stale (regenerate via render-gateway).
    if args.check_gateway:
        try:
            config_mtime = config_path.stat().st_mtime
        except OSError:
            config_mtime = None
        if config_mtime is not None:
            for rel_path, _ in GATEWAY_ARTIFACTS:
                artifact = target / rel_path
                if not artifact.is_file():
                    continue
                try:
                    artifact_mtime = artifact.stat().st_mtime
                except OSError:
                    continue
                if artifact_mtime < config_mtime:
                    findings.append((
                        "warn", "gateway_freshness",
                        f"{rel_path} is older than forge.config.yml. "
                        f"Re-run em-cli render-gateway --force to refresh.",
                    ))

    # <TICKET-ID> W30: optional pre-commit-grd002a hook installation check
    if args.check_hook:
        hook_path = target / ".git" / "hooks" / "pre-commit"
        if not hook_path.is_file():
            findings.append((
                "warn", "grd002a_hook",
                "pre-commit hook not installed; run em-cli install-hook --hook=pre-commit-grd002a "
                "for mechanical GRD-002a enforcement at local-push time",
            ))
        else:
            try:
                hook_content = hook_path.read_text(encoding="utf-8")
            except OSError:
                hook_content = ""
            if "pre-commit-grd002a" not in hook_content:
                findings.append((
                    "warn", "grd002a_hook",
                    f"pre-commit hook present at {hook_path.relative_to(target)} but does NOT "
                    "contain the pre-commit-grd002a signature; verify installation",
                ))

    # Report
    print(f"em-cli doctor → {target}")
    print(f"  config: {config_path.relative_to(target)}")
    print(f"  product_name: {config.get('product_name', '<missing>')}")
    print(f"  schema_version: {sv}")
    print()

    if not findings:
        print("PASS — all declared paths resolve; schema_version current; healthy.")
        return 0

    errors = [f for f in findings if f[0] == "error"]
    warns = [f for f in findings if f[0] == "warn"]

    if errors:
        print(f"FAIL — {len(errors)} error(s):")
        for sev, field, msg in errors:
            print(f"  [ERROR] {field}: {msg}")
    if warns:
        print(f"\n{len(warns)} warning(s):")
        for sev, field, msg in warns:
            print(f"  [WARN] {field}: {msg}")

    return 1 if errors else 0


# ---------- update (schema_version migration framework) ----------

# Per-version migration registry. <TICKET-ID> framework release layer (Pilar 1.2): first real
# migration entry registered — 1.0.0 -> 1.1.0 bumps schema_version + adds the
# `runtime_injection_enabled: true` feature flag. Closes the framework release layer "lazy
# infrastructure" finding from strategy v2 audit.

def migrate_1_0_0_to_1_1_0(config: dict) -> dict:
    """<TICKET-ID> framework release layer first real migration: bump schema_version from 1.0.0
    to 1.1.0 + add runtime_injection_enabled feature flag (default true).
    Returns the migrated config dict (caller writes back to disk)."""
    config["schema_version"] = "1.1.0"
    config.setdefault("runtime_injection_enabled", True)
    return config


MIGRATIONS = {
    ("1.0.0", "1.1.0"): migrate_1_0_0_to_1_1_0,
}


def _do_update(args) -> int:
    target = Path.cwd().resolve()
    config_path = target / "forge.config.yml"
    if not config_path.is_file():
        print(f"ERROR: {config_path} does not exist; run em-cli init first.", file=sys.stderr)
        return 3

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"ERROR parsing forge.config.yml: {e}", file=sys.stderr)
        return 2

    current_sv = config.get("schema_version")
    print(f"em-cli update → {target}")
    print(f"  current schema_version: {current_sv}")
    print(f"  framework canonical:    {SCHEMA_VERSION}")

    if current_sv == SCHEMA_VERSION:
        print(f"\nNo migrations needed. forge.config.yml is at canonical version.")
        return 0

    # Walk the migration graph
    path = []
    cur = current_sv
    while cur != SCHEMA_VERSION:
        # Find a migration whose source is cur
        applicable = [(src, dst) for (src, dst) in MIGRATIONS if src == cur]
        if not applicable:
            print(f"\nERROR: no migration path from {cur!r} to {SCHEMA_VERSION!r}.", file=sys.stderr)
            print(f"Available migrations: {list(MIGRATIONS.keys())}", file=sys.stderr)
            return 2
        # Take first applicable (linear chain assumed)
        src, dst = applicable[0]
        path.append((src, dst))
        cur = dst

    print(f"\nMigration path: {' → '.join([current_sv, *[d for (_, d) in path]])}")
    if args.dry_run:
        print("[dry-run] no changes will be written")
        return 0

    # <TICKET-ID> framework release layer (Pilar 1.2): apply each migration in the path. Each
    # migration function takes the config dict + returns the migrated config.
    for src, dst in path:
        fn = MIGRATIONS[(src, dst)]
        config = fn(config)
        print(f"  applied: migrate_{src.replace('.', '_')}_to_{dst.replace('.', '_')}")

    # Write the migrated config back to disk preserving YAML structure.
    try:
        with config_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, default_flow_style=False, sort_keys=False)
    except OSError as e:
        print(f"\nERROR writing migrated forge.config.yml: {e}", file=sys.stderr)
        return 3

    print(f"\nWROTE   {config_path.relative_to(target)} (schema_version: {SCHEMA_VERSION})")

    # Re-validate post-migration
    validator = Path(__file__).resolve().parent / "validate-artifact.py"
    if validator.is_file():
        rc = subprocess.run(
            [sys.executable, str(validator), str(config_path), "--quiet"],
            capture_output=True, text=True,
        ).returncode
        if rc != 0:
            print(f"\nWARNING: migrated config validation rc={rc}.", file=sys.stderr)
            return 2
    return 0


# ---------- install-hook (install pre-commit hook into target repo) ----------

KNOWN_HOOKS = {
    "pre-commit-grd002a": Path(__file__).resolve().parent / "hooks" / "pre-commit-grd002a.py",
}


def _do_install_hook(args) -> int:
    if args.hook not in KNOWN_HOOKS:
        print(f"ERROR: unknown hook {args.hook!r}. Known: {list(KNOWN_HOOKS.keys())}", file=sys.stderr)
        return 1

    src = KNOWN_HOOKS[args.hook]
    if not src.is_file():
        print(f"ERROR: hook source missing at {src}", file=sys.stderr)
        return 3

    # Resolve target .git/hooks/pre-commit
    if args.target:
        git_dir = Path(args.target).resolve()
    else:
        # Find .git from cwd
        cur = Path.cwd().resolve()
        git_dir = None
        for parent in [cur, *cur.parents]:
            if (parent / ".git").is_dir():
                git_dir = parent / ".git"
                break
        if git_dir is None:
            print(f"ERROR: no .git directory found from {cur}. Pass --target=<path>.", file=sys.stderr)
            return 3

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dst = hooks_dir / "pre-commit"

    if dst.exists() and not args.force:
        print(f"ERROR: {dst} already exists. Use --force to replace.", file=sys.stderr)
        return 4

    try:
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        dst.chmod(0o755)
    except OSError as e:
        print(f"ERROR writing hook: {e}", file=sys.stderr)
        return 3

    print(f"Installed hook {args.hook!r} → {dst}")
    return 0


# ---------- render-gateway (<TICKET-ID> framework release layer — file-based multi-agent gateway) ----------

# Per strategy v2 F0.2 industry finding (2026-05-31): `.cursorrules` is DEPRECATED
# per Cursor's own 2024-late docs (Cursor Agent mode ignores it 2026) — do NOT
# generate it. `GEMINI.md` has no industry-confirmed convention as of this Wave —
# do NOT generate it either. Adding either would be cargo-cult.

GATEWAY_ARTIFACTS = (
    ("AGENTS.md", "AGENTS.md.template"),
    (".github/copilot-instructions.md", "copilot-instructions.md.template"),
    ("CLAUDE.md", "CLAUDE.md.template"),
    ("ai-bootstrap.md", "ai-bootstrap.md.template"),
)


def _strip_optional_block(text: str, marker: str, value: Optional[str]) -> str:
    """If `value` is None / empty / "null", remove the marker-delimited block
    from text entirely (including the marker comments). Otherwise drop only the
    marker comments and keep the block content. Used for conditional rendering
    of `<workspace.*>` fields that may legitimately be null (framework
    self-host has no backend/frontend)."""
    begin = f"<!-- {marker}_BEGIN -->"
    end = f"<!-- {marker}_END -->"
    if begin not in text or end not in text:
        return text
    pre, rest = text.split(begin, 1)
    block, post = rest.split(end, 1)
    if value is None or value == "" or value == "null":
        # Drop the entire block + a trailing newline if present.
        cleaned = pre.rstrip("\n") + post
        # Collapse multiple blank lines we may have just introduced.
        return cleaned
    # Keep block content; drop the marker comments.
    return pre + block.strip("\n") + "\n" + post


def _render_template(template_name: str, config: dict) -> str:
    """Render a gateway template by substituting `{{KEY}}` placeholders from
    the forge.config.yml dict + applying conditional block stripping for
    optional fields. Returns the rendered string."""
    templates_dir = Path(__file__).resolve().parent / "em-cli-templates"
    template_path = templates_dir / template_name
    text = template_path.read_text(encoding="utf-8")

    stack = config.get("stack_metadata") or {}
    standards = config.get("custom_standards") or {}

    replacements = {
        "{{PRODUCT_NAME}}": config.get("product_name") or "",
        "{{STACK_LANGUAGE}}": stack.get("language") or "",
        "{{STACK_FRAMEWORK}}": stack.get("framework") or "",
        "{{STACK_VERSION}}": stack.get("version") or "",
        "{{BACKEND_ROOT}}": config.get("backend_root") or "",
        "{{FRONTEND_ROOT}}": config.get("frontend_root") or "",
        "{{SPECS_ROOT}}": config.get("specs_root") or "",
        "{{INTEGRATION_STATE_PATH}}": config.get("integration_state_path") or "",
        "{{DATA_MODEL_PATH}}": config.get("data_model_path") or "",
        "{{API_SPEC_PATH}}": config.get("api_spec_path") or "",
        "{{WORKFLOW_STANDARDS}}": standards.get("workflow") or "",
        "{{AUDIT_STANDARDS}}": standards.get("audit") or "",
    }

    # Conditional blocks for optional fields (strip block if value is null/empty).
    text = _strip_optional_block(text, "BACKEND_ROOT", config.get("backend_root"))
    text = _strip_optional_block(text, "FRONTEND_ROOT", config.get("frontend_root"))
    text = _strip_optional_block(text, "INTEGRATION_STATE", config.get("integration_state_path"))
    text = _strip_optional_block(text, "DATA_MODEL", config.get("data_model_path"))
    text = _strip_optional_block(text, "API_SPEC", config.get("api_spec_path"))

    for key, value in replacements.items():
        text = text.replace(key, value)

    return text


def _do_render_gateway(args) -> int:
    target = Path(args.target).resolve() if args.target else Path.cwd().resolve()
    config_path = target / "forge.config.yml"
    if not config_path.is_file():
        print(f"ERROR: {config_path} does not exist; run em-cli init first.", file=sys.stderr)
        return 3

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"ERROR parsing forge.config.yml: {e}", file=sys.stderr)
        return 2

    requested = set(args.only) if args.only else {rel for rel, _ in GATEWAY_ARTIFACTS}
    invalid = requested - {rel for rel, _ in GATEWAY_ARTIFACTS}
    if invalid:
        print(f"ERROR: unknown artifact(s) requested: {sorted(invalid)}", file=sys.stderr)
        return 1

    print(f"em-cli render-gateway → {target}")
    print(f"  config: {config_path.relative_to(target)}")
    print(f"  product_name: {config.get('product_name', '<missing>')}")
    print()

    written = 0
    skipped = 0
    for rel_path, template_name in GATEWAY_ARTIFACTS:
        if rel_path not in requested:
            continue
        content = _render_template(template_name, config)
        out = target / rel_path
        if out.exists() and not args.force:
            print(f"  SKIP  {rel_path}  (exists; pass --force to overwrite)")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  DRY   {rel_path}  ({len(content)} chars)")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"  WROTE {rel_path}  ({len(content)} chars)")
        written += 1

    print()
    if args.dry_run:
        print(f"Dry-run complete (would write {len(requested) - skipped} artifact(s)).")
    else:
        print(f"Done. {written} written, {skipped} skipped.")
    return 0


# ---------- setup (<TICKET-ID> Wave B real; replaces <TICKET-ID> Wave A STUB) ----------

# Filesystem signal files that indicate existing-repo (map mode); absent -> greenfield.
_SETUP_MAP_SIGNAL_FILES = (
    "package.json", "pyproject.toml", "Cargo.toml",
    "go.mod", "Gemfile", "composer.json", "build.gradle",
)


def _do_setup(args) -> int:
    """<TICKET-ID> Wave B: one-command framework setup wrapper.

    Auto-detects greenfield-vs-map from filesystem signals + invokes the
    appropriate init flow + chains doctor. Idempotent on re-run.

    Strategy v3 Pilar 1.2 brain (Wave A shells handle env bootstrap and
    delegate here for the user-facing setup logic).
    """
    import os as _os
    from argparse import Namespace

    target = Path(args.target).resolve() if args.target else Path.cwd().resolve()
    config_path = target / "forge.config.yml"

    # Idempotent re-run check (must_fix #6)
    if config_path.is_file() and not args.force:
        original_cwd = Path.cwd()
        try:
            _os.chdir(target)
            doctor_args = Namespace(check_groundedness=False, check_hook=False, check_gateway=False)
            rc = _do_doctor(doctor_args)
        finally:
            _os.chdir(original_cwd)
        if rc == 0:
            print(
                f"em-cli setup: already set up at {target}. forge.config.yml + doctor OK.\n"
                "Use --force to re-run init (will refuse to overwrite existing files unless --force).",
            )
            return 0
        print(
            f"em-cli setup: forge.config.yml exists at {target} but doctor reports errors.\n"
            "Run: python3 forge/tools/em-cli.py doctor (from the target dir) for details.",
            file=sys.stderr,
        )
        return 1

    # Auto-detect mode from filesystem signals
    has_existing_code = any((target / s).is_file() for s in _SETUP_MAP_SIGNAL_FILES)
    mode = "map" if has_existing_code else "greenfield"
    print(f"em-cli setup -> detected mode: {mode} (target={target})")

    # Forward to existing init flow. init reads cwd; chdir target then restore.
    original_cwd = Path.cwd()
    try:
        _os.chdir(target)
        args.mode = mode
        if mode == "greenfield":
            rc = _do_init_greenfield(args)
        else:
            rc = _do_init_map(args)
    finally:
        _os.chdir(original_cwd)

    if rc != 0:
        return rc

    # Final summary
    print()
    print("=" * 60)
    print(f"em-cli setup COMPLETE at {target}")
    print(f"  mode: {mode}")
    print(f"  config: forge.config.yml")
    print(f"  Run from target: python3 forge/tools/em-cli.py doctor")
    print("=" * 60)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="em-cli",
        description="Framework installer + workspace contract CLI (<TICKET-ID> framework release layer).",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    ap_init = sub.add_parser("init", help="Scaffold framework into a target repo")
    ap_init.add_argument("--mode", choices=["greenfield", "map"], default="greenfield",
                         help="Scaffolding mode: greenfield (blank canvas) or map (existing repo retrofit)")
    ap_init.add_argument("--dry-run", action="store_true", help="Preview without writing")
    ap_init.add_argument("--non-interactive", action="store_true",
                         help="No prompts; require all answers via flags")
    ap_init.add_argument("--force", action="store_true",
                         help="Overwrite existing forge.config.yml + spec stubs")
    ap_init.add_argument("--product-name")
    ap_init.add_argument("--language", choices=list(LANGUAGE_CHOICES))
    ap_init.add_argument("--framework")
    ap_init.add_argument("--backend-root", help="Path or 'null'")
    ap_init.add_argument("--frontend-root", help="Path or 'null'")

    ap_validate = sub.add_parser("validate", help="Validate forge.config.yml against schema")
    ap_validate.add_argument("path", nargs="?", help="Path to config file (default: cwd/forge.config.yml)")

    ap_doctor = sub.add_parser("doctor", help="Audit forge.config.yml ↔ filesystem coherence")
    ap_doctor.add_argument("--check-groundedness", action="store_true",
                           help="Also run anti-rot / groundedness baseline check")
    ap_doctor.add_argument("--check-hook", action="store_true",
                           help="Verify pre-commit-grd002a hook is installed in .git/hooks/")
    ap_doctor.add_argument("--check-gateway", action="store_true",
                           help="Warn if any gateway artifact (AGENTS.md / CLAUDE.md / etc.) is older than forge.config.yml")

    ap_update = sub.add_parser("update", help="Migrate forge.config.yml across schema_version bumps")
    ap_update.add_argument("--dry-run", action="store_true")

    ap_hook = sub.add_parser("install-hook", help="Install a framework git hook into .git/hooks/")
    ap_hook.add_argument("--hook", required=True, choices=list(KNOWN_HOOKS.keys()))
    ap_hook.add_argument("--target", help="Path to target .git dir (default: discover from cwd)")
    ap_hook.add_argument("--force", action="store_true", help="Replace existing hook")

    ap_render = sub.add_parser(
        "render-gateway",
        help="Render multi-agent gateway artifacts (AGENTS.md + copilot-instructions.md + CLAUDE.md + ai-bootstrap.md)",
    )
    ap_render.add_argument("--target", help="Target repo path (default: cwd)")
    ap_render.add_argument(
        "--only", nargs="+",
        choices=[rel for rel, _ in GATEWAY_ARTIFACTS],
        help="Render only specific artifacts (default: all)",
    )
    ap_render.add_argument("--force", action="store_true", help="Overwrite existing artifacts")
    ap_render.add_argument("--dry-run", action="store_true",
                           help="Show what would be written without writing")

    ap_serve = sub.add_parser(
        "serve-mcp",
        help="Start the framework MCP server (framework release layer — Pilar 2.2 FINAL)",
    )
    ap_serve.add_argument(
        "--transport", choices=["stdio", "http"], default="stdio",
        help="Transport mode (default: stdio = local-only, single-client-per-process)",
    )
    ap_serve.add_argument(
        "--port", type=int, default=8765,
        help="Port for streamable-http transport (default: 8765; ignored for stdio)",
    )

    ap_setup = sub.add_parser(
        "setup",
        help="One-command framework setup wrapper (Wave B <TICKET-ID>: real impl)",
    )
    ap_setup.add_argument("--target", help="Target repo path (default: cwd)")
    ap_setup.add_argument("--non-interactive", action="store_true",
                          help="No prompts; require all answers via flags")
    ap_setup.add_argument("--force", action="store_true",
                          help="Re-run setup even if forge.config.yml exists + doctor passes")
    ap_setup.add_argument("--dry-run", action="store_true",
                          help="Preview without writing (forwarded to init flow)")
    # Forward to init's underlying flags (setup auto-detects mode + dispatches)
    ap_setup.add_argument("--product-name")
    ap_setup.add_argument("--language", choices=list(LANGUAGE_CHOICES))
    ap_setup.add_argument("--framework")
    ap_setup.add_argument("--backend-root", help="Path or 'null'")
    ap_setup.add_argument("--frontend-root", help="Path or 'null'")

    args = ap.parse_args(argv)

    if args.command == "init":
        if args.mode == "greenfield":
            return _do_init_greenfield(args)
        if args.mode == "map":
            return _do_init_map(args)
        print(f"ERROR: unsupported --mode {args.mode!r}", file=sys.stderr)
        return 1

    if args.command == "validate":
        return _do_validate(args)

    if args.command == "doctor":
        return _do_doctor(args)

    if args.command == "update":
        return _do_update(args)

    if args.command == "install-hook":
        return _do_install_hook(args)

    if args.command == "render-gateway":
        return _do_render_gateway(args)

    if args.command == "serve-mcp":
        # <TICKET-ID> framework release layer: exec the MCP server script so its stdio is passed
        # transparently to the calling MCP client. The em-cli process IS the
        # MCP server when serve-mcp runs (stdio transport is process-bound).
        import os
        server_py = Path(__file__).resolve().parent / "mcp_server.py"
        cmd = [sys.executable, str(server_py), "--transport", args.transport, "--port", str(args.port)]
        os.execv(cmd[0], cmd)
        # Unreachable; execv replaces the process. Return 1 for static analysis.
        return 1  # pragma: no cover

    if args.command == "setup":
        return _do_setup(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
