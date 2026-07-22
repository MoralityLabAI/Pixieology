param([string]$PythonExecutable = "python")

$ErrorActionPreference = "Stop"
$experimentRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$runner = Join-Path $experimentRoot "run.py"
$wrapper = Join-Path $PSScriptRoot "run_capped_v2.ps1"
$probe = Join-Path $PSScriptRoot "cap_probe.py"
$outputRoot = (& $PythonExecutable $runner output-root).Trim()
if ($LASTEXITCODE -ne 0 -or -not $outputRoot) { throw "Could not resolve configured v0.2 output root." }
$attemptId = "cap-self-test-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ'))"
$arguments = @($probe, "--target-mb", "384", "--chunk-mb", "16")
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($arguments) -Compress)))

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $wrapper `
  -Executable $PythonExecutable `
  -ArgumentsBase64 $encoded `
  -RunId "pixie-v02-cap-self-test" `
  -AttemptId $attemptId `
  -OutputDirectory (Join-Path $outputRoot "cap_self_test") `
  -MemoryMB 128 `
  -CpuPercent 50 `
  -IoMBPerSecond 50 `
  -TimeoutSeconds 60 `
  -DiagnosticOsCapOnly
$childExit = $LASTEXITCODE
$summaryPath = Join-Path (Join-Path (Join-Path $outputRoot "cap_self_test") $attemptId) "resource_summary.json"
if (-not (Test-Path -LiteralPath $summaryPath)) { throw "Self-test wrapper produced no resource summary." }
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$stdout = Get-Content -LiteralPath $summary.stdout -Raw -ErrorAction SilentlyContinue
$passed = (
  $childExit -ne 0 -and
  $summary.status -eq "aborted" -and
  $summary.abort_reason -match "memory" -and
  $summary.abort_reason -eq "os_memory_cap_termination" -and
  $summary.timed_out -eq $false -and
  $stdout -notmatch "CAP_PROBE_UNEXPECTEDLY_COMPLETED"
)
$receipt = [ordered]@{
  schema = "pixie_cap_self_test_v2"
  status = if ($passed) { "PASS" } else { "FAIL" }
  attempt_id = $attemptId
  wrapper_exit_code = $childExit
  abort_reason = $summary.abort_reason
  configured_memory_mb = $summary.caps.memory_mb
  peak_tree_private_bytes = $summary.peak_tree_private_bytes
  peak_job_memory_bytes = $summary.peak_job_memory_bytes
  peak_process_memory_bytes = $summary.peak_process_memory_bytes
  timed_out = $summary.timed_out
  unexpected_completion_marker = [bool]($stdout -match "CAP_PROBE_UNEXPECTEDLY_COMPLETED")
  resource_summary = $summaryPath
}
$receiptPath = Join-Path (Split-Path -Parent $summaryPath) "self_test_receipt.json"
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
$receipt | ConvertTo-Json -Depth 5
if (-not $passed) { exit 1 }
