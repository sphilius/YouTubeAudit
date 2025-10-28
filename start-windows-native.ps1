# YouTube Audit Engine - Windows Native Startup Script
# Runs everything without Docker

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "YouTube Audit Engine - Windows Native" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check Python version
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python 3\.1[0-9]") {
        Write-Host "✓ Python installed: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "✗ Python 3.10+ required, found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Python not found! Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "✗ Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run setup_windows_simple.ps1 first" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Virtual environment found" -ForegroundColor Green

# Create .env for Windows if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file for Windows..." -ForegroundColor Yellow
    @"
# YouTube Audit Engine - Windows Native Configuration

ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Database (SQLite)
DATABASE_URL=sqlite:///./youtube_audit.db

# Redis (fakeredis - no server required)
REDIS_URL=fakeredis://localhost:6379/0
CELERY_BROKER_URL=fakeredis://localhost:6379/0
CELERY_RESULT_BACKEND=fakeredis://localhost:6379/1

# API Settings
API_URL=http://localhost:8000
ALLOWED_ORIGINS=*

# Security
SECRET_KEY=dev-secret-key-for-testing-only
API_BEARER_TOKEN=

# File Upload
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=104857600

# YouTube API (add your key)
YOUTUBE_API_KEY=

# Logging
LOG_LEVEL=INFO
"@ | Out-File -FilePath .env -Encoding utf8
    Write-Host "✓ .env file created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
$env:PYTHONPATH = $PWD

Write-Host "✓ Virtual environment activated" -ForegroundColor Green

# Create uploads directory
if (-not (Test-Path "uploads")) {
    New-Item -ItemType Directory -Path "uploads" | Out-Null
    Write-Host "✓ Created uploads directory" -ForegroundColor Green
}

Write-Host "`nStarting services..." -ForegroundColor Yellow
Write-Host "This will start 3 background services:`n" -ForegroundColor White
Write-Host "  1. Backend API (port 8000)" -ForegroundColor White
Write-Host "  2. Celery Worker (background tasks)" -ForegroundColor White
Write-Host "  3. Streamlit Frontend (port 8501)" -ForegroundColor White

# Start backend in background
Write-Host "`n[1/3] Starting Backend API..." -ForegroundColor Cyan
$backendJob = Start-Job -ScriptBlock {
    param($projectPath)
    Set-Location $projectPath
    & .\venv\Scripts\Activate.ps1
    $env:PYTHONPATH = $PWD
    python backend/main.py
} -ArgumentList $PWD

Start-Sleep -Seconds 3

# Check if backend started
$backendOutput = Receive-Job -Job $backendJob -Keep
if ($backendJob.State -eq "Failed") {
    Write-Host "✗ Backend failed to start!" -ForegroundColor Red
    Receive-Job -Job $backendJob
    Stop-Job -Job $backendJob
    Remove-Job -Job $backendJob
    exit 1
}

Write-Host "✓ Backend API starting on http://localhost:8000" -ForegroundColor Green
Start-Sleep -Seconds 2

# Start Celery worker in background
Write-Host "[2/3] Starting Celery Worker..." -ForegroundColor Cyan
$celeryJob = Start-Job -ScriptBlock {
    param($projectPath)
    Set-Location $projectPath
    & .\venv\Scripts\Activate.ps1
    $env:PYTHONPATH = $PWD
    celery -A backend.celery_app worker --pool=solo --loglevel=info
} -ArgumentList $PWD

Start-Sleep -Seconds 5

# Check if celery started
if ($celeryJob.State -eq "Failed") {
    Write-Host "✗ Celery worker failed to start!" -ForegroundColor Red
    Receive-Job -Job $celeryJob
    Stop-Job -Job $backendJob
    Remove-Job -Job $backendJob
    Stop-Job -Job $celeryJob
    Remove-Job -Job $celeryJob
    exit 1
}

Write-Host "✓ Celery Worker started" -ForegroundColor Green

# Start frontend in foreground (so we can see logs)
Write-Host "[3/3] Starting Streamlit Frontend..." -ForegroundColor Cyan
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "ALL SERVICES RUNNING!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nAccess the app at: http://localhost:8501" -ForegroundColor Cyan
Write-Host "Backend API at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop all services`n" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Green

# Set API_URL for frontend
$env:API_URL = "http://localhost:8000"

try {
    streamlit run frontend/app.py
} finally {
    # Cleanup on exit
    Write-Host "`n`nStopping all services..." -ForegroundColor Yellow

    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -ErrorAction SilentlyContinue

    Stop-Job -Job $celeryJob -ErrorAction SilentlyContinue
    Remove-Job -Job $celeryJob -ErrorAction SilentlyContinue

    Write-Host "✓ All services stopped" -ForegroundColor Green
}
