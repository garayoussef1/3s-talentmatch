$ErrorActionPreference = "Stop"

function _mask([string]$v) {
  if (-not $v) { return "(absent)" }
  if ($v.Length -le 8) { return "(présent)" }
  return ($v.Substring(0,4) + "..." + $v.Substring($v.Length-4,4))
}

Write-Host "=== CamemBERT / HF env status ==="
Write-Host ("HF_ENABLE_CAMEMBERT_NAME = {0}" -f ($env:HF_ENABLE_CAMEMBERT_NAME ?? "(absent)"))
Write-Host ("HF_TOKEN                = {0}" -f (_mask $env:HF_TOKEN))
Write-Host ("HF_CAMEMBERT_NER_MODEL   = {0}" -f ($env:HF_CAMEMBERT_NER_MODEL ?? "(absent)"))
Write-Host ("HF_TIMEOUT_SECONDS       = {0}" -f ($env:HF_TIMEOUT_SECONDS ?? "(absent)"))

$enabled = $false
if ($env:HF_ENABLE_CAMEMBERT_NAME) {
  $v = $env:HF_ENABLE_CAMEMBERT_NAME.Trim().ToLower()
  if ($v -in @("1","true","yes","y","on")) { $enabled = $true }
  if ($v -in @("0","false","no","n","off")) { $enabled = $false }
} else {
  $enabled = [bool]$env:HF_TOKEN
}

Write-Host ("=> CamemBERT tenté au runtime: {0}" -f ($enabled ? "OUI" : "NON"))
