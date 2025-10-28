# YouTube Audit Engine - Minimal Docker Startup Script
# This starts only the essential services for MVP testing

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "YouTube Audit Engine - Minimal MVP Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerRunning = $false
try {
    docker ps > $null 2>&1
    $dockerRunning = $true
    Write-Host "✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

# Check if .env.minimal exists, if not copy it to .env
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.minimal") {
        Write-Host "Creating .env file from .env.minimal..." -ForegroundColor Yellow
        Copy-Item ".env.minimal" ".env"
        Write-Host "✓ .env file created" -ForegroundColor Green
    } else {
        Write-Host "✗ .env.minimal not found!" -ForegroundColor Red
        exit 1
    }
}

# Create data directory for SQLite
if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
    Write-Host "✓ Created data directory for SQLite" -ForegroundColor Green
}

Write-Host "`nStarting minimal services..." -ForegroundColor Yellow
Write-Host "Services: Redis, Backend, Celery Worker, Frontend" -ForegroundColor Cyan
Write-Host "`nThis includes:" -ForegroundColor White
Write-Host "  - Redis (lightweight cache)" -ForegroundColor White
Write-Host "  - Backend API" -ForegroundColor White
Write-Host "  - Celery worker (1 worker)" -ForegroundColor White
Write-Host "  - Streamlit frontend" -ForegroundColor White
Write-Host "  - SQLite database (no PostgreSQL)" -ForegroundColor White

Write-Host "`nSkipped for space savings:" -ForegroundColor Gray
Write-Host "  - PostgreSQL (using SQLite instead)" -ForegroundColor Gray
Write-Host "  - Celery Beat (scheduled tasks)" -ForegroundColor Gray
Write-Host "  - Flower (monitoring UI)" -ForegroundColor Gray

Write-Host "`n⏳ Building and starting containers (first time: 3-5 minutes)..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray

# Start minimal docker-compose
docker-compose -f docker-compose.minimal.yml up --build

# Cleanup on exit
Write-Host "`n`nStopping containers..." -ForegroundColor Yellow
docker-compose -f docker-compose.minimal.yml down
Write-Host "✓ All containers stopped" -ForegroundColor Green
