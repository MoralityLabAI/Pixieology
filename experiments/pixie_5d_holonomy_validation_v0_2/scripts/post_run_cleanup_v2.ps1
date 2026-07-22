param(
  [Parameter(Mandatory = $true)][string]$AttemptDirectory
)

$ErrorActionPreference = "Stop"
$AttemptDirectory = [IO.Path]::GetFullPath($AttemptDirectory)
$pidPath = Join-Path $AttemptDirectory "owned_pids.json"
$summaryPath = Join-Path $AttemptDirectory "resource_summary.json"
$outputPath = Join-Path $AttemptDirectory "cleanup_summary.json"

function Get-MemorySnapshot {
  $os = Get-CimInstance Win32_OperatingSystem
  $processes = @(Get-Process -ErrorAction SilentlyContinue | Sort-Object WorkingSet64 -Descending | Select-Object -First 20)
  return [ordered]@{
    total_visible_bytes = [uint64]$os.TotalVisibleMemorySize * 1KB
    free_physical_bytes = [uint64]$os.FreePhysicalMemory * 1KB
    total_virtual_bytes = [uint64]$os.TotalVirtualMemorySize * 1KB
    free_virtual_bytes = [uint64]$os.FreeVirtualMemory * 1KB
    top_processes = @($processes | ForEach-Object {
      [ordered]@{
        pid = $_.Id
        name = $_.ProcessName
        working_set_bytes = [uint64]$_.WorkingSet64
        private_bytes = [uint64]$_.PrivateMemorySize64
      }
    })
  }
}

function Get-GpuSnapshot {
  if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    return [ordered]@{ available = $false; gpu = @(); compute_apps = @() }
  }
  $gpu = @(& nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>$null)
  $apps = @(& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>$null)
  return [ordered]@{ available = $true; gpu = $gpu; compute_apps = $apps }
}

$memoryBefore = Get-MemorySnapshot
$gpuBefore = Get-GpuSnapshot
$owned = @()
$ownedIds = New-Object System.Collections.Generic.HashSet[int]
if (Test-Path -LiteralPath $pidPath) {
  $receipt = Get-Content -LiteralPath $pidPath -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($processId in @($receipt.owned_pids)) { [void]$ownedIds.Add([int]$processId) }
}
foreach ($processId in $ownedIds) {
  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  $owned += [ordered]@{
    pid = $processId
    lingering = $null -ne $process
    name = if ($process) { $process.ProcessName } else { $null }
    working_set_bytes = if ($process) { [uint64]$process.WorkingSet64 } else { 0 }
  }
}
$ownedGpu = @()
foreach ($line in @($gpuBefore.compute_apps)) {
  if ($line -match '^\s*(\d+)\s*,') {
    $gpuPid = [int]$Matches[1]
    if ($ownedIds.Contains($gpuPid)) { $ownedGpu += $line }
  }
}
$wslRunning = @()
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
  $wslRunning = @(& wsl.exe --list --running --quiet 2>$null | Where-Object { $_.Trim() })
}
[GC]::Collect()
[GC]::WaitForPendingFinalizers()
Start-Sleep -Milliseconds 250
$memoryAfter = Get-MemorySnapshot
$gpuAfter = Get-GpuSnapshot
$lingering = @($owned | Where-Object { $_.lingering }).Count
$passed = (Test-Path -LiteralPath $summaryPath) -and $lingering -eq 0 -and @($ownedGpu).Count -eq 0
$report = [ordered]@{
  schema = "pixie_post_run_cleanup_v2"
  status = if ($passed) { "PASS" } else { "FAIL" }
  audited_utc = (Get-Date).ToUniversalTime().ToString("o")
  attempt_directory = $AttemptDirectory
  wrapper_summary_exists = Test-Path -LiteralPath $summaryPath
  pid_receipt_exists = Test-Path -LiteralPath $pidPath
  owned_processes = $owned
  lingering_owned_count = $lingering
  owned_gpu_processes = $ownedGpu
  memory_before = $memoryBefore
  memory_after = $memoryAfter
  gpu_before = $gpuBefore
  gpu_after = $gpuAfter
  wsl_running_distributions = $wslRunning
  action = "AUDIT_ONLY; Job Object kill-on-close owns cleanup; no unrelated process or system cache was modified"
}
$temporary = "$outputPath.tmp-$PID"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -LiteralPath $temporary -Destination $outputPath -Force
$report | ConvertTo-Json -Depth 8
if (-not $passed) { exit 2 }
