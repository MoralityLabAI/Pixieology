param(
  [string]$StudyId = "multi-adapter-ni-v1",
  [string]$RunId = "$StudyId-companion-semantic",
  [int]$MaxRuntimeMinutes = 10
)

$ErrorActionPreference = "Stop"
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$configPath = Join-Path $repo "pixieology.config.json"
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$dataRoot = [string]$config.paths.data_root
if (-not [IO.Path]::IsPathRooted($dataRoot)) { $dataRoot = Join-Path $repo $dataRoot }
$runtimeRoot = ([string]$config.paths.lora_pixie_village_runtime).Replace('${data_root}', [IO.Path]::GetFullPath($dataRoot))
$capRoot = Join-Path ([IO.Path]::GetFullPath($runtimeRoot)) "caps"
$pointer = Join-Path $PSScriptRoot "..\reports\multi_adapter_noninferiority_companion.receipt.json"
$resourceSummary = Join-Path $capRoot "$RunId.resource_summary.json"
$cleanup = Join-Path $capRoot "$RunId.cleanup.json"
$python = (Get-Command python).Source
$childArguments = @(
  [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "analyze_noninferiority_companion.py")),
  "--config", $configPath,
  "--study-id", $StudyId
)
$argumentJson = ConvertTo-Json $childArguments -Compress
$argumentBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentJson))
$capWrapper = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\persona_training\run_capped_strict.ps1"))

& $capWrapper -Executable $python -ArgumentsBase64 $argumentBase64 -RunId $RunId `
  -OutputDirectory $capRoot -MemoryGB 2 -CpuPercent 50 -IoMBPerSecond 50 `
  -TimeoutMinutes $MaxRuntimeMinutes
$result = $LASTEXITCODE
if ($result -eq 0) {
  python (Join-Path $PSScriptRoot "finalize_multi_adapter_receipt.py") `
    --pointer $pointer --resource-summary $resourceSummary --cleanup $cleanup
  $result = $LASTEXITCODE
}
exit $result
