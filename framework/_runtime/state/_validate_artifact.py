#!/usr/bin/env python3
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
"""validate-artifact — FW-002 / framework release layer

Validates an ai-specs framework artifact (markdown or YAML) against its
declared JSON Schema (Draft 2020-12).

Two-stage validation:
  1. Parse the file:
       - .md  -> extract YAML frontmatter + headings list
       - .yml -> load YAML directly
  2. Apply the appropriate schema (declared in frontmatter, or auto-detected
     from path).

Exit codes:
  0   PASS
  1   FAIL (schema errors)
  2   ERROR (parse error, missing schema, file not found, etc.)

Usage:
  validate-artifact.py <file> [--schema PATH] [--json] [--quiet]
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

# Post W64 SCRUM-632: framework/_runtime/state/ IS a package — use absolute
# imports. forge/tools/ original copies retain ADR-006 bare-import pattern.
from framework._runtime.state._common import find_framework_install_root  # noqa: E402

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install --user pyyaml", file=sys.stderr)
    sys.exit(2)


def _normalize_dates(obj):
    """Walk a parsed structure and convert datetime/date objects to ISO strings.

    YAML 1.1 auto-coerces 2026-05-13 to datetime.date and 2026-05-13T12:00:00Z to
    datetime.datetime. JSON Schema expects strings for `format: date`/`date-time`.
    Without this normalization every artifact with an unquoted date in frontmatter
    fails validation, which is a parser bug — not a schema or content bug.
    """
    if isinstance(obj, dict):
        return {k: _normalize_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_dates(v) for v in obj]
    if isinstance(obj, datetime.datetime):
        # Always emit UTC Z form when naive; otherwise keep tz.
        if obj.tzinfo is None:
            return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    return obj

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install --user 'jsonschema>=4.21'", file=sys.stderr)
    sys.exit(2)


# SKIP_PATHS: paths that match these patterns are explicitly free-form (no
# schema required). The tool returns verdict SKIP (exit 0) so CI doesn't fail.
# Use this for audit-folder design notes and analysis docs that aren't
# F-resolutions, audit phase reports, or completion reports. Keep this list
# narrow: explicit > implicit.
SKIP_PATHS = [
    # 00-index.md / 00-summary.md are free-form audit-folder overviews
    # (operator-authored). Required by audit-completion-check.py but have
    # no schema (would be over-constrained).
    r'/audits/[^/]+/00-(index|summary)\.md$',
    r'/audit/audit-[^/]+/00-(index|summary)\.md$',
    # Pre-schema historical phase reports written ad-hoc before
    # audit-phase-report.schema.yml existed as enforceable rule. Future audits
    # will declare `schema:` in frontmatter and route via the frontmatter
    # detector (which runs first). Grandfathered files without frontmatter SKIP.
    r'/audits/[^/]+-full-audit/(?:0[1-9]|[1-9]\d)-[a-z][a-z0-9-]*\.md$',
    # Framework playbook CHANGELOG at forge/CHANGELOG.md (append-only).
    r'/forge/CHANGELOG\.md$',
    # Module-level plan/roadmap docs (e.g. changes/auth/AUTH-v2-plan.md) —
    # free-form human planning docs; not lifecycle artifacts (those live under
    # plans/<sprint>/ with their own schema).
    r'/artifacts/[^/]+/[A-Za-z][A-Za-z0-9-]*-plan\.md$',
    # <TICKET-ID> (framework release layer): agent-runtime-conventions.md is a reference spec
    # documenting Claude Code runtime conventions consumed symbolically by
    # forge/.agents/*.md personas. No schema (would be over-constrained).
    r'/forge/specs/agent-runtime-conventions\.md$',
]

# Auto-detect rules: pattern matched against the absolute file path.
# First match wins. Schemas live under <repo>/forge/schemas/.
SCHEMA_BY_PATH = [
    (r'/artifacts/[^/]+/plans/[^/]+/[A-Z][A-Z0-9]*-\d+_(backend|frontend|fullstack)\.md$', 'plan.schema.yml'),
    (r'/artifacts/[^/]+/plans/[^/]+/[A-Z][A-Z0-9]*-\d+_verify\.md$',                       'verify.schema.yml'),
    (r'/artifacts/[^/]+/records/[^/]+/[A-Z][A-Z0-9]*-\d+_(backend|frontend|fullstack)\.md$', 'record.schema.yml'),
    (r'/artifacts/[^/]+/state/[A-Z][A-Z0-9]*-\d+\.ya?ml$',                                 'state.schema.yml'),
    # <TICKET-ID> (framework release layer): workspace contract — forge.config.yml at repo root,
    # consumed symbolically by agent personas (Pre-session read 0).
    (r'/forge\.config\.ya?ml$',                                                            'forge-workspace.schema.yml'),
    (r'/artifacts/[^/]+/audit/audit-[^/]+/fase-\d+[^/]*\.md$',                     'audit-phase-report.schema.yml'),
    (r'/artifacts/[^/]+/audit/audit-[^/]+/[a-z][a-z0-9-]*-completion-report\.md$', 'audit-completion-report.schema.yml'),
    # <TICKET-ID>: G/F-findings stored as one-file-per-finding under findings/.
    # The two rules below cover new plural + legacy singular folder layouts.
    (r'/artifacts/[^/]+/audits/[^/]+/findings/[GF]\d+\.md$',                       'audit-finding.schema.yml'),
    (r'/artifacts/[^/]+/audit/audit-[^/]+/findings/[GF]\d+\.md$',                  'audit-finding.schema.yml'),
    (r'/bypass-log\.ya?ml$',                                                     'bypass-log.schema.yml'),
    (r'/registers/pending-improvements\.ya?ml$',                                 'pending-improvements.schema.yml'),
    (r'/specs/modules/[a-z][a-z0-9-]*/module-charter\.md$',                      'charter.schema.yml'),
    (r'/specs/modules/[a-z][a-z0-9-]*/module-boundary\.md$',                     'boundary.schema.yml'),
    (r'/specs/modules/[a-z][a-z0-9-]*/stable-baseline\.md$',                     'stable-baseline.schema.yml'),
    (r'/specs/freeze-status\.md$',                                               'freeze-status.schema.yml'),
    (r'/commands\.catalog\.yml$',                                                'commands-catalog.schema.yml'),
    (r'/\.anti-rot-allowlist\.ya?ml$',                                           'anti-rot-allowlist.schema.yml'),
    (r'/\.deviation-taxonomy\.ya?ml$',                                           'deviation-taxonomy.schema.yml'),
    (r'/\.checks-registry\.ya?ml$',                                              'checks.schema.yml'),
    (r'/\.framework-modules\.ya?ml$',                                            'framework-module.schema.yml'),
]

FRONTMATTER_RE = re.compile(r'\A---\r?\n(.*?)\r?\n---\r?\n', re.DOTALL)
HEADING_RE     = re.compile(r'^(#{1,6})\s+(.+?)\s*$')


# ---------- Parsing ----------

def parse_markdown(text):
    """Return {'frontmatter': dict, 'headings': [{'level': int, 'text': str}], ...}."""
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError as e:
            raise ValueError(f'Invalid YAML in frontmatter: {e}')
        if not isinstance(frontmatter, dict):
            raise ValueError('Frontmatter is not a mapping')
        body = text[fm_match.end():]
    else:
        frontmatter = {}
        body = text

    headings = []
    in_fence = False
    fence_marker = None
    for raw_line in body.split('\n'):
        stripped = raw_line.lstrip()
        # Track fenced code blocks (``` or ~~~).
        if stripped.startswith('```') or stripped.startswith('~~~'):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif stripped.startswith(fence_marker):
                in_fence = False
                fence_marker = None
            continue
        if in_fence:
            continue
        # Setext or atx? We only handle atx for simplicity (matches framework convention).
        m = HEADING_RE.match(raw_line)
        if m:
            level = len(m.group(1))
            text_part = m.group(2).strip()
            # strip trailing #s (atx-closing form)
            text_part = re.sub(r'\s+#+\s*$', '', text_part)
            # strip bold/italic markup commonly used: **text** -> text
            text_part = re.sub(r'^\*\*(.+?)\*\*$', r'\1', text_part)
            text_part = re.sub(r'^\*(.+?)\*$', r'\1', text_part)
            headings.append({'level': level, 'text': text_part})

    # Shallow copy so we can mutate without touching the YAML-loaded dict.
    fm = dict(frontmatter) if isinstance(frontmatter, dict) else frontmatter
    parsed = {'frontmatter': fm, 'headings': headings}

    # Lift schema-relevant top-level fields out of frontmatter when the schema
    # expects them at top-level. The audit-phase-report schema declares `checks`
    # at the root; authors naturally write it inside frontmatter so the markdown
    # body stays human-readable. Lift before normalization so the date-walker
    # sees the lifted shape.
    if isinstance(fm, dict):
        for lift_key in ('checks',):
            if lift_key in fm:
                parsed[lift_key] = fm.pop(lift_key)

    # Normalize dates AFTER the lift so the date-walker reaches every field.
    parsed = _normalize_dates(parsed)
    return parsed


def extract_body(text):
    """Return the markdown content past the frontmatter block (or whole text if none)."""
    m = FRONTMATTER_RE.match(text)
    return text[m.end():] if m else text


def parse_yaml_file(text):
    """Return the parsed YAML object with dates normalized to ISO strings."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f'Invalid YAML: {e}')
    if data is None:
        raise ValueError('YAML file is empty')
    return _normalize_dates(data)


# ---------- Schema detection ----------

def detect_schema_from_path(file_path):
    """Return relative schema path (e.g., 'forge/schemas/plan.schema.yml') or None."""
    p = str(file_path).replace('\\', '/')
    for pattern, schema_name in SCHEMA_BY_PATH:
        if re.search(pattern, p):
            return f'forge/schemas/{schema_name}'
    return None


def detect_schema_from_frontmatter(parsed):
    """For markdown: read frontmatter.schema. For YAML: try root.schema or known shape."""
    if isinstance(parsed, dict):
        if 'frontmatter' in parsed and isinstance(parsed['frontmatter'], dict):
            return parsed['frontmatter'].get('schema')
        if 'schema' in parsed:
            return parsed.get('schema')
        if '$schema' in parsed:
            # This is a schema FILE itself, not an artifact. Refuse.
            return '__schema_file__'
    return None


# ---------- Schema location ----------

def load_schema(schema_ref, repo_root):
    """Resolve a schema ref to its on-disk location.

    Accepts an absolute path OR a repo-relative path. The legacy symbolic
    prefix `ai-specs/schemas/...` (used in historical artifact frontmatter
    and current schema `const:` fields) is translated to `forge/schemas/...`
    transparently — the engine dir was renamed in <TICKET-ID> but the symbolic
    schema identifier stays stable so historical artifacts still validate.
    """
    if Path(schema_ref).is_absolute():
        path = Path(schema_ref)
    else:
        if repo_root is None:
            raise FileNotFoundError(
                f'Could not locate repo root (no forge/schemas/ found). '
                f'Provide --schema with an absolute path.'
            )
        # Translate legacy symbolic prefix to the renamed engine dir.
        if schema_ref.startswith('ai-specs/schemas/'):
            schema_ref = 'forge/schemas/' + schema_ref[len('ai-specs/schemas/'):]
        path = repo_root / schema_ref
    if not path.is_file():
        raise FileNotFoundError(f'Schema file not found: {path}')
    with path.open() as fh:
        try:
            schema = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            raise ValueError(f'Schema is not valid YAML: {e}')
    if not isinstance(schema, dict):
        raise ValueError(f'Schema root is not a mapping: {path}')
    # Validate the schema is itself well-formed (cheap protection).
    Draft202012Validator.check_schema(schema)
    return schema, path


# ---------- Main validate() ----------

def validate(file_path, schema_override=None, strict_groundedness=False,
             groundedness_offline=False, allowlist_path=None):
    """Validate one file. Return result dict (always has 'verdict').

    When strict_groundedness=True and the file is markdown, groundedness checks
    (GRD-001/002/003) run AFTER schema validation. Violations are reported in
    the result dict under 'groundedness' but do NOT alter the verdict — schema
    remains authoritative per <TICKET-ID> §18.3 (warn-only iteration).
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {'verdict': 'ERROR', 'reason': f'File not found: {file_path}'}
    file_path = file_path.resolve()

    # Parse based on extension
    ext = file_path.suffix.lower()
    text = file_path.read_text(encoding='utf-8')
    try:
        if ext in ('.md', '.markdown'):
            parsed = parse_markdown(text)
        elif ext in ('.yml', '.yaml'):
            parsed = parse_yaml_file(text)
        else:
            return {'verdict': 'ERROR',
                    'reason': f'Unsupported extension {ext!r} (expected .md or .yml/.yaml)'}
    except ValueError as e:
        return {'verdict': 'ERROR', 'reason': f'Parse error: {e}'}

    # Detect schema
    schema_ref = schema_override
    if not schema_ref:
        schema_ref = detect_schema_from_frontmatter(parsed)
        if schema_ref == '__schema_file__':
            return {'verdict': 'ERROR',
                    'reason': 'This file looks like a schema definition (has $schema), not an artifact. '
                              'Refusing to validate a schema with itself.'}
    if not schema_ref:
        schema_ref = detect_schema_from_path(str(file_path))
    if not schema_ref:
        # Explicit skip for free-form paths (audit-folder design notes etc.).
        if not schema_override:  # only auto-skip when no schema was forced
            abs_path = str(file_path)
            for pat in SKIP_PATHS:
                if re.search(pat, abs_path):
                    return {'verdict': 'SKIP',
                            'file': str(file_path),
                            'reason': 'no schema required (matched SKIP_PATHS)'}
        return {'verdict': 'ERROR',
                'reason': 'Could not determine which schema to apply. '
                          'No frontmatter `schema:` field and path does not match any auto-detect rule. '
                          'Pass --schema explicitly.'}

    # Resolve + load. Schemas live in the ENGINE, so resolve from the
    # framework root (cwd-independent default), NOT by walking up from the
    # artifact — the artifact may live in a separate governed repo. <TICKET-ID>.
    repo_root = find_framework_install_root()
    try:
        schema, schema_path = load_schema(schema_ref, repo_root)
    except (FileNotFoundError, ValueError) as e:
        return {'verdict': 'ERROR', 'reason': str(e)}
    except Exception as e:
        return {'verdict': 'ERROR', 'reason': f'Schema load failed: {type(e).__name__}: {e}'}

    # Validate
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(parsed))

    base = {
        'file': str(file_path),
        'schema': schema_ref,
        'schema_resolved': str(schema_path),
    }

    if strict_groundedness and ext in ('.md', '.markdown'):
        try:
            from _groundedness import run_groundedness, load_allowlist
            if repo_root is not None:
                allowlist = load_allowlist(allowlist_path if allowlist_path else repo_root)
                body = extract_body(text)
                violations, rules_run = run_groundedness(
                    parsed, body, file_path, repo_root, allowlist,
                    offline=groundedness_offline,
                )
                base['groundedness'] = {
                    'warnings': [v.__dict__ for v in violations],
                    'rules_run': rules_run,
                }
            else:
                base['groundedness'] = {
                    'warnings': [], 'rules_run': [], 'note': 'skipped — no repo root',
                }
        except ImportError as e:
            base['groundedness'] = {
                'warnings': [], 'rules_run': [], 'note': f'import error: {e}',
            }

    if not errors:
        return {'verdict': 'PASS', **base}

    base['errors'] = []
    for e in errors:
        base['errors'].append({
            'path': '/'.join(str(p) for p in e.absolute_path) or '(root)',
            'message': e.message[:400],
            'validator': e.validator,
            'schema_path': '/'.join(str(p) for p in e.absolute_schema_path),
        })
    return {'verdict': 'FAIL', **base}


# ---------- Typed orchestrator API (<TICKET-ID>) ----------

class ValidationResult(BaseModel):
    """Strict-typed view of validate() for in-memory consumers (the orchestrator).

    The CLI path keeps consuming the dict from validate() verbatim (so stdout is
    byte-identical); this model is the typed boundary that importers receive.
    `schema_ref` (not `schema`) avoids shadowing pydantic's BaseModel.schema.
    """
    model_config = ConfigDict(extra="forbid")
    verdict: str  # PASS | SKIP | FAIL | ERROR
    file: Optional[str] = None
    schema_ref: Optional[str] = None
    schema_resolved: Optional[str] = None
    errors: list[dict] = []
    reason: Optional[str] = None
    groundedness: Optional[dict] = None


def validate_typed(*args, **kwargs) -> ValidationResult:
    """Importable, strict-typed wrapper over validate(). Orchestrator-facing."""
    d = validate(*args, **kwargs)
    return ValidationResult(
        verdict=d["verdict"],
        file=d.get("file"),
        schema_ref=d.get("schema"),
        schema_resolved=d.get("schema_resolved"),
        errors=d.get("errors", []),
        reason=d.get("reason"),
        groundedness=d.get("groundedness"),
    )


# ---------- CLI ----------

def _print_human(result):
    v = result['verdict']
    if v == 'PASS':
        print(f"PASS  {result['file']}")
        print(f"      schema: {result['schema']}")
    elif v == 'SKIP':
        print(f"SKIP  {result['file']}")
        print(f"      {result['reason']}")
    elif v == 'ERROR':
        print(f"ERROR {result.get('file', '(no file)')}")
        print(f"      {result['reason']}")
    else:  # FAIL
        print(f"FAIL  {result['file']}")
        print(f"      schema: {result['schema']}")
        print(f"      {len(result['errors'])} validation error(s):")
        for i, err in enumerate(result['errors'], 1):
            print(f"  {i:>2}. at {err['path']}")
            print(f"      {err['message']}")
    g = result.get('groundedness')
    if g and g.get('warnings'):
        rules = ','.join(g.get('rules_run', []))
        print(f"      GROUNDEDNESS WARN ({len(g['warnings'])} violations across {rules}):")
        for i, w in enumerate(g['warnings'], 1):
            loc = f"{w['file']}:{w['line']}" if w.get('line') else w['file']
            print(f"  G{i:>2}. [{w['rule_id']}] {w['ref']} at {loc}")
            print(f"        {w['message']}")


def run_cli(argv=None):
    """Relocated main(): parse argv, validate, print, RETURN the exit code (0/1/2)."""
    ap = argparse.ArgumentParser(
        prog='validate-artifact',
        description='Validate an ai-specs framework artifact against its JSON Schema.',
    )
    ap.add_argument('file', help='Path to artifact (.md or .yml)')
    ap.add_argument('--schema',
                    help='Override the schema (relative to repo root or absolute path)')
    ap.add_argument('--json', action='store_true',
                    help='Print the result as JSON instead of human-readable')
    ap.add_argument('--quiet', '-q', action='store_true',
                    help='Suppress PASS output; only print on FAIL/ERROR')
    ap.add_argument('--strict-groundedness', action='store_true',
                    help='Cross-check PR/SHA/file:line refs against authoritative sources (GRD-001/002/003)')
    ap.add_argument('--groundedness-offline', action='store_true',
                    help='Skip network calls (gh pr view); use cache only')
    ap.add_argument('--allowlist',
                    help='Override allowlist path (default: <repo>/forge/.groundedness-allowlist.yml)')
    args = ap.parse_args(argv)

    result = validate(
        args.file,
        schema_override=args.schema,
        strict_groundedness=args.strict_groundedness,
        groundedness_offline=args.groundedness_offline,
        allowlist_path=Path(args.allowlist) if args.allowlist else None,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if not (args.quiet and result['verdict'] == 'PASS'):
            _print_human(result)

    if result['verdict'] in ('PASS', 'SKIP'):
        return 0
    if result['verdict'] == 'FAIL':
        return 1
    return 2
