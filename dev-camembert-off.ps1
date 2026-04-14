param(
  [string]$BackendHost = "127.0.0.1",
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DevScript = Join-Path $RepoRoot "dev.ps1"
if (-not (Test-Path $DevScript)) { throw "dev.ps1 introuvable: $DevScript" }

# Désactiver explicitement CamemBERT (même si HF_TOKEN existe)
$env:HF_ENABLE_CAMEMBERT_NAME = "0"

Write-Host "CamemBERT: OFF (HF_ENABLE_CAMEMBERT_NAME=0)"

& $DevScript -BackendHost $BackendHost -BackendPort $BackendPort -FrontendPort $FrontendPort
