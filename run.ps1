param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$requirementsFile = Join-Path $projectRoot "requirements.txt"
$uploadsPath = Join-Path $projectRoot "static\uploads"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment in .venv ..."
    python -m venv $venvPath
}

if (-not (Test-Path $uploadsPath)) {
    New-Item -ItemType Directory -Path $uploadsPath | Out-Null
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies ..."
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r $requirementsFile
}

Write-Host "Starting Flask app at http://127.0.0.1:5000 ..."
& $venvPython (Join-Path $projectRoot "app.py")
