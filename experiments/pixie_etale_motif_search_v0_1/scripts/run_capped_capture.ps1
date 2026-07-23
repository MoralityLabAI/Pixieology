param(
  [Parameter(Mandatory = $true)][ValidateSet("Shard", "Capture", "Intervention")][string]$Mode,
  [Parameter(Mandatory = $true)][string]$Authorization,
  [int]$ChunkIndex = -1,
  [string]$InterventionPlan = "",
  [int]$TaskIndex = -1,
  [ValidateRange(1, 8)][int]$TaskCount = 4,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocolPath = Join-Path $experimentRoot "protocol.json"
$authorizationPath = [IO.Path]::GetFullPath($Authorization)

& $PythonExecutable $runner authorization-check --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "Motif-search authorization validation failed." }
& $PythonExecutable $runner verify
if ($LASTEXITCODE -ne 0) { throw "Motif-search frozen-input verification failed." }

$protocol = Get-Content -LiteralPath $protocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.underlying_job_wrapper))
$invoker = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.owned_process_gate))
$cleanup = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.cleanup))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.underlying_job_wrapper_sha256) {
  throw "Underlying Job Object wrapper differs from the frozen protocol."
}
if ((Get-FileHash -LiteralPath $invoker -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.owned_process_gate_sha256) {
  throw "Owned-process gate differs from the frozen protocol."
}
if ((Get-FileHash -LiteralPath $cleanup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.cleanup_sha256) {
  throw "Cleanup script differs from the frozen protocol."
}

if ($Mode -in @("Capture", "Intervention")) {
  if ($Mode -eq "Capture" -and ($ChunkIndex -lt 0 -or $ChunkIndex -gt 5)) { throw "ChunkIndex must be 0..5." }
  if ($Mode -eq "Intervention" -and (-not $InterventionPlan -or $TaskIndex -lt 0)) {
    throw "InterventionPlan and a non-negative TaskIndex are required."
  }
  if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    throw "nvidia-smi is required for the fail-closed GPU-idle preflight."
  }
  $memoryLines = @(& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null)
  if ($LASTEXITCODE -ne 0 -or $memoryLines.Count -ne 1 -or $memoryLines[0] -notmatch '^\s*(\d+)\s*$') {
    throw "Could not obtain an unambiguous single-GPU memory reading."
  }
  if ([int]$Matches[1] -gt [int]$protocol.resources.gpu_preflight.maximum_existing_memory_mib) {
    throw "GPU preflight blocked by existing memory allocation."
  }
  $computeApps = @(& nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader,nounits 2>$null | Where-Object { $_.Trim() })
  if ([bool]$protocol.resources.gpu_preflight.require_no_compute_applications -and $computeApps.Count -gt 0) {
    throw "GPU preflight blocked by existing compute applications: $($computeApps -join '; ')"
  }
}

$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve motif output root." }
$arguments = if ($Mode -eq "Shard") {
  @($runner, "shard-model", "--authorization", $authorizationPath)
} elseif ($Mode -eq "Capture") {
  @($runner, "capture", "--authorization", $authorizationPath, "--chunk-index", [string]$ChunkIndex)
} else {
  $resolvedPlan = [IO.Path]::GetFullPath($InterventionPlan)
  @($runner, "capture-intervention", "--authorization", $authorizationPath, "--plan", $resolvedPlan, "--task-index", [string]$TaskIndex, "--task-count", [string]$TaskCount)
}
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($arguments) -Compress)))
$wrapperRoot = Join-Path $outputRoot "wrapper"
$attemptDirectory = Join-Path $wrapperRoot $receipt.attempt_id
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
  }
}
if ($wrapperExit -ne 0) { exit $wrapperExit }
if ($cleanupExit -ne 0) { exit 126 }
