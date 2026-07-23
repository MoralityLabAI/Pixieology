param(
  [Parameter(Mandatory = $true)][ValidateSet("Train", "Evaluate")][string]$Mode,
  [Parameter(Mandatory = $true)][string]$Job,
  [Parameter(Mandatory = $true)][string]$Authorization,
  [string]$Adapter = "",
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocolPath = Join-Path $experimentRoot "protocol.json"
$jobPath = [IO.Path]::GetFullPath($Job)
$authorizationPath = [IO.Path]::GetFullPath($Authorization)

& $PythonExecutable $runner verify
if ($LASTEXITCODE -ne 0) { throw "Feedback-loop frozen-input verification failed." }
& $PythonExecutable $runner authorization-check --job $jobPath --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "Feedback-loop authorization validation failed." }

$protocol = Get-Content -LiteralPath $protocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.underlying_job_wrapper))
$cleanup = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.cleanup))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.underlying_job_wrapper_sha256) {
  throw "Underlying Job Object wrapper differs from the frozen feedback protocol."
}
if ((Get-FileHash -LiteralPath $cleanup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.cleanup_sha256) {
  throw "Cleanup script differs from the frozen feedback protocol."
}
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
  throw "nvidia-smi is required for the fail-closed GPU preflight."
}
$memoryLines = @(& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null)
if ($LASTEXITCODE -ne 0 -or $memoryLines.Count -ne 1 -or $memoryLines[0] -notmatch '^\s*(\d+)\s*$') {
  throw "Could not obtain an unambiguous single-GPU memory reading."
}
if ([int]$Matches[1] -gt [int]$protocol.resources.gpu.maximum_existing_memory_mib) {
  throw "GPU preflight blocked by existing memory allocation."
}
$computeApps = @(& nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader,nounits 2>$null | Where-Object { $_.Trim() })
if ([bool]$protocol.resources.gpu.require_no_compute_applications -and $computeApps.Count -gt 0) {
  throw "GPU preflight blocked by existing compute applications: $($computeApps -join '; ')"
}

$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve feedback output root." }
$childArguments = if ($Mode -eq "Train") {
  @($runner, "train", "--job", $jobPath, "--authorization", $authorizationPath)
} else {
  $values = @($runner, "evaluate", "--job", $jobPath, "--authorization", $authorizationPath)
  if ($Adapter) { $values += @("--adapter", [IO.Path]::GetFullPath($Adapter)) }
  $values
}
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($childArguments) -Compress)))
$wrapperRoot = Join-Path $outputRoot "wrapper"
$attemptDirectory = Join-Path $wrapperRoot $receipt.attempt_id
$resourceSummary = Join-Path $attemptDirectory "resource_summary.json"
$cleanupSummary = Join-Path $attemptDirectory "cleanup_summary.json"
$executionSummary = Join-Path $attemptDirectory "feedback_execution_summary.json"
$wrapperExit = 125
$cleanupExit = 125
try {
  & $wrapper `
    -Executable $PythonExecutable `
    -ArgumentsBase64 $encoded `
    -RunId $receipt.run_id `
    -AttemptId $receipt.attempt_id `
    -OutputDirectory $wrapperRoot `
    -MemoryMB 2048 `
    -CpuPercent 50 `
    -IoMBPerSecond 50 `
    -TimeoutSeconds 1800
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
