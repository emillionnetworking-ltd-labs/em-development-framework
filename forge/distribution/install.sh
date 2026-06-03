#!/usr/bin/env bash
# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
# Strategy v3 Wave A <TICKET-ID> — em-development-framework one-command installer (Linux/macOS).
# Idempotent. PEP-668-compliant. Distro-aware ensurepip detection.
# Companion: install.ps1 (Windows PowerShell). Full docs: INSTALL.md.

set -euo pipefail
INSTALLED=()
cleanup() {
  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "ERROR rc=$rc — rolling back partial install:" >&2
    for p in "${INSTALLED[@]:-}"; do rm -rf "$p" 2>/dev/null && echo "  removed $p" >&2 || true; done
  fi
  exit $rc
}
trap cleanup EXIT ERR INT TERM

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not on PATH. Install Python >=3.10." >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git not on PATH." >&2; exit 1; }

if ! python3 -c "import ensurepip" 2>/dev/null; then
  if [ -f /etc/os-release ]; then . /etc/os-release; fi
  case "${ID:-unknown}" in
    debian|ubuntu) MSG="apt install python3-venv" ;;
    fedora|rhel|centos|rocky|almalinux) MSG="dnf install python3-venv" ;;
    arch|manjaro) MSG="pacman -S python" ;;
    *) [ "${OSTYPE:-}" = "darwin"* ] && MSG="brew install python@3.12 (ensurepip ships with brew)" || MSG="install your distro's python3-venv package" ;;
  esac
  echo "ERROR: python3 venv module missing. Run: $MSG" >&2
  exit 1
fi

if [ -d .venv ] && [ "${1:-}" != "--force" ]; then
  echo "INFO: .venv exists; idempotent skip. Use --force to recreate." >&2
  exec python3 forge/tools/em-cli.py setup
fi

python3 -m venv .venv
INSTALLED+=(".venv")
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --quiet -r requirements.txt
exec python3 forge/tools/em-cli.py setup
