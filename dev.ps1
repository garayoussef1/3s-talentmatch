param(
  [string]$BackendHost = "127.0.0.1",
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

# Affichage UTF-8 propre dans le terminal (accents)
try {
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
} catch {
  # ignore
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $RepoRoot ".venv-10\Scripts\python.exe"
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

if (-not (Test-Path $VenvPython)) { throw "Python venv introuvable: $VenvPython" }
if (-not (Test-Path $BackendDir)) { throw "Dossier backend introuvable: $BackendDir" }
if (-not (Test-Path $FrontendDir)) { throw "Dossier frontend introuvable: $FrontendDir" }

$LogsDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$BackendOutLog = Join-Path $LogsDir "backend.out.log"
$BackendErrLog = Join-Path $LogsDir "backend.err.log"
$FrontendOutLog = Join-Path $LogsDir "frontend.out.log"
$FrontendErrLog = Join-Path $LogsDir "frontend.err.log"

# Backend (FastAPI)
$backendArgs = @(
  "-m", "uvicorn",
  "app.main:app",
  "--host", $BackendHost,
  "--port", "$BackendPort"
)

$backendProc = Start-Process -FilePath $VenvPython -ArgumentList $backendArgs -WorkingDirectory $BackendDir -PassThru -WindowStyle Hidden -RedirectStandardOutput $BackendOutLog -RedirectStandardError $BackendErrLog

# Frontend (Vite)
# Windows: `npm` est souvent un shim (npm.cmd). Pour éviter l'erreur Win32, on passe par cmd.exe.
$frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm", "run", "dev") -WorkingDirectory $FrontendDir -PassThru -WindowStyle Hidden -RedirectStandardOutput $FrontendOutLog -RedirectStandardError $FrontendErrLog

# Détecter le vrai port Vite (si 3000 est déjà pris, Vite bascule sur 3001/3002/...)
$detectedFrontendPort = $FrontendPort
try {
  $deadline = (Get-Date).AddSeconds(8)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path $FrontendOutLog) {
      $tail = Get-Content $FrontendOutLog -Tail 80 -ErrorAction SilentlyContinue | Out-String
      $m = [regex]::Match($tail, "http://localhost:(\d+)/")
      if ($m.Success) {
        $detectedFrontendPort = [int]$m.Groups[1].Value
        break
      }
    }
    Start-Sleep -Milliseconds 250
  }
} catch {
  # ignore
}

$pids = [ordered]@{
  backend_pid = $backendProc.Id
  frontend_pid = $frontendProc.Id
  started_at = (Get-Date).ToString("o")
  backend_url = "http://$BackendHost`:$BackendPort"
  frontend_url = "http://localhost:$detectedFrontendPort"
  backend_stdout_log = $BackendOutLog
  backend_stderr_log = $BackendErrLog
  frontend_stdout_log = $FrontendOutLog
  frontend_stderr_log = $FrontendErrLog
}

$pidsPath = Join-Path $RepoRoot "logs\.dev-pids.json"
$pids | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -Path $pidsPath

Write-Host "Backend PID: $($backendProc.Id)  -> http://$BackendHost`:$BackendPort (logs: $BackendOutLog / $BackendErrLog)"
Write-Host "Frontend PID: $($frontendProc.Id) -> http://localhost:$detectedFrontendPort (logs: $FrontendOutLog / $FrontendErrLog)"
Write-Host "Pour arrêter: .\stop-dev.ps1"
