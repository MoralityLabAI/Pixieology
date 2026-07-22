param(
  [Parameter(Mandatory = $true)][string]$Executable,
  [string[]]$ChildArguments = @(),
  [string]$ArgumentsBase64 = "",
  [Parameter(Mandatory = $true)][string]$RunId,
  [Parameter(Mandatory = $true)][string]$AttemptId,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [int]$MemoryMB = 2048,
  [int]$CpuPercent = 50,
  [int]$IoMBPerSecond = 50,
  [int]$TimeoutSeconds = 300,
  [switch]$DiagnosticOsCapOnly
)

$ErrorActionPreference = "Stop"
if ($MemoryMB -lt 64) { throw "MemoryMB must be at least 64." }
if ($CpuPercent -lt 1 -or $CpuPercent -gt 100) { throw "CpuPercent must be 1..100." }
if ($IoMBPerSecond -lt 1 -or $TimeoutSeconds -lt 1) { throw "I/O and timeout caps must be positive." }
if ($DiagnosticOsCapOnly -and ($RunId -ne "pixie-v02-cap-self-test" -or $MemoryMB -gt 256)) {
  throw "DiagnosticOsCapOnly is restricted to the small destructive cap self-test."
}
if ($ArgumentsBase64) {
  $decoded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ArgumentsBase64))
  $parsed = $decoded | ConvertFrom-Json
  $ChildArguments = @()
  foreach ($item in $parsed) { $ChildArguments += [string]$item }
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$attemptDirectory = Join-Path $OutputDirectory $AttemptId
if (Test-Path -LiteralPath $attemptDirectory) {
  throw "Attempt directory already exists and will not be overwritten: $attemptDirectory"
}
New-Item -ItemType Directory -Path $attemptDirectory -Force | Out-Null
$stdoutPath = Join-Path $attemptDirectory "stdout.log"
$stderrPath = Join-Path $attemptDirectory "stderr.log"
$summaryPath = Join-Path $attemptDirectory "resource_summary.json"
$pidPath = Join-Path $attemptDirectory "owned_pids.json"

if (-not ("PixieJobObjectV2" -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class PixieJobObjectV2 {
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern IntPtr CreateJobObject(IntPtr attributes, string name);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool QueryInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length, out uint returnLength);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool TerminateJobObject(IntPtr job, uint exitCode);
  [DllImport("kernel32.dll", SetLastError = true)]
  public static extern bool CloseHandle(IntPtr handle);
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
  public static extern uint SetIoRateControlInformationJobObject(IntPtr job, ref JOBOBJECT_IO_RATE_CONTROL_INFORMATION info);

  public const int ExtendedLimitInformation = 9;
  public const int CpuRateControlInformation = 15;
  public const uint JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100;
  public const uint JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200;
  public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
  public const uint JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1;
  public const uint JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4;
  public const uint JOB_OBJECT_IO_RATE_CONTROL_ENABLE = 0x1;

  [StructLayout(LayoutKind.Sequential)]
  public struct IO_COUNTERS {
    public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
    public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct BASIC_LIMIT_INFORMATION {
    public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
    public uint LimitFlags;
    public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
    public uint ActiveProcessLimit;
    public long Affinity;
    public uint PriorityClass, SchedulingClass;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct EXTENDED_LIMIT_INFORMATION {
    public BASIC_LIMIT_INFORMATION BasicLimitInformation;
    public IO_COUNTERS IoInfo;
    public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
  }
  [StructLayout(LayoutKind.Sequential)]
  public struct CPU_RATE_CONTROL_INFORMATION { public uint ControlFlags, CpuRate; }
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct JOBOBJECT_IO_RATE_CONTROL_INFORMATION {
    public long MaxIops, MaxBandwidth, ReservationIops;
    [MarshalAs(UnmanagedType.LPWStr)] public string VolumeName;
    public uint BaseIoSize, ControlFlags;
  }
}
'@
}

function Set-JobInformation {
  param([IntPtr]$Job, [int]$Class, [object]$Value)
  $size = [Runtime.InteropServices.Marshal]::SizeOf($Value)
  $pointer = [Runtime.InteropServices.Marshal]::AllocHGlobal($size)
  try {
    [Runtime.InteropServices.Marshal]::StructureToPtr($Value, $pointer, $false)
    if (-not [PixieJobObjectV2]::SetInformationJobObject($Job, $Class, $pointer, [uint32]$size)) {
      throw "SetInformationJobObject($Class) failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
  } finally {
    [Runtime.InteropServices.Marshal]::FreeHGlobal($pointer)
  }
}

function Get-JobExtendedInformation {
  param([IntPtr]$Job)
  $value = New-Object PixieJobObjectV2+EXTENDED_LIMIT_INFORMATION
  $size = [Runtime.InteropServices.Marshal]::SizeOf($value)
  $pointer = [Runtime.InteropServices.Marshal]::AllocHGlobal($size)
  try {
    $returned = [uint32]0
    if (-not [PixieJobObjectV2]::QueryInformationJobObject($Job, [PixieJobObjectV2]::ExtendedLimitInformation, $pointer, [uint32]$size, [ref]$returned)) {
      throw "QueryInformationJobObject failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
    return [Runtime.InteropServices.Marshal]::PtrToStructure($pointer, [type][PixieJobObjectV2+EXTENDED_LIMIT_INFORMATION])
  } finally {
    [Runtime.InteropServices.Marshal]::FreeHGlobal($pointer)
  }
}

function Get-OwnedTreeSnapshot {
  param([int]$RootPid)
  $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object ProcessId,ParentProcessId,Name,CommandLine)
  $seen = New-Object System.Collections.Generic.HashSet[int]
  $queue = New-Object System.Collections.Generic.Queue[int]
  [void]$seen.Add($RootPid)
  $queue.Enqueue($RootPid)
  while ($queue.Count -gt 0) {
    $current = $queue.Dequeue()
    foreach ($child in ($all | Where-Object { [int]$_.ParentProcessId -eq $current })) {
      if ($seen.Add([int]$child.ProcessId)) { $queue.Enqueue([int]$child.ProcessId) }
    }
  }
  $processes = @()
  $privateTotal = [uint64]0
  $workingTotal = [uint64]0
  $cpuTotal = [double]0
  foreach ($ownedId in $seen) {
    $process = Get-Process -Id $ownedId -ErrorAction SilentlyContinue
    $meta = $all | Where-Object { [int]$_.ProcessId -eq $ownedId } | Select-Object -First 1
    if ($process) {
      $privateTotal += [uint64]$process.PrivateMemorySize64
      $workingTotal += [uint64]$process.WorkingSet64
      $cpuTotal += [double]$process.TotalProcessorTime.TotalSeconds
      $processes += [ordered]@{
        pid = $ownedId
        parent_pid = if ($meta) { [int]$meta.ParentProcessId } else { $null }
        name = $process.ProcessName
        private_bytes = [uint64]$process.PrivateMemorySize64
        working_set_bytes = [uint64]$process.WorkingSet64
        cpu_seconds = [double]$process.TotalProcessorTime.TotalSeconds
        command_line = if ($meta) { $meta.CommandLine } else { $null }
      }
    }
  }
  return [ordered]@{
    pids = @($seen)
    processes = @($processes)
    private_bytes = $privateTotal
    working_set_bytes = $workingTotal
    cpu_seconds = $cpuTotal
  }
}

$memoryBytes = [uint64]$MemoryMB * 1MB
$job = [PixieJobObjectV2]::CreateJobObject([IntPtr]::Zero, "pixie-v2-$AttemptId-$PID")
if ($job -eq [IntPtr]::Zero) { throw "CreateJobObject failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
$process = $null
$started = Get-Date
$deadline = $started.AddSeconds($TimeoutSeconds)
$abortReason = $null
$timedOut = $false
$exitCode = 125
$wrapperError = $null
$samples = New-Object System.Collections.Generic.List[object]
$ownedPidSet = New-Object System.Collections.Generic.HashSet[int]
$peakTreePrivate = [uint64]0
$peakTreeWorking = [uint64]0
$peakJobMemory = [uint64]0
$peakProcessMemory = [uint64]0
$peakGpuMemoryMiB = 0
$peakGpuTemperatureC = 0
$configuredJobReadback = $null
$oldEnvironment = @{}
$capNames = @("PIXIE_RESOURCE_CAP_ACTIVE", "PIXIE_RUN_ID", "PIXIE_ATTEMPT_ID", "PIXIE_CAP_RAM_MB", "PIXIE_CAP_CPU_PCT", "PIXIE_CAP_IO_MB_S", "PIXIE_CAP_TIMEOUT_SECONDS")
foreach ($name in $capNames) { $oldEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
try {
  $limit = New-Object PixieJobObjectV2+EXTENDED_LIMIT_INFORMATION
  $basicLimit = New-Object PixieJobObjectV2+BASIC_LIMIT_INFORMATION
  $basicLimit.LimitFlags = [PixieJobObjectV2]::JOB_OBJECT_LIMIT_PROCESS_MEMORY -bor [PixieJobObjectV2]::JOB_OBJECT_LIMIT_JOB_MEMORY -bor [PixieJobObjectV2]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
  $limit.BasicLimitInformation = $basicLimit
  $limit.ProcessMemoryLimit = [UIntPtr]$memoryBytes
  $limit.JobMemoryLimit = [UIntPtr]$memoryBytes
  Set-JobInformation -Job $job -Class ([PixieJobObjectV2]::ExtendedLimitInformation) -Value $limit
  $configuredInfo = Get-JobExtendedInformation -Job $job
  $configuredJobReadback = [ordered]@{
    limit_flags = [uint32]$configuredInfo.BasicLimitInformation.LimitFlags
    process_memory_limit_bytes = [uint64]$configuredInfo.ProcessMemoryLimit
    job_memory_limit_bytes = [uint64]$configuredInfo.JobMemoryLimit
  }
  $requiredFlags = [PixieJobObjectV2]::JOB_OBJECT_LIMIT_PROCESS_MEMORY -bor [PixieJobObjectV2]::JOB_OBJECT_LIMIT_JOB_MEMORY -bor [PixieJobObjectV2]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
  if (($configuredJobReadback.limit_flags -band $requiredFlags) -ne $requiredFlags) {
    throw "Job Object readback lacks required memory/cleanup flags: $($configuredJobReadback.limit_flags)"
  }
  if ($configuredJobReadback.process_memory_limit_bytes -ne $memoryBytes -or $configuredJobReadback.job_memory_limit_bytes -ne $memoryBytes) {
    throw "Job Object memory-limit readback differs from requested $memoryBytes bytes."
  }

  $cpu = New-Object PixieJobObjectV2+CPU_RATE_CONTROL_INFORMATION
  $cpu.ControlFlags = [PixieJobObjectV2]::JOB_OBJECT_CPU_RATE_CONTROL_ENABLE -bor [PixieJobObjectV2]::JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
  $cpu.CpuRate = [uint32]($CpuPercent * 100)
  Set-JobInformation -Job $job -Class ([PixieJobObjectV2]::CpuRateControlInformation) -Value $cpu

  $io = New-Object PixieJobObjectV2+JOBOBJECT_IO_RATE_CONTROL_INFORMATION
  $io.MaxIops = 0
  $io.MaxBandwidth = [int64]$IoMBPerSecond * 1MB
  $io.ReservationIops = 0
  $io.VolumeName = $null
  $io.BaseIoSize = 0
  $io.ControlFlags = [PixieJobObjectV2]::JOB_OBJECT_IO_RATE_CONTROL_ENABLE
  $ioResult = [PixieJobObjectV2]::SetIoRateControlInformationJobObject($job, [ref]$io)
  if ($ioResult -ne 0) { throw "SetIoRateControlInformationJobObject failed: $ioResult" }

  $env:PIXIE_RESOURCE_CAP_ACTIVE = "1"
  $env:PIXIE_RUN_ID = $RunId
  $env:PIXIE_ATTEMPT_ID = $AttemptId
  $env:PIXIE_CAP_RAM_MB = [string]$MemoryMB
  $env:PIXIE_CAP_CPU_PCT = [string]$CpuPercent
  $env:PIXIE_CAP_IO_MB_S = [string]$IoMBPerSecond
  $env:PIXIE_CAP_TIMEOUT_SECONDS = [string]$TimeoutSeconds
  $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($ChildArguments) -Compress)))
  $gate = Join-Path $PSScriptRoot "invoke_owned_v2.ps1"
  $gateArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $gate, "-Executable", $Executable, "-ArgumentsBase64", $payload)
  $process = Start-Process -FilePath "powershell.exe" -ArgumentList $gateArguments -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
  if (-not [PixieJobObjectV2]::AssignProcessToJobObject($job, $process.Handle)) {
    throw "AssignProcessToJobObject failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
  }

  while (-not $process.HasExited) {
    $tree = Get-OwnedTreeSnapshot -RootPid $process.Id
    foreach ($ownedId in $tree.pids) { [void]$ownedPidSet.Add([int]$ownedId) }
    $peakTreePrivate = [math]::Max($peakTreePrivate, [uint64]$tree.private_bytes)
    $peakTreeWorking = [math]::Max($peakTreeWorking, [uint64]$tree.working_set_bytes)
    $jobInfo = Get-JobExtendedInformation -Job $job
    $peakJobMemory = [math]::Max($peakJobMemory, [uint64]$jobInfo.PeakJobMemoryUsed)
    $peakProcessMemory = [math]::Max($peakProcessMemory, [uint64]$jobInfo.PeakProcessMemoryUsed)
    $gpu = $null
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
      $gpu = (& nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader,nounits 2>$null)
      if ($gpu) {
        $parts = $gpu -split ","
        if ($parts.Count -ge 3) {
          $peakGpuMemoryMiB = [math]::Max($peakGpuMemoryMiB, [int]$parts[1].Trim())
          $peakGpuTemperatureC = [math]::Max($peakGpuTemperatureC, [int]$parts[2].Trim())
        }
      }
    }
    $sample = [ordered]@{
      utc = (Get-Date).ToUniversalTime().ToString("o")
      tree_private_bytes = $tree.private_bytes
      tree_working_set_bytes = $tree.working_set_bytes
      tree_cpu_seconds = $tree.cpu_seconds
      owned_pids = @($tree.pids)
      peak_job_memory_bytes = [uint64]$jobInfo.PeakJobMemoryUsed
      peak_process_memory_bytes = [uint64]$jobInfo.PeakProcessMemoryUsed
      gpu = $gpu
    }
    $samples.Add($sample)
    [ordered]@{
      schema = "pixie_owned_process_tree_v2"
      run_id = $RunId
      attempt_id = $AttemptId
      root_pid = $process.Id
      owned_pids = @($ownedPidSet)
      current_processes = @($tree.processes)
      updated_utc = $sample.utc
    } | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $pidPath -Encoding UTF8

    if (-not $DiagnosticOsCapOnly -and [uint64]$tree.private_bytes -gt $memoryBytes) {
      $abortReason = "tree_private_memory_cap_exceeded"
      [PixieJobObjectV2]::TerminateJobObject($job, 137) | Out-Null
      break
    }
    if (-not $DiagnosticOsCapOnly -and [uint64]$jobInfo.PeakJobMemoryUsed -gt $memoryBytes) {
      $abortReason = "job_memory_accounting_cap_exceeded"
      [PixieJobObjectV2]::TerminateJobObject($job, 137) | Out-Null
      break
    }
    if ((Get-Date) -ge $deadline) {
      $abortReason = "timeout"
      $timedOut = $true
      [PixieJobObjectV2]::TerminateJobObject($job, 124) | Out-Null
      break
    }
    Start-Sleep -Milliseconds 500
    $process.Refresh()
  }
  $process.WaitForExit()
  if ($abortReason -eq "timeout") { $exitCode = 124 }
  elseif ($abortReason -match "memory") { $exitCode = 137 }
  else { $exitCode = $process.ExitCode }
  if (-not $abortReason -and $exitCode -ne 0) {
    $finalInfo = Get-JobExtendedInformation -Job $job
    $peakJobMemory = [math]::Max($peakJobMemory, [uint64]$finalInfo.PeakJobMemoryUsed)
    $peakProcessMemory = [math]::Max($peakProcessMemory, [uint64]$finalInfo.PeakProcessMemoryUsed)
    if ($peakJobMemory -ge [uint64]($memoryBytes * 0.90) -or $peakProcessMemory -ge [uint64]($memoryBytes * 0.90)) {
      $abortReason = "os_memory_cap_termination"
      $exitCode = 137
    } else {
      $abortReason = "child_nonzero_exit"
    }
  }
} catch {
  if ($process -and -not $process.HasExited) { [PixieJobObjectV2]::TerminateJobObject($job, 125) | Out-Null }
  $wrapperError = $_.Exception.ToString()
  $abortReason = if ($abortReason) { $abortReason } else { "wrapper_error" }
  $exitCode = 125
} finally {
  try {
    $finalInfo = Get-JobExtendedInformation -Job $job
    $peakJobMemory = [math]::Max($peakJobMemory, [uint64]$finalInfo.PeakJobMemoryUsed)
    $peakProcessMemory = [math]::Max($peakProcessMemory, [uint64]$finalInfo.PeakProcessMemoryUsed)
  } catch {
    if (-not $wrapperError) { $wrapperError = "Job accounting query: $($_.Exception.Message)" }
  }
  [PixieJobObjectV2]::CloseHandle($job) | Out-Null
  foreach ($name in $capNames) { [Environment]::SetEnvironmentVariable($name, $oldEnvironment[$name], "Process") }
}

$summary = [ordered]@{
  schema = "pixie_resource_summary_v2"
  run_id = $RunId
  attempt_id = $AttemptId
  started_utc = $started.ToUniversalTime().ToString("o")
  ended_utc = (Get-Date).ToUniversalTime().ToString("o")
  command = [ordered]@{ executable = $Executable; arguments = [string[]]$ChildArguments }
  caps = [ordered]@{ memory_mb = $MemoryMB; cpu_percent = $CpuPercent; io_mb_per_second = $IoMBPerSecond; timeout_seconds = $TimeoutSeconds }
  cap_mechanism = [ordered]@{
    process_memory = "Windows Job Object per-process hard limit"
    job_memory = "Windows Job Object whole-job hard limit"
    independent_tree_memory = "500 ms owned-descendant private-memory audit and termination"
    cpu = "Windows Job Object hard CPU rate"
    io = "Windows Job Object I/O rate control"
  }
  configured_job_readback = $configuredJobReadback
  root_pid = if ($process) { $process.Id } else { $null }
  owned_pids = @($ownedPidSet)
  exit_code = $exitCode
  status = if ($exitCode -eq 0) { "complete" } else { "aborted" }
  abort_reason = $abortReason
  timed_out = $timedOut
  diagnostic_os_cap_only = [bool]$DiagnosticOsCapOnly
  peak_tree_private_bytes = $peakTreePrivate
  peak_tree_working_set_bytes = $peakTreeWorking
  peak_job_memory_bytes = $peakJobMemory
  peak_process_memory_bytes = $peakProcessMemory
  peak_gpu_memory_mib = $peakGpuMemoryMiB
  peak_gpu_temperature_c = $peakGpuTemperatureC
  wrapper_error = $wrapperError
  samples = [object[]]$samples
  stdout = $stdoutPath
  stderr = $stderrPath
  pid_receipt = $pidPath
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
if ($exitCode -ne 0) {
  Write-Error "Capped child aborted ($abortReason), exit $exitCode. Receipt: $summaryPath"
  exit $exitCode
}
Write-Output $summaryPath
