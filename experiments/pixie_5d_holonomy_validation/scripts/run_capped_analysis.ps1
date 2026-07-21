param(
  [Parameter(Mandatory = $true)][string]$RunId,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$protocol = Get-Content -LiteralPath (Join-Path $experimentRoot "protocol.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$launcher = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.path))
$ownedGate = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.owned_process_gate_path))
if ((Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.sha256) {
  throw "Bounded launcher hash differs from the frozen protocol."
}
if ((Get-FileHash -LiteralPath $ownedGate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $protocol.bounded_launcher.owned_process_gate_sha256) {
  throw "Owned-process gate hash differs from the frozen protocol."
}
$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve the configured output root." }
$arguments = @($runner, "analyze", "--run-id", $RunId)
$argumentsBase64 = [Convert]::ToBase64String(
  [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($arguments) -Compress))
)
& $launcher `
  -Executable $PythonExecutable `
  -ArgumentsBase64 $argumentsBase64 `
  -RunId "$RunId-analysis" `
  -OutputDirectory (Join-Path $outputRoot "wrapper") `
  -MemoryGB 2 `
  -CpuPercent 50 `
  -IoMBPerSecond 50 `
  -TimeoutMinutes 5
