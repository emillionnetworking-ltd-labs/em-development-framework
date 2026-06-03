# Copyright (c) 2026 EMillion Networking LTD
# SPDX-License-Identifier: MIT
# Strategy v3 Wave A <TICKET-ID> — em-development-framework one-command installer (Windows).
# Idempotent. PEP-668-compliant. Companion: install.sh (Linux/macOS). Full docs: INSTALL.md.

$ErrorActionPreference = "Stop"
# PEP 540 UTF-8 Mode: forces Python stdout/stderr to UTF-8 on Windows cp1252
# console. Without this, framework print() calls with non-ASCII chars (-> arrows,
# em-dashes) raise UnicodeEncodeError on Windows cmd/PowerShell default console.
$env:PYTHONUTF8 = "1"
$Installed = @()
$ExitCode = 0
try {
    $pyCmd = (Get-Command python -ErrorAction SilentlyContinue) `
        ?? (Get-Command py -ErrorAction SilentlyContinue) `
        ?? (Get-Command python3 -ErrorAction SilentlyContinue)
    if (-not $pyCmd) {
        Write-Error "python not on PATH. Install Python >=3.10 via: winget install Python.Python.3.12"
        exit 1
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Error "git not on PATH."
        exit 1
    }
    & $pyCmd.Source -c "import ensurepip" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "python venv module missing. Reinstall Python via winget install Python.Python.3.12"
        exit 1
    }
    $forceFlag = ($args.Count -gt 0) -and ($args[0] -eq "--force")
    if ((Test-Path ".venv") -and (-not $forceFlag)) {
        Write-Host "INFO: .venv exists; idempotent skip. Use --force to recreate."
        & ".venv\Scripts\python.exe" forge/tools/em-cli.py setup
        exit $LASTEXITCODE
    }
    & $pyCmd.Source -m venv .venv
    $Installed += ".venv"
    & ".venv\Scripts\pip.exe" install --quiet -r requirements.txt
    & ".venv\Scripts\python.exe" forge/tools/em-cli.py setup
    $ExitCode = $LASTEXITCODE
}
catch {
    Write-Error "ERROR: $_ — rolling back"
    foreach ($p in $Installed) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue }
    $ExitCode = 1
}
exit $ExitCode
