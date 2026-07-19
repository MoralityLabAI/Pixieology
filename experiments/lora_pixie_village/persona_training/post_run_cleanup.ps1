param(
  [Parameter(Mandatory = $true)][string]$PidFile,
  [Parameter(Mandatory = $true)][string]$SummaryPath,
  [string]$RunId = "manual"
)

$ErrorActionPreference = "Continue"
$owned = @()
if (Test-Path -LiteralPath $PidFile) {
  $payload = Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
  $owned = @($payload.owned_pids)
}
$lingering = @()
foreach ($ownedPid in $owned) {
  if (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue) { $lingering += $ownedPid }
}
$gpu = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  @(& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>$null)
} else { @() }
$os = Get-CimInstance Win32_OperatingSystem
$summary = [ordered]@{
  schema_version = 1
  run_id = $RunId
  utc = (Get-Date).ToUniversalTime().ToString("o")
  owned_pids = $owned
  lingering_owned_pids = $lingering
  gpu_compute_processes = $gpu
  memory = [ordered]@{
    total_bytes = [uint64]$os.TotalVisibleMemorySize * 1KB
    free_bytes = [uint64]$os.FreePhysicalMemory * 1KB
  }
  cleanup_passed = ($lingering.Count -eq 0)
  note = "Only owned PIDs were inspected; no unrelated process or global cache was terminated."
}
New-Item -ItemType Directory -Path (Split-Path -Parent $SummaryPath) -Force | Out-Null
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
$summary | ConvertTo-Json -Depth 6
