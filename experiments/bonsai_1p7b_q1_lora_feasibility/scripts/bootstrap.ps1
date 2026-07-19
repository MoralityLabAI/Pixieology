param([string]$Venv = "")
$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $Venv) {
  if (-not $env:OUTPUT_ROOT) { throw "Set OUTPUT_ROOT or pass -Venv explicitly." }
  $Venv = Join-Path $env:OUTPUT_ROOT ".venv"
}
python -m venv $Venv
$python = Join-Path $Venv "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e "$root[test]"
& $python -m pip freeze

