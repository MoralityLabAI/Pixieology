param(
  [Parameter(Mandatory = $true)][string[]]$Arguments,
  [Parameter(Mandatory = $true)][string]$RunId,
  [Parameter(Mandatory = $true)][string]$AttemptId,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocol = Get-Content -LiteralPath (Join-Path $experimentRoot "protocol.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$wrapper = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.underlying_job_wrapper))
$cleanup = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.cleanup))
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.underlying_job_wrapper_sha256) {
  throw "Underlying Job Object wrapper differs from the frozen protocol."
}
if ((Get-FileHash -LiteralPath $cleanup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.cleanup_sha256) {
  throw "Cleanup script differs from the frozen protocol."
}
$outputRoot = (& $PythonExecutable $runner output-root).Trim()
$wrapperRoot = Join-Path $outputRoot "analysis_wrapper"
$attemptDirectory = Join-Path $wrapperRoot $AttemptId
$childArguments = @($runner) + @($Arguments)
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($childArguments) -Compress)))
$wrapperExit = 125
$cleanupExit = 125
try {
  & $wrapper `
    -Executable $PythonExecutable `
    -ArgumentsBase64 $encoded `
    -RunId $RunId `
    -AttemptId $AttemptId `
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
  }
}
if ($wrapperExit -ne 0) { exit $wrapperExit }
if ($cleanupExit -ne 0) { exit 126 }
