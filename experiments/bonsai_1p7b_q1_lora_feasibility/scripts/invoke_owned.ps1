param(
  [Parameter(Mandatory = $true)][string]$Executable,
  [Parameter(Mandatory = $true)][string]$ArgumentsBase64
)

$ErrorActionPreference = "Stop"
# This short gate gives run_capped.ps1 time to assign this process to the Job
# Object. All subsequently launched children inherit the hard limits.
Start-Sleep -Seconds 2
$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ArgumentsBase64))
$parsedArguments = $json | ConvertFrom-Json
$childArguments = @()
foreach ($item in $parsedArguments) { $childArguments += [string]$item }
& $Executable @childArguments
exit $LASTEXITCODE
