param(
  [string]$RunId = "multi-adapter-ni-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
  [string]$StudyId = $RunId,
  [int]$Port = 8081,
  [int]$MaxItems = 12,
  [int]$MaxRuntimeMinutes = 30
)

$ErrorActionPreference = "Stop"
if ($MaxRuntimeMinutes -lt 1 -or $MaxRuntimeMinutes -gt 30) {
  throw "MaxRuntimeMinutes must be between 1 and 30."
}
if ($MaxItems -lt 1 -or $MaxItems -gt 44) { throw "MaxItems must be between 1 and 44." }
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$configPath = Join-Path $repo "pixieology.config.json"
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$dataRoot = [string]$config.paths.data_root
if (-not [IO.Path]::IsPathRooted($dataRoot)) { $dataRoot = Join-Path $repo $dataRoot }
$runtimeRoot = ([string]$config.paths.lora_pixie_village_runtime).Replace('${data_root}', [IO.Path]::GetFullPath($dataRoot))
if (-not [IO.Path]::IsPathRooted($runtimeRoot)) { $runtimeRoot = Join-Path $repo $runtimeRoot }
$runtimeRoot = [IO.Path]::GetFullPath($runtimeRoot)
$capRoot = Join-Path $runtimeRoot "caps"
$pointer = Join-Path $PSScriptRoot "..\reports\multi_adapter_noninferiority.receipt.json"
$resourceSummary = Join-Path $capRoot "$RunId.resource_summary.json"
$cleanup = Join-Path $capRoot "$RunId.cleanup.json"
$python = (Get-Command python).Source
$studyScript = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "real_multi_adapter_noninferiority.py"))
$childArguments = @(
  $studyScript,
  "--config", $configPath,
  "--run-id", $RunId,
  "--study-id", $StudyId,
  "--max-items", [string]$MaxItems,
  "--port", [string]$Port,
  "--startup-timeout", "180"
)
$argumentJson = ConvertTo-Json $childArguments -Compress
$argumentBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentJson))
$capWrapper = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\persona_training\run_capped_strict.ps1"))

& $capWrapper `
  -Executable $python `
  -ArgumentsBase64 $argumentBase64 `
  -RunId $RunId `
  -OutputDirectory $capRoot `
  -MemoryGB 2 `
  -CpuPercent 50 `
  -IoMBPerSecond 50 `
  -TimeoutMinutes $MaxRuntimeMinutes
$result = $LASTEXITCODE

if ((Test-Path -LiteralPath $pointer) -and (Test-Path -LiteralPath $resourceSummary) -and (Test-Path -LiteralPath $cleanup)) {
  python (Join-Path $PSScriptRoot "finalize_multi_adapter_receipt.py") `
    --pointer $pointer `
    --resource-summary $resourceSummary `
    --cleanup $cleanup
  $finalizeResult = $LASTEXITCODE
  if ($result -eq 0) { $result = $finalizeResult }
}

exit $result
