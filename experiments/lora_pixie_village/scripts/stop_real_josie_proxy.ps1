param(
  [Parameter(Mandatory = $true)][string]$RunId,
  [int]$Port = 8081
)

$ErrorActionPreference = "Stop"
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$config = Get-Content -LiteralPath (Join-Path $repo "pixieology.config.json") -Raw | ConvertFrom-Json
$dataRoot = [string]$config.paths.data_root
if (-not [IO.Path]::IsPathRooted($dataRoot)) { $dataRoot = Join-Path $repo $dataRoot }
$runtimeRoot = ([string]$config.paths.lora_pixie_village_runtime).Replace('${data_root}', [IO.Path]::GetFullPath($dataRoot))
if (-not [IO.Path]::IsPathRooted($runtimeRoot)) { $runtimeRoot = Join-Path $repo $runtimeRoot }
$tokenPath = Join-Path ([IO.Path]::GetFullPath($runtimeRoot)) "dual_lora_launches\$RunId\shutdown.token"
if (-not (Test-Path -LiteralPath $tokenPath -PathType Leaf)) { throw "Shutdown token not found: $tokenPath" }
$token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:$Port/pixie/shutdown" `
  -Headers @{ "X-Pixie-Shutdown-Token" = $token } `
  -ContentType "application/json" `
  -Body "{}" | ConvertTo-Json -Compress
Write-Host "Shutdown requested for owned run $RunId. The capped wrapper will write its cleanup receipt."
