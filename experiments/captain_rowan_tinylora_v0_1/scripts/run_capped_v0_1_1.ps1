param(
  [Parameter(Mandatory = $true)][ValidateSet("Train", "Evaluate")][string]$Mode,
  [Parameter(Mandatory = $true)][string]$Authorization,
  [string]$Adapter = "",
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$repo = [IO.Path]::GetFullPath((Join-Path $root "..\.."))
$runner = Join-Path $root "run_v0_1_1.py"
$jobPath = Join-Path $root "job_v0_1_1.json"
$authorizationPath = [IO.Path]::GetFullPath($Authorization)
$feedbackRoot = Join-Path $repo "experiments\pixie_lora_feedback_loop_v0_2"
$feedbackProtocolPath = Join-Path $feedbackRoot "protocol.json"
$feedbackRunner = Join-Path $feedbackRoot "run.py"

& $PythonExecutable $runner verify --job $jobPath --require-model
if ($LASTEXITCODE -ne 0) { throw "Captain Rowan v0.1.1 frozen-input verification failed." }
& $PythonExecutable $runner authorization-check --job $jobPath --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "Captain Rowan v0.1.1 exact-job authorization validation failed." }

$job = Get-Content -LiteralPath $jobPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $runner -Algorithm SHA256).Hash.ToLowerInvariant() -ne $job.execution.retry_launcher_sha256) {
  throw "Captain Rowan v0.1.1 launcher differs from the bound job."
}
if ((Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $job.execution.retry_wrapper_sha256) {
  throw "Captain Rowan v0.1.1 wrapper differs from the bound job."
}

$protocol = Get-Content -LiteralPath $feedbackProtocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $feedbackRoot $protocol.bounded_launcher.underlying_job_wrapper))
$cleanup = [IO.Path]::GetFullPath((Join-Path $feedbackRoot $protocol.bounded_launcher.cleanup))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.underlying_job_wrapper_sha256) {
  throw "Underlying Job Object wrapper differs from the sealed feedback protocol."
}
if ((Get-FileHash -LiteralPath $cleanup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.cleanup_sha256) {
  throw "Cleanup script differs from the sealed feedback protocol."
}
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { throw "nvidia-smi is required." }
$memoryLines = @(& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null)
if ($LASTEXITCODE -ne 0 -or $memoryLines.Count -ne 1 -or $memoryLines[0] -notmatch '^\s*(\d+)\s*$') { throw "Could not obtain one GPU memory reading." }
if ([int]$Matches[1] -gt [int]$job.gpu_guard.maximum_existing_memory_mib) { throw "GPU preflight blocked by existing memory allocation." }
$computeApps = @(& nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader,nounits 2>$null | Where-Object { $_.Trim() })
if ([bool]$job.gpu_guard.require_no_compute_applications -and $computeApps.Count -gt 0) { throw "GPU preflight blocked by existing compute applications." }

$outputRoot = (& $PythonExecutable $feedbackRunner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve feedback output root." }
$childArguments = if ($Mode -eq "Train") {
  @($runner, "train", "--job", $jobPath, "--authorization", $authorizationPath)
} else {
  if (-not $Adapter) { throw "Evaluate requires -Adapter." }
  @($runner, "evaluate", "--job", $jobPath, "--authorization", $authorizationPath, "--adapter", [IO.Path]::GetFullPath($Adapter))
}
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($childArguments) -Compress)))
$wrapperRoot = Join-Path $outputRoot "wrapper"
$attemptDirectory = Join-Path $wrapperRoot $receipt.attempt_id
$resourceSummary = Join-Path $attemptDirectory "resource_summary.json"
$cleanupSummary = Join-Path $attemptDirectory "cleanup_summary.json"
$executionSummary = Join-Path $attemptDirectory "captain_rowan_execution_summary.json"
$wrapperExit = 125
$cleanupExit = 125
try {
  & $wrapper -Executable $PythonExecutable -ArgumentsBase64 $encoded -RunId $receipt.run_id -AttemptId $receipt.attempt_id -OutputDirectory $wrapperRoot -MemoryMB ([int]$job.resources.ram_mb) -CpuPercent ([int]$job.resources.cpu_pct) -IoMBPerSecond ([int]$job.resources.io_mb_s) -TimeoutSeconds ([int]$job.resources.timeout_seconds)
  $wrapperExit = $LASTEXITCODE
} finally {
  if (Test-Path -LiteralPath $attemptDirectory) {
    & $cleanup -AttemptDirectory $attemptDirectory
    $cleanupExit = $LASTEXITCODE
    if ((Test-Path -LiteralPath $resourceSummary) -and (Test-Path -LiteralPath $cleanupSummary)) {
      & $PythonExecutable $runner finalize --job $jobPath --resource-summary $resourceSummary --cleanup-summary $cleanupSummary --output $executionSummary
    }
  }
}
if ($wrapperExit -ne 0) { exit $wrapperExit }
if ($cleanupExit -ne 0) { exit 126 }
