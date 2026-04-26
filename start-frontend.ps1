# Start Ginie Frontend with Railway Backend
# This script starts the frontend locally and connects to deployed Railway services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ginie Frontend - Local Development" -ForegroundColor Cyan
Write-Host "  Backend: Railway (Production)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Node.js is installed
Write-Host "Checking prerequisites..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "✓ Node.js installed: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Node.js not found!" -ForegroundColor Red
    Write-Host "  Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Navigate to frontend directory
$frontendDir = Join-Path $PSScriptRoot "frontend_dark"
if (-not (Test-Path $frontendDir)) {
    Write-Host "✗ Frontend directory not found: $frontendDir" -ForegroundColor Red
    exit 1
}

Set-Location $frontendDir
Write-Host "✓ Changed to frontend directory" -ForegroundColor Green
Write-Host ""

# Check if .env.local exists
$envFile = Join-Path $frontendDir ".env.local"
if (Test-Path $envFile) {
    Write-Host "✓ Environment file found" -ForegroundColor Green
    $envContent = Get-Content $envFile -Raw
    Write-Host "  Configuration:" -ForegroundColor Cyan
    Write-Host "  $($envContent.Trim())" -ForegroundColor Gray
} else {
    Write-Host "⚠ .env.local not found, creating..." -ForegroundColor Yellow
    @"
# Ginie Frontend - Railway Production Backend
NEXT_PUBLIC_API_URL=https://canton-ginie-production.up.railway.app/api/v1
"@ | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host "✓ Created .env.local" -ForegroundColor Green
}
Write-Host ""

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ npm install failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
    Write-Host ""
}

# Verify backend is reachable
Write-Host "Verifying backend connection..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "https://canton-ginie-production.up.railway.app/api/v1/health" -Method GET -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Backend is online and healthy" -ForegroundColor Green
        $health = $response.Content | ConvertFrom-Json
        Write-Host "  Canton: $($health.canton_connected ? 'Connected' : 'Disconnected')" -ForegroundColor $(if ($health.canton_connected) { 'Green' } else { 'Yellow' })
        Write-Host "  Redis: $($health.redis_status)" -ForegroundColor Gray
        Write-Host "  Database: $($health.db_status)" -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠ Could not reach backend (this is OK if backend is still starting)" -ForegroundColor Yellow
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
}
Write-Host ""

# Display instructions
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting Development Server..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend will be available at:" -ForegroundColor Green
Write-Host "  → http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API (Railway):" -ForegroundColor Green
Write-Host "  → https://canton-ginie-production.up.railway.app" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the development server
npm run dev
