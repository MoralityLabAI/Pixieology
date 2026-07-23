param(
  [Parameter(Mandatory = $true)][string]$Authorization,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocolPath = Join-Path $experimentRoot "protocol.json"
$jobPath = Join-Path $experimentRoot "proposed_job.json"
$authorizationPath = [IO.Path]::GetFullPath($Authorization)

& $PythonExecutable $runner verify
if ($LASTEXITCODE -ne 0) { throw "Capture v0.2 frozen-input verification failed." }
& $PythonExecutable $runner authorization-check --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "Capture v0.2 authorization validation failed." }

$protocol = Get-Content -LiteralPath $protocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.underlying_job_wrapper))
$cleanup = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.cleanup))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.underlying_job_wrapper_sha256) {
  throw "Underlying Job Object wrapper differs from capture v0.2."
}
if ((Get-FileHash -LiteralPath $cleanup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.cleanup_sha256) {
  throw "Cleanup script differs from capture v0.2."
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
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve capture v0.2 output root." }
$childArguments = @($runner, "capture", "--authorization", $authorizationPath)
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($childArguments) -Compress)))
$wrapperRoot = Join-Path $outputRoot "wrapper_v0_2"
$attemptDirectory = Join-Path $wrapperRoot $receipt.attempt_id
$resourceSummary = Join-Path $attemptDirectory "resource_summary.json"
$cleanupSummary = Join-Path $attemptDirectory "cleanup_summary.json"
$executionSummary = Join-Path $attemptDirectory "capture_execution_summary.json"
$wrapperExit = 125
$cleanupExit = 125
try {
  & $wrapper `
    -Executable $PythonExecutable `
    -ArgumentsBase64 $encoded `
    -RunId $receipt.run_id `
    -AttemptId $receipt.attempt_id `
    -OutputDirectory $wrapperRoot `
    -MemoryMB 6144 `
    -CpuPercent 50 `
    -IoMBPerSecond 250 `
    -TimeoutSeconds 1800
  $wrapperExit = $LASTEXITCODE
} finally {
  if (Test-Path -LiteralPath $attemptDirectory) {
    & $cleanup -AttemptDirectory $attemptDirectory
    $cleanupExit = $LASTEXITCODE
    if ($cleanupExit -ne 0 -and (Test-Path -LiteralPath $cleanupSummary)) {
      $initialCleanup = Join-Path $attemptDirectory "cleanup_summary.initial.json"
      Copy-Item -LiteralPath $cleanupSummary -Destination $initialCleanup -Force
      Start-Sleep -Seconds 1
      & $cleanup -AttemptDirectory $attemptDirectory
      $cleanupExit = $LASTEXITCODE
    }
    if ((Test-Path -LiteralPath $resourceSummary) -and (Test-Path -LiteralPath $cleanupSummary)) {
      & $PythonExecutable $runner finalize `
        --resource-summary $resourceSummary `
        --cleanup-summary $cleanupSummary `
        --output $executionSummary
    }
  }
}
if ($wrapperExit -ne 0) { exit $wrapperExit }
if ($cleanupExit -ne 0) { exit 126 }
