# deploy-railway.ps1 - Deploy Ginie Backend to Railway
#
# Prerequisites:
#   - Railway CLI installed (railway --version)
#   - Logged in to Railway (railway login)
#
# Usage:
#   .\deploy-railway.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ginie Backend - Railway Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
try {
    railway --version | Out-Null
} catch {
    Write-Host "ERROR: Railway CLI not installed." -ForegroundColor Red
    Write-Host "Install from: https://docs.railway.app/develop/cli" -ForegroundColor Yellow
    exit 1
}

# Check if logged in
Write-Host "[1/6] Checking Railway authentication..." -ForegroundColor Yellow
$loginCheck = railway whoami 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in. Opening browser for authentication..." -ForegroundColor Yellow
    railway login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Railway login failed." -ForegroundColor Red
        exit 1
    }
}
Write-Host "✓ Authenticated" -ForegroundColor Green
Write-Host ""

# Initialize project if not already initialized
Write-Host "[2/6] Initializing Railway project..." -ForegroundColor Yellow
$projectCheck = railway status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating new Railway project..." -ForegroundColor Gray
    railway init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to initialize Railway project." -ForegroundColor Red
        exit 1
    }
}
Write-Host "✓ Project initialized" -ForegroundColor Green
Write-Host ""

# Add databases
Write-Host "[3/6] Setting up databases..." -ForegroundColor Yellow

# Check if PostgreSQL exists
$pgCheck = railway variables | Select-String "DATABASE_URL"
if (-not $pgCheck) {
    Write-Host "Adding PostgreSQL..." -ForegroundColor Gray
    railway add --database postgresql
}

# Check if Redis exists
$redisCheck = railway variables | Select-String "REDIS_URL"
if (-not $redisCheck) {
    Write-Host "Adding Redis..." -ForegroundColor Gray
    railway add --database redis
}

Write-Host "✓ Databases configured" -ForegroundColor Green
Write-Host ""

# Set environment variables
Write-Host "[4/6] Configuring environment variables..." -ForegroundColor Yellow

# Check if .env.ginie exists
if (-not (Test-Path ".env.ginie")) {
    Write-Host "ERROR: .env.ginie not found." -ForegroundColor Red
    Write-Host "Copy .env.ginie.example to .env.ginie and configure it first." -ForegroundColor Yellow
    exit 1
}

# Read .env.ginie and set variables
Write-Host "Reading .env.ginie..." -ForegroundColor Gray
$envVars = Get-Content ".env.ginie" | Where-Object { $_ -match "^[^#].*=" }

foreach ($line in $envVars) {
    if ($line -match '^([^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Skip empty values and database URLs (Railway provides these)
        if ($value -and $key -ne "DATABASE_URL" -and $key -ne "REDIS_URL") {
            Write-Host "  Setting $key..." -ForegroundColor Gray
            railway variables set "$key=$value" | Out-Null
        }
    }
}

# Generate JWT secret if not set
$jwtCheck = railway variables | Select-String "JWT_SECRET"
if (-not $jwtCheck) {
    Write-Host "  Generating JWT_SECRET..." -ForegroundColor Gray
    $jwtSecret = python -c "import secrets; print(secrets.token_hex(32))"
    railway variables set "JWT_SECRET=$jwtSecret" | Out-Null
}

Write-Host "✓ Environment variables configured" -ForegroundColor Green
Write-Host ""

# Deploy
Write-Host "[5/6] Deploying to Railway..." -ForegroundColor Yellow
Write-Host "This may take 2-3 minutes..." -ForegroundColor Gray
Write-Host ""

railway up

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ Deployment successful!" -ForegroundColor Green
Write-Host ""

# Get deployment URL
Write-Host "[6/6] Getting deployment URL..." -ForegroundColor Yellow
$domain = railway domain 2>&1

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend API URL:" -ForegroundColor Green
$deployUrl = railway domain 2>&1 | Out-String
Write-Host "  $deployUrl" -ForegroundColor White
Write-Host ""
Write-Host "API Documentation:" -ForegroundColor Green
Write-Host "  $deployUrl/docs" -ForegroundColor White
Write-Host ""
Write-Host "Health Check:" -ForegroundColor Green
Write-Host "  $deployUrl/api/v1/health" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Test the API: curl $deployUrl/api/v1/health" -ForegroundColor Gray
Write-Host "  2. Update frontend NEXT_PUBLIC_API_URL to: $deployUrl" -ForegroundColor Gray
Write-Host "  3. Update CORS_ORIGINS to include your frontend URL" -ForegroundColor Gray
Write-Host ""
Write-Host "To view logs: railway logs" -ForegroundColor Gray
Write-Host "To open dashboard: railway open" -ForegroundColor Gray
Write-Host ""
