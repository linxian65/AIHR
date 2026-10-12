# Start HR Recruit Agent frontend (Vite dev server).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path node_modules)) {
  Write-Host "node_modules missing, running npm install..."
  npm install
}

npm run dev
