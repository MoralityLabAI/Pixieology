param(
  [Parameter(Mandatory = $true)][string]$Executable,
  [Parameter(Mandatory = $true)][string]$ArgumentsBase64
)

$ErrorActionPreference = "Stop"
# Give the parent enough time to assign this gate to the Job Object. Every
# subsequently launched process inherits both per-process and whole-job caps.
Start-Sleep -Seconds 2
$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ArgumentsBase64))
$parsed = $json | ConvertFrom-Json
$arguments = @()
foreach ($item in $parsed) { $arguments += [string]$item }
& $Executable @arguments
exit $LASTEXITCODE
