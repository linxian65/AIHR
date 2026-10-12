# Start HR Recruit Agent backend (PowerShell).
# Activates the project venv, checks .env exists, runs uvicorn with auto-reload.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
  Write-Host "ERROR: .venv not found. Run: python -m venv .venv ; .venv\Scripts\pip install -e ." -ForegroundColor Red
  exit 1
}

& .\.venv\Scripts\Activate.ps1

if (-not (Test-Path .env)) {
  Write-Host "ERROR: .env not found. Copy .env.example to .env and fill MINIMAX_API_KEY." -ForegroundColor Red
  exit 1
}

uvicorn app.main:app --port 8000 --host 127.0.0.1 --reload
