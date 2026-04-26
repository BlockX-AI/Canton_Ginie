# start-all-services.ps1 — Launch all Ginie services for local development
#
# This script starts:
#   1. PostgreSQL + Redis (via Docker)
#   2. Canton Sandbox (local Daml ledger)
#   3. Ginie Backend API (FastAPI on port 8000)
#   4. Frontend (Next.js on port 3000)
#
# Prerequisites:
#   - Docker Desktop running
#   - Daml SDK installed
#   - backend/.env.ginie configured with LLM API key
#   - Node.js 18+ and Python 3.10+ installed
#
# Usage:
#   .\start-all-services.ps1
#
# To stop all services:
#   Press Ctrl+C in each terminal, then run: docker-compose down

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ginie - Full Stack Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "[1/4] Checking prerequisites..." -ForegroundColor Yellow

# Check Docker
try {
    docker --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
} catch {
    Write-Host "ERROR: Docker not found. Install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check Daml SDK
$DamlPath = $env:DAML_SDK_PATH
if (-not $DamlPath) {
    $DamlPath = "$env:APPDATA\daml\bin\daml.cmd"
}
if (-not (Test-Path $DamlPath)) {
    $DamlPath = (Get-Command daml -ErrorAction SilentlyContinue).Source
}
if (-not $DamlPath) {
    Write-Host "ERROR: Daml SDK not found. Install from https://docs.daml.com/getting-started/installation.html" -ForegroundColor Red
    exit 1
}

# Check Python
try {
    python --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
} catch {
    Write-Host "ERROR: Python not found. Install Python 3.10+." -ForegroundColor Red
    exit 1
}

# Check Node.js
try {
    node --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
} catch {
    Write-Host "ERROR: Node.js not found. Install Node.js 18+." -ForegroundColor Red
    exit 1
}

# Check .env.ginie
if (-not (Test-Path "backend\.env.ginie")) {
    Write-Host "ERROR: backend\.env.ginie not found." -ForegroundColor Red
    Write-Host "Copy backend\.env.ginie.example to backend\.env.ginie and add your LLM API key." -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ All prerequisites met" -ForegroundColor Green
Write-Host ""

# Start infrastructure
Write-Host "[2/4] Starting PostgreSQL + Redis..." -ForegroundColor Yellow
docker-compose up -d postgres redis
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start Docker services." -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 5

Write-Host "✓ Infrastructure running" -ForegroundColor Green
Write-Host ""

# Instructions for manual terminal startup
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Open 3 NEW TERMINALS and run:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "TERMINAL 1 - Canton Sandbox:" -ForegroundColor Yellow
Write-Host "  cd $PWD" -ForegroundColor Gray
Write-Host "  .\scripts\start-canton-sandbox.ps1" -ForegroundColor White
Write-Host ""

Write-Host "TERMINAL 2 - Backend API:" -ForegroundColor Yellow
Write-Host "  cd $PWD\backend" -ForegroundColor Gray
Write-Host "  .\venv\Scripts\activate" -ForegroundColor White
Write-Host "  python -m api.main" -ForegroundColor White
Write-Host ""

Write-Host "TERMINAL 3 - Frontend:" -ForegroundColor Yellow
Write-Host "  cd $PWD\frontend_dark" -ForegroundColor Gray
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Service URLs (after starting above):" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Frontend:       http://localhost:3000" -ForegroundColor Green
Write-Host "  Backend API:    http://localhost:8000" -ForegroundColor Green
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Canton Ledger:  http://localhost:6865" -ForegroundColor Green
Write-Host "  Canton JSON:    http://localhost:7575" -ForegroundColor Green
Write-Host ""

Write-Host "Press any key to continue (this will keep Docker running)..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Write-Host ""
Write-Host "Docker services (PostgreSQL + Redis) are running in background." -ForegroundColor Green
Write-Host "Start the 3 services in separate terminals as shown above." -ForegroundColor Green
Write-Host ""
Write-Host "To stop Docker services later: docker-compose down" -ForegroundColor Gray
