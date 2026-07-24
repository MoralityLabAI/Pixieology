param(
  [Parameter(Mandatory = $true)][string]$Authorization,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocolPath = Join-Path $experimentRoot "protocol.json"
$authorizationPath = [IO.Path]::GetFullPath($Authorization)

& $PythonExecutable $runner verify
if ($LASTEXITCODE -ne 0) { throw "Quantization canary frozen verification failed." }
& $PythonExecutable $runner authorization-check --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "Quantization canary authorization validation failed." }

$protocol = Get-Content -LiteralPath $protocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.underlying_job_wrapper))
$cleanup = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.cleanup))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.underlying_job_wrapper_sha256) {
  throw "Underlying Job Object wrapper differs from the canary protocol."
}
if ((Get-FileHash -LiteralPath $cleanup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.cleanup_sha256) {
  throw "Cleanup script differs from the canary protocol."
}

if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
  throw "nvidia-smi is required for the fail-closed GPU preflight."
}
$profileLines = @(& nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap,memory.used,utilization.gpu --format=csv,noheader,nounits 2>$null)
if ($LASTEXITCODE -ne 0 -or $profileLines.Count -ne 1) {
  throw "Could not obtain an unambiguous single-GPU profile."
}
$fields = @($profileLines[0] -split "," | ForEach-Object { $_.Trim() })
if ($fields.Count -ne 6) { throw "GPU profile field count differs from protocol." }
if ($fields[0] -ne $protocol.runtime.gpu_name -or
    $fields[1] -ne $protocol.runtime.nvidia_driver -or
    [int]$fields[2] -ne [int]$protocol.runtime.gpu_memory_total_mib -or
    $fields[3] -ne $protocol.runtime.gpu_compute_capability) {
  throw "GPU profile differs from the exact canary runtime."
}
if ([int]$fields[4] -gt [int]$protocol.resources.gpu.maximum_existing_memory_mib) {
  throw "GPU preflight blocked by existing memory allocation."
}
if ([int]$fields[5] -gt [int]$protocol.resources.gpu.maximum_existing_utilization_pct) {
  throw "GPU preflight blocked by existing utilization."
}
$computeApps = @(& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>$null | Where-Object { $_.Trim() })
$allowed = $protocol.resources.gpu.allowed_preexisting_compute_application
if ($computeApps.Count -gt [int]$allowed.maximum_count) {
  throw "GPU preflight blocked by too many registered applications: $($computeApps -join '; ')"
}
foreach ($line in $computeApps) {
  $application = @($line -split "," | ForEach-Object { $_.Trim() })
  if ($application.Count -ne 3) {
    throw "GPU application profile is ambiguous: $line"
  }
  $processName = $application[1]
  if ([IO.Path]::GetFileName($processName) -ine [string]$allowed.executable_basename -or
      -not $processName.EndsWith([string]$allowed.required_path_suffix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "GPU preflight blocked by an unapproved application: $line"
  }
  if ($application[2] -eq '[N/A]' -and -not [bool]$allowed.used_memory_may_be_unavailable) {
    throw "GPU application memory is unavailable but the protocol forbids that state."
  }
}

$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve canary output root." }
$childArguments = @($runner, "canary", "--authorization", $authorizationPath)
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($childArguments) -Compress)))
$wrapperRoot = Join-Path $outputRoot "wrapper"
$attemptDirectory = Join-Path $wrapperRoot $receipt.attempt_id
$resourceSummary = Join-Path $attemptDirectory "resource_summary.json"
$cleanupSummary = Join-Path $attemptDirectory "cleanup_summary.json"
$executionSummary = Join-Path $attemptDirectory "canary_execution_summary.json"
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
    -TimeoutSeconds 600
  $wrapperExit = $LASTEXITCODE
} finally {
  if (Test-Path -LiteralPath $attemptDirectory) {
    & $cleanup -AttemptDirectory $attemptDirectory
    $cleanupExit = $LASTEXITCODE
    $cleanupAttempts = 1
    while ($cleanupExit -ne 0 -and $cleanupAttempts -lt 5) {
      $initialCleanup = Join-Path $attemptDirectory "cleanup_summary.attempt-$cleanupAttempts.json"
      if (Test-Path -LiteralPath $cleanupSummary) {
        Copy-Item -LiteralPath $cleanupSummary -Destination $initialCleanup -Force
      }
      Start-Sleep -Seconds 1
      & $cleanup -AttemptDirectory $attemptDirectory
      $cleanupExit = $LASTEXITCODE
      $cleanupAttempts += 1
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
