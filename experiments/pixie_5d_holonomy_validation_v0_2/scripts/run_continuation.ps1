param(
  [Parameter(Mandatory = $true)][string]$Authorization,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocolPath = Join-Path $experimentRoot "protocol.json"
$authorizationPath = [IO.Path]::GetFullPath($Authorization)
& $PythonExecutable $runner authorization-check --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "v0.2 authorization validation failed." }
& $PythonExecutable $runner verify
if ($LASTEXITCODE -ne 0) { throw "v0.2 frozen-lineage verification failed." }

$protocol = Get-Content -LiteralPath $protocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$gpuPreflight = $protocol.resources.gpu_preflight
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
  throw "nvidia-smi is required for the fail-closed GPU-idle preflight."
}
$memoryLines = @(& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null)
if ($LASTEXITCODE -ne 0 -or $memoryLines.Count -ne 1 -or $memoryLines[0] -notmatch '^\s*(\d+)\s*$') {
  throw "Could not obtain an unambiguous single-GPU memory reading."
}
$existingMemoryMiB = [int]$Matches[1]
$computeApps = @(& nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader,nounits 2>$null | Where-Object { $_.Trim() })
if ($existingMemoryMiB -gt [int]$gpuPreflight.maximum_existing_memory_mib) {
  throw "GPU preflight blocked: $existingMemoryMiB MiB already used; maximum is $($gpuPreflight.maximum_existing_memory_mib) MiB."
}
if ([bool]$gpuPreflight.require_no_compute_applications -and $computeApps.Count -gt 0) {
  throw "GPU preflight blocked by existing compute applications: $($computeApps -join '; ')"
}
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.path))
$invoker = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.owned_process_gate_path))
$wrapperHash = (Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant()
$invokerHash = (Get-FileHash -LiteralPath $invoker -Algorithm SHA256).Hash.ToLowerInvariant()
if ($wrapperHash -ne $protocol.bounded_launcher.sha256 -or $invokerHash -ne $protocol.bounded_launcher.owned_process_gate_sha256) {
  throw "v0.2 launcher or invoker differs from the frozen protocol."
}
$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve configured v0.2 output root." }
$arguments = @($runner, "continue-context3", "--authorization", $authorizationPath)
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($arguments) -Compress)))
$oldHash = $env:PIXIE_CAP_WRAPPER_SHA256
$attemptDirectory = Join-Path (Join-Path $outputRoot "wrapper") $receipt.attempt_id
$cleanupScript = Join-Path $PSScriptRoot "post_run_cleanup_v2.ps1"
$wrapperExit = 125
$cleanupExit = 125
try {
  $env:PIXIE_CAP_WRAPPER_SHA256 = $wrapperHash
  & $wrapper `
    -Executable $PythonExecutable `
    -ArgumentsBase64 $encoded `
    -RunId $receipt.continuation_id `
    -AttemptId $receipt.attempt_id `
    -OutputDirectory (Join-Path $outputRoot "wrapper") `
    -MemoryMB 6144 `
    -CpuPercent 50 `
    -IoMBPerSecond 250 `
    -TimeoutSeconds 1800
  $wrapperExit = $LASTEXITCODE
} finally {
  $env:PIXIE_CAP_WRAPPER_SHA256 = $oldHash
  if (Test-Path -LiteralPath $attemptDirectory) {
    & $cleanupScript -AttemptDirectory $attemptDirectory
    $cleanupExit = $LASTEXITCODE
  }
}
if ($wrapperExit -ne 0) { exit $wrapperExit }
if ($cleanupExit -ne 0) { exit 126 }
