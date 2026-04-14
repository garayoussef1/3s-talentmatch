[CmdletBinding()]
param(
    [int[]]$Ports = @(8000, 3000)
)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$msg) { Write-Host "[stop-dev] $msg" }
function Write-Warn([string]$msg) { Write-Host "[stop-dev] WARNING: $msg" -ForegroundColor Yellow }

foreach ($port in $Ports) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
    } catch {
        Write-Warn "Impossible de lire les connexions pour le port $port (Get-NetTCPConnection)."
        continue
    }

    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $procIds -or $procIds.Count -eq 0) {
        Write-Info "Aucun process à l'écoute sur $port"
        continue
    }

    foreach ($procId in $procIds) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Write-Info "Stop PID=$procId ($($proc.ProcessName)) pour port $port"
            Stop-Process -Id $procId -Force
        } catch {
            Write-Warn "Échec stop PID=$procId sur port $port : $($_.Exception.Message)"
        }
    }
}

Write-Info "Terminé. Si un terminal est resté ouvert, tu peux aussi faire Ctrl+C dedans."
