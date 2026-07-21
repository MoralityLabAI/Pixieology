param(
  [Parameter(Mandatory = $true)][string]$RunId,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve the configured output root." }
$pidReceipt = Join-Path (Join-Path $outputRoot "wrapper") "$RunId.pids.json"
$wrapperSummary = Join-Path (Join-Path $outputRoot "wrapper") "$RunId.resource_summary.json"
$captureSummary = Join-Path (Join-Path (Join-Path $outputRoot "capture") $RunId) "summary.json"

$owned = @()
if (Test-Path -LiteralPath $pidReceipt) {
  $receipt = Get-Content -LiteralPath $pidReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($processId in @($receipt.owned_pids)) {
    $process = Get-Process -Id ([int]$processId) -ErrorAction SilentlyContinue
    $owned += [ordered]@{
      pid = [int]$processId
      lingering = $null -ne $process
      name = if ($process) { $process.ProcessName } else { $null }
      start_time_utc = if ($process) { $process.StartTime.ToUniversalTime().ToString("o") } else { $null }
    }
  }
}
$gpu = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  (& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>$null)
} else { $null }
$report = [ordered]@{
  schema = "pixie_5d_post_run_cleanup_audit_v1"
  run_id = $RunId
  audited_utc = (Get-Date).ToUniversalTime().ToString("o")
  capture_summary_exists = Test-Path -LiteralPath $captureSummary
  wrapper_summary_exists = Test-Path -LiteralPath $wrapperSummary
  pid_receipt_exists = Test-Path -LiteralPath $pidReceipt
  owned_processes = $owned
  lingering_owned_count = @($owned | Where-Object { $_.lingering }).Count
  gpu_compute_processes = @($gpu)
  action = "AUDIT_ONLY; the Job Object owns termination and no unrelated process is touched"
}
$auditPath = Join-Path (Join-Path $outputRoot "wrapper") "$RunId.cleanup_audit.json"
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $auditPath -Encoding UTF8
$report | ConvertTo-Json -Depth 6
if ($report.lingering_owned_count -gt 0) {
  Write-Error "A recorded run-owned process is still present. Do not kill by name; inspect $auditPath."
  exit 2
}
