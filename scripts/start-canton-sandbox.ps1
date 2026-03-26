# start-canton-sandbox.ps1 — Start Canton sandbox with PostgreSQL persistence
#
# Prerequisites:
#   1. PostgreSQL running (docker-compose up -d postgres)
#   2. DAML SDK installed (~/.daml/bin/daml or DAML_SDK_PATH set)
#   3. canton_sandbox database created (init_db.sql or docker-compose handles this)
#
# Usage:
#   .\scripts\start-canton-sandbox.ps1
#   .\scripts\start-canton-sandbox.ps1 -InMemory   # fallback: skip PostgreSQL

param(
    [switch]$InMemory
)

$ErrorActionPreference = "Stop"

# Resolve DAML SDK path
$DamlPath = $env:DAML_SDK_PATH
if (-not $DamlPath) {
    $DamlPath = "$env:APPDATA\daml\bin\daml.cmd"
}
if (-not (Test-Path $DamlPath)) {
    $DamlPath = (Get-Command daml -ErrorAction SilentlyContinue).Source
}
if (-not $DamlPath) {
    Write-Error "DAML SDK not found. Set DAML_SDK_PATH or install the SDK."
    exit 1
}

Write-Host "Using DAML SDK: $DamlPath" -ForegroundColor Cyan

# Resolve project root (one level up from scripts/)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ConfFile = Join-Path $ProjectRoot "canton-sandbox.conf"

if ($InMemory) {
    Write-Host "Starting Canton sandbox (IN-MEMORY mode)..." -ForegroundColor Yellow
    Write-Host "  Ledger API: http://localhost:6865" -ForegroundColor Gray
    Write-Host "  Admin API:  http://localhost:26012" -ForegroundColor Gray
    Write-Host ""
    & $DamlPath sandbox
} else {
    # Check PostgreSQL connectivity
    Write-Host "Checking PostgreSQL connectivity..." -ForegroundColor Cyan
    try {
        $pgResult = & psql -U postgres -h localhost -c "SELECT 1" -t 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "PostgreSQL not reachable. Start it with: docker-compose up -d postgres" -ForegroundColor Red
            Write-Host "Or use -InMemory flag to skip PostgreSQL." -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "psql not found or PostgreSQL not reachable." -ForegroundColor Red
        Write-Host "Make sure PostgreSQL is running: docker-compose up -d postgres" -ForegroundColor Yellow
        Write-Host "Or use -InMemory flag: .\scripts\start-canton-sandbox.ps1 -InMemory" -ForegroundColor Yellow
        exit 1
    }

    # Ensure canton_sandbox database exists
    Write-Host "Ensuring canton_sandbox database exists..." -ForegroundColor Cyan
    & psql -U postgres -h localhost -tc "SELECT 1 FROM pg_database WHERE datname = 'canton_sandbox'" | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not $?) {
        & psql -U postgres -h localhost -c "CREATE DATABASE canton_sandbox"
    }

    Write-Host "Starting Canton sandbox (PostgreSQL persistence)..." -ForegroundColor Green
    Write-Host "  Config:     $ConfFile" -ForegroundColor Gray
    Write-Host "  Ledger API: http://localhost:6865" -ForegroundColor Gray
    Write-Host "  Admin API:  http://localhost:26012" -ForegroundColor Gray
    Write-Host "  Database:   canton_sandbox @ localhost:5432" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Parties and contracts will persist across restarts." -ForegroundColor Green
    Write-Host ""

    # Set env vars for HOCON substitution
    $env:CANTON_DB_HOST = if ($env:CANTON_DB_HOST) { $env:CANTON_DB_HOST } else { "localhost" }
    $env:CANTON_DB_PORT = if ($env:CANTON_DB_PORT) { $env:CANTON_DB_PORT } else { "5432" }
    $env:CANTON_DB_NAME = if ($env:CANTON_DB_NAME) { $env:CANTON_DB_NAME } else { "canton_sandbox" }
    $env:CANTON_DB_USER = if ($env:CANTON_DB_USER) { $env:CANTON_DB_USER } else { "postgres" }
    $env:CANTON_DB_PASSWORD = if ($env:CANTON_DB_PASSWORD) { $env:CANTON_DB_PASSWORD } else { "password" }

    & $DamlPath sandbox --config $ConfFile
}
