[CmdletBinding()]
param(
    [switch]$Install
)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$msg) { Write-Host "[run-dev] $msg" }
function Write-Warn([string]$msg) { Write-Host "[run-dev] WARNING: $msg" -ForegroundColor Yellow }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# Detect venv folder
$venvCandidates = @('.venv-10', '.venv', 'venv')
$venvDir = $null
foreach ($name in $venvCandidates) {
    $candidate = Join-Path $repoRoot $name
    if (Test-Path $candidate) {
        $venvDir = (Resolve-Path $candidate).Path
        break
    }
}

if (-not $venvDir) {
    Write-Warn "Aucun venv trouve (.venv-10/.venv/venv). Le backend risque de ne pas demarrer."
} else {
    Write-Info "Venv detecte: $venvDir"
}

$backendDir = Join-Path $repoRoot 'backend'
$frontendDir = Join-Path $repoRoot 'frontend'

if (-not (Test-Path $backendDir)) { throw "Dossier backend introuvable: $backendDir" }
if (-not (Test-Path $frontendDir)) { throw "Dossier frontend introuvable: $frontendDir" }

# Optionally install deps
if ($Install) {
    if ($venvDir) {
        Write-Info "Installation deps backend (pip -r backend/requirements.txt)"
        $pythonExe = Join-Path $venvDir 'Scripts\python.exe'
        if (-not (Test-Path $pythonExe)) { throw "python.exe introuvable dans $venvDir" }
        & $pythonExe -m pip install -r (Join-Path $backendDir 'requirements.txt')
    } else {
        Write-Warn "Skip install backend: venv non detecte."
    }

    if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
        Write-Info "Installation deps frontend (npm install)"
        Push-Location $frontendDir
        try { npm install }
        finally { Pop-Location }
    } else {
        Write-Info "node_modules deja present -- skip npm install"
    }
}

# Resolve python executable (prefer venv)
$pythonExe = $null
if ($venvDir) {
    $candidate = Join-Path $venvDir 'Scripts\python.exe'
    if (Test-Path $candidate) { $pythonExe = $candidate }
}
if (-not $pythonExe) { $pythonExe = 'python' }

# Start backend in a new window
Write-Info "Demarrage backend (port 8000)"
$backendCmdLine = "`"$pythonExe`" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Start-Process -FilePath cmd.exe -WorkingDirectory $backendDir -ArgumentList @('/k', $backendCmdLine) | Out-Null

# Start frontend in a new window
Write-Info "Demarrage frontend (port 3000)"
Start-Process -FilePath cmd.exe -WorkingDirectory $frontendDir -ArgumentList @('/k', 'npm run dev') | Out-Null

Write-Info "OK. Ouvre http://localhost:3000 (UI) et http://localhost:8000/docs (API)."
Write-Info "Pour arreter: scripts\stop-dev.ps1"
