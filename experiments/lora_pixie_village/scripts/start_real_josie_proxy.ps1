param(
  [string]$RunId = "josie-live-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
  [int]$Port = 8081,
  [int]$MaxRuntimeMinutes = 30
)

$ErrorActionPreference = "Stop"
if ($MaxRuntimeMinutes -lt 1 -or $MaxRuntimeMinutes -gt 30) {
  throw "MaxRuntimeMinutes must be between 1 and 30."
}
if ($Port -lt 1 -or $Port -gt 65535) { throw "Port is invalid." }

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$configPath = Join-Path $repo "pixieology.config.json"
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$rawPaths = @{}
foreach ($property in $config.paths.PSObject.Properties) { $rawPaths[$property.Name] = [string]$property.Value }
$resolved = @{}

function Resolve-PixiePath([string]$Key) {
  if ($resolved.ContainsKey($Key)) { return [string]$resolved[$Key] }
  if (-not $rawPaths.ContainsKey($Key)) { throw "Missing config path: $Key" }
  $value = [string]$rawPaths[$Key]
  foreach ($candidate in $rawPaths.Keys) {
    $marker = '${' + $candidate + '}'
    if ($value.Contains($marker)) {
      $value = $value.Replace($marker, (Resolve-PixiePath $candidate))
    }
  }
  if (-not [IO.Path]::IsPathRooted($value)) { $value = Join-Path $repo $value }
  $resolved[$Key] = [IO.Path]::GetFullPath($value)
  return [string]$resolved[$Key]
}

$runtimeRoot = Resolve-PixiePath "lora_pixie_village_runtime"
$agentConfig = Join-Path $runtimeRoot "live_configs\$RunId.agents.json"
$python = (Get-Command python).Source
$writeConfig = Join-Path $PSScriptRoot "write_josie_agents.py"
& $python $writeConfig --config $configPath --run-id $RunId --base-url "http://127.0.0.1:$Port" --out $agentConfig
if ($LASTEXITCODE -ne 0) { throw "Failed to write the resolved agent config." }

$proxyScript = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\dual_lora_proxy.py"))
$childArguments = @(
  $proxyScript,
  "--config", $configPath,
  "--run-id", $RunId,
  "--port", [string]$Port,
  "--ctx-size", "1536",
  "--threads", "4",
  "--gpu-layers", "0",
  "--startup-timeout", "120",
  "--max-runtime-seconds", [string]($MaxRuntimeMinutes * 60)
)
$argumentJson = ConvertTo-Json $childArguments -Compress
$argumentBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentJson))
$capWrapper = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\persona_training\run_capped_strict.ps1"))
$capOutput = Join-Path $runtimeRoot "caps"

Write-Host "Resolved agent config: $agentConfig"
$wrapperStdout = Join-Path $capOutput "$RunId.launcher.stdout.log"
$wrapperStderr = Join-Path $capOutput "$RunId.launcher.stderr.log"
New-Item -ItemType Directory -Path $capOutput -Force | Out-Null
$wrapperArguments = @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $capWrapper,
  "-Executable", $python,
  "-ArgumentsBase64", $argumentBase64,
  "-RunId", $RunId,
  "-OutputDirectory", $capOutput,
  "-MemoryGB", "2",
  "-CpuPercent", "50",
  "-IoMBPerSecond", "50",
  "-TimeoutMinutes", [string]$MaxRuntimeMinutes
)
$capProcess = Start-Process `
  -FilePath "powershell.exe" `
  -ArgumentList $wrapperArguments `
  -PassThru `
  -WindowStyle Hidden `
  -RedirectStandardOutput $wrapperStdout `
  -RedirectStandardError $wrapperStderr

$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
  if ($capProcess.HasExited) {
    throw "The capped proxy exited during startup. See $wrapperStderr and $capOutput."
  }
  try {
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 3
    $ids = @($models.data | ForEach-Object { [string]$_.id })
    if ($ids -contains "companion-local" -and $ids -contains "storyworld-local") {
      $ready = $true
      break
    }
  } catch {
    # Expected while the bounded backend loads.
  }
  Start-Sleep -Milliseconds 500
}
if (-not $ready) {
  throw "The capped proxy did not become ready within 120 seconds. It remains bounded by its timeout; see $capOutput."
}

Write-Host "READY: two trained LoRA routes at http://127.0.0.1:$Port"
Write-Host "Capped wrapper PID: $($capProcess.Id); automatic stop after $MaxRuntimeMinutes minute(s)."
Write-Host "Use a second terminal:"
Write-Host "python .\experiments\lora_pixie_village\server.py --agents `"$agentConfig`" --require-adapter-attestation"
