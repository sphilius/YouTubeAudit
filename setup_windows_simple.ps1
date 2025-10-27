# Simple Windows Setup Script for YouTube Audit Engine
# Uses SQLite + fakeredis (no external services required)

Write-Host "YouTube Audit Engine - Simple Windows Setup" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "1. Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "   Found: $pythonVersion"

if ($pythonVersion -notmatch "Python 3\.1[0-9]") {
    Write-Host "   ERROR: Python 3.10+ is required" -ForegroundColor Red
    Write-Host "   Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

Write-Host "   ✓ Python version OK" -ForegroundColor Green
Write-Host ""

# Create virtual environment
Write-Host "2. Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "   Virtual environment already exists, skipping..." -ForegroundColor Gray
} else {
    python -m venv venv
    Write-Host "   ✓ Virtual environment created" -ForegroundColor Green
}
Write-Host ""

# Activate virtual environment
Write-Host "3. Activating virtual environment..." -ForegroundColor Yellow
try {
    & .\venv\Scripts\Activate.ps1
    Write-Host "   ✓ Virtual environment activated" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "   Run this command to allow script execution:" -ForegroundColor Yellow
    Write-Host "   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Install dependencies
Write-Host "4. Installing dependencies..." -ForegroundColor Yellow
Write-Host "   This may take several minutes..." -ForegroundColor Gray

# Install fakeredis first for testing
pip install fakeredis[lua] --quiet
Write-Host "   ✓ fakeredis installed" -ForegroundColor Green

# Install main requirements
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ All dependencies installed" -ForegroundColor Green
} else {
    Write-Host "   WARNING: Some dependencies may have failed" -ForegroundColor Yellow
}
Write-Host ""

# Create .env file for testing
Write-Host "5. Creating .env configuration..." -ForegroundColor Yellow
$envContent = @"
# SQLite Database (no installation required)
DATABASE_URL=sqlite:///./youtube_audit.db

# fakeredis (no installation required)
REDIS_URL=fakeredis://localhost:6379/0
CELERY_BROKER_URL=fakeredis://localhost:6379/0
CELERY_RESULT_BACKEND=fakeredis://localhost:6379/1

# YouTube API Key (REQUIRED - add your key here)
GOOGLE_API_KEY=your-google-api-key-here

# Authentication
API_BEARER_TOKEN=dev-token-12345678

# Environment
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# Testing mode
TESTING_MODE=True
"@

$envContent | Out-File -FilePath ".env" -Encoding utf8
Write-Host "   ✓ .env file created" -ForegroundColor Green
Write-Host ""

# Create uploads directory
Write-Host "6. Creating required directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "uploads" | Out-Null
Write-Host "   ✓ Directories created" -ForegroundColor Green
Write-Host ""

# Initialize database
Write-Host "7. Initializing database..." -ForegroundColor Yellow
$env:PYTHONPATH = $PWD
Write-Host "   Creating database tables..." -ForegroundColor Gray

# Check if alembic is configured
if (Test-Path "alembic/versions/20250121_0000_001_initial_schema.py") {
    python -c "from backend.database import Base, get_engine; Base.metadata.create_all(get_engine()); print('Database initialized')"
    Write-Host "   ✓ Database initialized" -ForegroundColor Green
} else {
    Write-Host "   ⚠ Database migrations not found, will initialize on first run" -ForegroundColor Yellow
}
Write-Host ""

# Final instructions
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Edit .env file and add your Google API Key!" -ForegroundColor Yellow
Write-Host ""
Write-Host "To get a Google API Key:" -ForegroundColor Cyan
Write-Host "1. Go to: https://console.cloud.google.com" -ForegroundColor White
Write-Host "2. Create a new project (or select existing)" -ForegroundColor White
Write-Host "3. Enable YouTube Data API v3" -ForegroundColor White
Write-Host "4. Create credentials (API Key)" -ForegroundColor White
Write-Host "5. Copy the key and paste it in .env file" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env file - Add your GOOGLE_API_KEY" -ForegroundColor White
Write-Host "2. Run: .\run_windows_simple.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Or manually:" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "   python launcher.py" -ForegroundColor White
Write-Host ""
