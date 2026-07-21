param(
  [Parameter(Mandatory = $true)][string]$Authorization,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$repoRoot = [IO.Path]::GetFullPath((Join-Path $experimentRoot "..\.."))
$runner = Join-Path $experimentRoot "run.py"
$protocolPath = Join-Path $experimentRoot "protocol.json"
$authorizationPath = [IO.Path]::GetFullPath($Authorization)

& $PythonExecutable $runner authorization-check --authorization $authorizationPath
if ($LASTEXITCODE -ne 0) { throw "Authorization receipt validation failed." }

$protocol = Get-Content -LiteralPath $protocolPath -Raw -Encoding UTF8 | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$launcher = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.path))
$ownedGate = [IO.Path]::GetFullPath((Join-Path $experimentRoot $protocol.bounded_launcher.owned_process_gate_path))
$launcherHash = (Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant()
$ownedGateHash = (Get-FileHash -LiteralPath $ownedGate -Algorithm SHA256).Hash.ToLowerInvariant()
if ($launcherHash -ne $protocol.bounded_launcher.sha256) {
  throw "Bounded launcher hash differs from the frozen protocol."
}
if ($ownedGateHash -ne $protocol.bounded_launcher.owned_process_gate_sha256) {
  throw "Owned-process gate hash differs from the frozen protocol."
}

$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve the configured output root." }
$wrapperOutput = Join-Path $outputRoot "wrapper"
$arguments = @($runner, "capture", "--authorization", $authorizationPath)
$argumentsJson = ConvertTo-Json @($arguments) -Compress
$argumentsBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentsJson))

$oldValues = @{}
$capVariables = @(
  "PIXIE_CAP_RAM_MB",
  "PIXIE_CAP_CPU_PCT",
  "PIXIE_CAP_IO_MB_S",
  "PIXIE_CAP_TIMEOUT_SECONDS",
  "PIXIE_CAP_WRAPPER_SHA256"
)
foreach ($name in $capVariables) { $oldValues[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
try {
  $env:PIXIE_CAP_RAM_MB = [string]$receipt.caps.ram_mb
  $env:PIXIE_CAP_CPU_PCT = [string]$receipt.caps.cpu_pct
  $env:PIXIE_CAP_IO_MB_S = [string]$receipt.caps.io_mb_s
  $env:PIXIE_CAP_TIMEOUT_SECONDS = [string]$receipt.caps.timeout_seconds
  $env:PIXIE_CAP_WRAPPER_SHA256 = $launcherHash
  & $launcher `
    -Executable $PythonExecutable `
    -ArgumentsBase64 $argumentsBase64 `
    -RunId $receipt.run_id `
    -OutputDirectory $wrapperOutput `
    -MemoryGB 6 `
    -CpuPercent 50 `
    -IoMBPerSecond 250 `
    -TimeoutMinutes 30
  if ($LASTEXITCODE -ne 0) { throw "Capped capture failed with exit code $LASTEXITCODE." }
} finally {
  foreach ($name in $capVariables) {
    [Environment]::SetEnvironmentVariable($name, $oldValues[$name], "Process")
  }
}
