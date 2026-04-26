# Simple Railway Deployment Script
# Run from backend directory

Write-Host "Deploying Ginie Backend to Railway..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Login
Write-Host "[1/4] Checking authentication..." -ForegroundColor Yellow
railway whoami
if ($LASTEXITCODE -ne 0) {
    Write-Host "Please login first..." -ForegroundColor Yellow
    railway login
}

# Step 2: Initialize or link project
Write-Host ""
Write-Host "[2/4] Initializing project..." -ForegroundColor Yellow
railway link

# Step 3: Add databases if needed
Write-Host ""
Write-Host "[3/4] Checking databases..." -ForegroundColor Yellow
Write-Host "Note: Add PostgreSQL and Redis from Railway dashboard if not already added" -ForegroundColor Gray

# Step 4: Deploy
Write-Host ""
Write-Host "[4/4] Deploying..." -ForegroundColor Yellow
railway up

# Get URL
Write-Host ""
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Your backend URL:" -ForegroundColor Cyan
railway domain

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Set environment variables in Railway dashboard" -ForegroundColor Gray
Write-Host "2. Add PostgreSQL and Redis databases" -ForegroundColor Gray
Write-Host "3. Test: railway logs" -ForegroundColor Gray
