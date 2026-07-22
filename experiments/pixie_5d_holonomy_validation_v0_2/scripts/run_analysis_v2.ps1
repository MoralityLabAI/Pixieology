param(
  [string]$PythonExecutable = "python",
  [string]$AttemptId = ""
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocol = Get-Content -LiteralPath (Join-Path $experimentRoot "protocol.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.path))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.sha256) {
  throw "v0.2 bounded launcher differs from the frozen protocol."
}
& $PythonExecutable $runner verify
if ($LASTEXITCODE -ne 0) { throw "v0.2 frozen-lineage verification failed." }
$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve configured v0.2 output root." }
if (-not $AttemptId) { $AttemptId = "analysis-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ") }
$arguments = @($runner, "analyze")
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($arguments) -Compress)))
$attemptDirectory = Join-Path (Join-Path $outputRoot "wrapper") $AttemptId
$wrapperExit = 125
$cleanupExit = 125
try {
  & $wrapper `
    -Executable $PythonExecutable `
    -ArgumentsBase64 $encoded `
    -RunId ($protocol.continuation.continuation_id + "-analysis") `
    -AttemptId $AttemptId `
    -OutputDirectory (Join-Path $outputRoot "wrapper") `
    -MemoryMB 2048 `
    -CpuPercent 50 `
    -IoMBPerSecond 50 `
    -TimeoutSeconds 600
  $wrapperExit = $LASTEXITCODE
} finally {
  if (Test-Path -LiteralPath $attemptDirectory) {
    & (Join-Path $PSScriptRoot "post_run_cleanup_v2.ps1") -AttemptDirectory $attemptDirectory
    $cleanupExit = $LASTEXITCODE
  }
}
if ($wrapperExit -ne 0) { exit $wrapperExit }
if ($cleanupExit -ne 0) { exit 126 }
