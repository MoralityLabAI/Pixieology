param(
  [Parameter(Mandatory = $true)][string]$Executable,
  [string[]]$ChildArguments = @(),
  [string]$ArgumentsBase64 = "",
  [string]$RunId = "manual",
  [string]$OutputDirectory = "",
  [int]$MemoryGB = 10,
  [int]$CpuPercent = 50,
  [int]$IoMBPerSecond = 50,
  [int]$TimeoutMinutes = 30
)

$ErrorActionPreference = "Stop"
if ($ArgumentsBase64) {
  $decoded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ArgumentsBase64))
  $parsedArguments = $decoded | ConvertFrom-Json
  $ChildArguments = @()
  foreach ($item in $parsedArguments) { $ChildArguments += [string]$item }
}
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $PSScriptRoot "..\artifacts\capped" }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$stdoutPath = Join-Path $OutputDirectory "$RunId.stdout.log"
$stderrPath = Join-Path $OutputDirectory "$RunId.stderr.log"
$summaryPath = Join-Path $OutputDirectory "$RunId.resource_summary.json"
$pidPath = Join-Path $OutputDirectory "$RunId.pids.json"
$cleanupPath = Join-Path $OutputDirectory "$RunId.cleanup.json"

if (-not ("PixieJobObject" -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class PixieJobObject {
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
    if (-not [PixieJobObject]::SetInformationJobObject($Job, $Class, $pointer, [uint32]$size)) {
      throw "SetInformationJobObject($Class) failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
  } finally {
    [Runtime.InteropServices.Marshal]::FreeHGlobal($pointer)
  }
}

function Get-JobExtendedInformation {
  param([IntPtr]$Job)
  $value = New-Object PixieJobObject+EXTENDED_LIMIT_INFORMATION
  $size = [Runtime.InteropServices.Marshal]::SizeOf($value)
  $pointer = [Runtime.InteropServices.Marshal]::AllocHGlobal($size)
  try {
    $returned = [uint32]0
    if (-not [PixieJobObject]::QueryInformationJobObject($Job, [PixieJobObject]::ExtendedLimitInformation, $pointer, [uint32]$size, [ref]$returned)) {
      throw "QueryInformationJobObject failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
    return [Runtime.InteropServices.Marshal]::PtrToStructure($pointer, [type][PixieJobObject+EXTENDED_LIMIT_INFORMATION])
  } finally {
    [Runtime.InteropServices.Marshal]::FreeHGlobal($pointer)
  }
}

function Get-OwnedProcessIds {
  param([int]$RootPid)
  $owned = New-Object System.Collections.Generic.HashSet[int]
  [void]$owned.Add($RootPid)
  $changed = $true
  while ($changed) {
    $changed = $false
    foreach ($candidate in Get-CimInstance Win32_Process -ErrorAction SilentlyContinue) {
      if ($owned.Contains([int]$candidate.ParentProcessId) -and -not $owned.Contains([int]$candidate.ProcessId)) {
        [void]$owned.Add([int]$candidate.ProcessId)
        $changed = $true
      }
    }
  }
  return @($owned | Sort-Object)
}

$job = [PixieJobObject]::CreateJobObject([IntPtr]::Zero, "pixie-$RunId-$PID")
if ($job -eq [IntPtr]::Zero) { throw "CreateJobObject failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
$process = $null
$timedOut = $false
$peakWorkingSet = 0L
$peakPrivate = 0L
$jobPeakMemory = 0L
$jobIoReadBytes = 0L
$jobIoWriteBytes = 0L
$wrapperError = $null
$exitCode = 125
$capVerified = $false
$capBreached = $false
$verifiedLimitFlags = 0
$verifiedProcessMemoryBytes = 0L
$verifiedJobMemoryBytes = 0L
$ownedPids = @()
$samples = New-Object System.Collections.Generic.List[object]
$started = Get-Date
$oldCap = $env:PIXIE_RESOURCE_CAP_ACTIVE
$oldRun = $env:PIXIE_RUN_ID
try {
  $expectedMemoryBytes = [uint64]$MemoryGB * 1GB
  $limit = New-Object PixieJobObject+EXTENDED_LIMIT_INFORMATION
  $basicLimit = New-Object PixieJobObject+BASIC_LIMIT_INFORMATION
  $basicLimit.LimitFlags = [PixieJobObject]::JOB_OBJECT_LIMIT_PROCESS_MEMORY -bor [PixieJobObject]::JOB_OBJECT_LIMIT_JOB_MEMORY -bor [PixieJobObject]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
  $limit.BasicLimitInformation = $basicLimit
  $limit.ProcessMemoryLimit = [UIntPtr]$expectedMemoryBytes
  $limit.JobMemoryLimit = [UIntPtr]$expectedMemoryBytes
  Set-JobInformation -Job $job -Class ([PixieJobObject]::ExtendedLimitInformation) -Value $limit

  $verified = Get-JobExtendedInformation -Job $job
  $verifiedLimitFlags = [uint32]$verified.BasicLimitInformation.LimitFlags
  $verifiedProcessMemoryBytes = $verified.ProcessMemoryLimit.ToUInt64()
  $verifiedJobMemoryBytes = $verified.JobMemoryLimit.ToUInt64()
  $requiredFlags = [PixieJobObject]::JOB_OBJECT_LIMIT_PROCESS_MEMORY -bor [PixieJobObject]::JOB_OBJECT_LIMIT_JOB_MEMORY -bor [PixieJobObject]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
  if (($verifiedLimitFlags -band $requiredFlags) -ne $requiredFlags) {
    throw "Job memory flags did not round-trip: expected $requiredFlags, got $verifiedLimitFlags"
  }
  if ($verifiedProcessMemoryBytes -ne $expectedMemoryBytes -or $verifiedJobMemoryBytes -ne $expectedMemoryBytes) {
    throw "Job memory limits did not round-trip: expected $expectedMemoryBytes, got process=$verifiedProcessMemoryBytes job=$verifiedJobMemoryBytes"
  }
  $capVerified = $true

  $cpu = New-Object PixieJobObject+CPU_RATE_CONTROL_INFORMATION
  $cpu.ControlFlags = [PixieJobObject]::JOB_OBJECT_CPU_RATE_CONTROL_ENABLE -bor [PixieJobObject]::JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
  $cpu.CpuRate = [uint32]($CpuPercent * 100)
  Set-JobInformation -Job $job -Class ([PixieJobObject]::CpuRateControlInformation) -Value $cpu

  $io = New-Object PixieJobObject+JOBOBJECT_IO_RATE_CONTROL_INFORMATION
  $io.MaxIops = 0
  $io.MaxBandwidth = [int64]$IoMBPerSecond * 1MB
  $io.ReservationIops = 0
  $io.VolumeName = $null
  $io.BaseIoSize = 0
  $io.ControlFlags = [PixieJobObject]::JOB_OBJECT_IO_RATE_CONTROL_ENABLE
  $ioResult = [PixieJobObject]::SetIoRateControlInformationJobObject($job, [ref]$io)
  if ($ioResult -ne 0) { throw "SetIoRateControlInformationJobObject failed: $ioResult" }

  $env:PIXIE_RESOURCE_CAP_ACTIVE = "1"
  $env:PIXIE_RUN_ID = $RunId
  $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((ConvertTo-Json @($ChildArguments) -Compress)))
  $gate = Join-Path $PSScriptRoot "invoke_owned.ps1"
  $gateArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $gate, "-Executable", $Executable, "-ArgumentsBase64", $payload)
  $process = Start-Process -FilePath "powershell.exe" -ArgumentList $gateArguments -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
  if (-not [PixieJobObject]::AssignProcessToJobObject($job, $process.Handle)) {
    throw "AssignProcessToJobObject failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
  }
  $ownedPids = @($process.Id)
  @{run_id=$RunId; root_pid=$process.Id; owned_pids=$ownedPids; started_utc=$started.ToUniversalTime().ToString("o")} | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding UTF8
  $deadline = $started.AddMinutes($TimeoutMinutes)
  while (-not $process.HasExited) {
    $process.Refresh()
    $peakWorkingSet = [math]::Max($peakWorkingSet, $process.WorkingSet64)
    $peakPrivate = [math]::Max($peakPrivate, $process.PrivateMemorySize64)
    $ownedPids = @(Get-OwnedProcessIds -RootPid $process.Id)
    @{run_id=$RunId; root_pid=$process.Id; owned_pids=$ownedPids; started_utc=$started.ToUniversalTime().ToString("o")} | ConvertTo-Json | Set-Content -LiteralPath $pidPath -Encoding UTF8
    $currentJob = Get-JobExtendedInformation -Job $job
    $currentJobPeak = [uint64]$currentJob.PeakJobMemoryUsed
    $gpu = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { (& nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader,nounits 2>$null) } else { $null }
    $samples.Add([ordered]@{utc=(Get-Date).ToUniversalTime().ToString("o"); working_set_bytes=$process.WorkingSet64; private_bytes=$process.PrivateMemorySize64; job_peak_memory_bytes=$currentJobPeak; owned_pids=$ownedPids; cpu_seconds=$process.TotalProcessorTime.TotalSeconds; gpu=$gpu})
    if ($currentJobPeak -gt $expectedMemoryBytes) {
      $capBreached = $true
      [PixieJobObject]::TerminateJobObject($job, 137) | Out-Null
      break
    }
    if ((Get-Date) -ge $deadline) {
      $timedOut = $true
      [PixieJobObject]::TerminateJobObject($job, 124) | Out-Null
      break
    }
    Start-Sleep -Seconds 1
  }
  $process.WaitForExit()
  $exitCode = if ($capBreached) { 137 } elseif ($timedOut) { 124 } else { $process.ExitCode }
} catch {
  if ($process -and -not $process.HasExited) { [PixieJobObject]::TerminateJobObject($job, 125) | Out-Null }
  $exitCode = 125
  $wrapperError = $_.Exception.ToString()
} finally {
  try {
    $jobInfo = Get-JobExtendedInformation -Job $job
    $jobPeakMemory = [uint64]$jobInfo.PeakJobMemoryUsed
    $jobIoReadBytes = [uint64]$jobInfo.IoInfo.ReadTransferCount
    $jobIoWriteBytes = [uint64]$jobInfo.IoInfo.WriteTransferCount
    if ($jobPeakMemory -gt ([uint64]$MemoryGB * 1GB)) {
      $capBreached = $true
      if ($exitCode -eq 0) { $exitCode = 137 }
    }
  } catch {
    if (-not $wrapperError) { $wrapperError = "Job accounting query: $($_.Exception.Message)" }
  }
  [PixieJobObject]::CloseHandle($job) | Out-Null
  $env:PIXIE_RESOURCE_CAP_ACTIVE = $oldCap
  $env:PIXIE_RUN_ID = $oldRun
}

$rootPid = $null
if ($null -ne $process) { $rootPid = [int]$process.Id }
$summary = [ordered]@{}
$summary["schema_version"] = 1
$summary["run_id"] = $RunId
$summary["started_utc"] = $started.ToUniversalTime().ToString("o")
$summary["ended_utc"] = (Get-Date).ToUniversalTime().ToString("o")
$summary["command"] = [ordered]@{ executable=$Executable; arguments=[string[]]$ChildArguments }
$summary["caps"] = [ordered]@{ memory_gb=$MemoryGB; cpu_percent=$CpuPercent; io_mb_per_second=$IoMBPerSecond; timeout_minutes=$TimeoutMinutes }
$summary["cap_mechanism"] = [ordered]@{ memory="Windows Job Object job-memory limit"; cpu="Windows Job Object hard CPU rate"; io="Windows Job Object I/O rate control" }
$summary["cap_verified"] = $capVerified
$summary["cap_breached"] = $capBreached
$summary["verified_limit_flags"] = $verifiedLimitFlags
$summary["verified_process_memory_bytes"] = $verifiedProcessMemoryBytes
$summary["verified_job_memory_bytes"] = $verifiedJobMemoryBytes
$summary["owned_pids"] = $ownedPids
$summary["root_pid"] = $rootPid
$summary["exit_code"] = $exitCode
$summary["timed_out"] = $timedOut
$summary["peak_working_set_bytes"] = $peakWorkingSet
$summary["peak_private_bytes"] = $peakPrivate
$summary["peak_job_memory_bytes"] = $jobPeakMemory
$summary["job_io_read_bytes"] = $jobIoReadBytes
$summary["job_io_write_bytes"] = $jobIoWriteBytes
$summary["wrapper_error"] = $wrapperError
$summary["samples"] = [object[]]$samples
$summary["stdout"] = $stdoutPath
$summary["stderr"] = $stderrPath
$summary["cleanup"] = $cleanupPath
$summary["cleanup_error"] = $null
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

# The Job Object owns and terminates only this run's process tree.  Audit those
# recorded PIDs after the job handle closes on both success and failure, before
# propagating the child exit code to the caller.
try {
  $cleanupScript = Join-Path $PSScriptRoot "post_run_cleanup.ps1"
  & $cleanupScript -PidFile $pidPath -SummaryPath $cleanupPath -RunId $RunId | Out-Host
} catch {
  $summary["cleanup_error"] = $_.Exception.ToString()
  if ($exitCode -eq 0) { $exitCode = 125 }
  $summary["exit_code"] = $exitCode
  $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
}
if ($exitCode -ne 0) {
  [Console]::Error.WriteLine("Capped child failed with exit code $exitCode. See $summaryPath, $stdoutPath, and $stderrPath")
  exit $exitCode
}
Write-Output $summaryPath
