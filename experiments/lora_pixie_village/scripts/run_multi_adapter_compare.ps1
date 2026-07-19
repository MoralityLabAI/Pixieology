param(
  [string]$RunId = "multi-adapter-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
  [int]$Port = 8081,
  [int]$MaxRuntimeMinutes = 10
)

$ErrorActionPreference = "Stop"
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$configPath = Join-Path $repo "pixieology.config.json"
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$dataRoot = [string]$config.paths.data_root
if (-not [IO.Path]::IsPathRooted($dataRoot)) { $dataRoot = Join-Path $repo $dataRoot }
$runtimeRoot = ([string]$config.paths.lora_pixie_village_runtime).Replace('${data_root}', [IO.Path]::GetFullPath($dataRoot))
if (-not [IO.Path]::IsPathRooted($runtimeRoot)) { $runtimeRoot = Join-Path $repo $runtimeRoot }
$runtimeRoot = [IO.Path]::GetFullPath($runtimeRoot)
$outputDir = Join-Path $runtimeRoot "multi_adapter_compares\$RunId"
$launchManifest = Join-Path $runtimeRoot "dual_lora_launches\$RunId\launch_manifest.json"
$pointer = Join-Path $PSScriptRoot "..\reports\multi_adapter_compare.receipt.json"
$capRoot = Join-Path $runtimeRoot "caps"
$resourceSummary = Join-Path $capRoot "$RunId.resource_summary.json"
$cleanup = Join-Path $capRoot "$RunId.cleanup.json"
$started = $false
$result = 1

try {
  & (Join-Path $PSScriptRoot "start_real_josie_proxy.ps1") `
    -RunId $RunId `
    -Port $Port `
    -MaxRuntimeMinutes $MaxRuntimeMinutes
  if ($LASTEXITCODE -ne 0) { throw "The capped multi-adapter backend did not start." }
  $started = $true

  python (Join-Path $PSScriptRoot "..\multi_adapter_compare.py") `
    --base-url "http://127.0.0.1:$Port" `
    --output-dir $outputDir `
    --launch-manifest $launchManifest `
    --pointer $pointer
  $result = $LASTEXITCODE
  if ($result -ne 0) { throw "Multi-adapter comparison failed with exit code $result." }
}
finally {
  if ($started) {
    try {
      & (Join-Path $PSScriptRoot "stop_real_josie_proxy.ps1") -RunId $RunId -Port $Port
    }
    catch {
      Write-Warning "Owned proxy shutdown needs inspection: $($_.Exception.Message)"
      if ($result -eq 0) { $result = 2 }
    }
  }
}

if ($result -eq 0) {
  $deadline = (Get-Date).AddSeconds(30)
  while ((-not (Test-Path -LiteralPath $resourceSummary) -or -not (Test-Path -LiteralPath $cleanup)) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
  }
  if (-not (Test-Path -LiteralPath $resourceSummary) -or -not (Test-Path -LiteralPath $cleanup)) {
    throw "Capped wrapper receipts were not finalized for $RunId."
  }
  python (Join-Path $PSScriptRoot "finalize_multi_adapter_receipt.py") `
    --pointer $pointer `
    --resource-summary $resourceSummary `
    --cleanup $cleanup
  $result = $LASTEXITCODE
}

exit $result
