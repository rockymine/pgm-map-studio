param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Command = "restart",

    [string]$HostAddress = "127.0.0.1",

    [int]$Port = 7893
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Could not find project venv Python at $Python"
}

& $Python (Join-Path $ProjectRoot "tools\run_studio_dev.py") $Command --host $HostAddress --port $Port
