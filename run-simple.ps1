# Simple YouTube Analyzer - Quick Start Script
# No backend, no Celery, no database - just run and analyze!

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "YouTube Watch History Analyzer - Simple" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✓ Virtual environment created`n" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Check if dependencies are installed
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$streamlitInstalled = pip list 2>$null | Select-String "streamlit"

if (-not $streamlitInstalled) {
    Write-Host "Installing dependencies (this may take 5-10 minutes)..." -ForegroundColor Yellow
    Write-Host "Note: If torch/sentence-transformers fail, the app will still work with basic clustering`n" -ForegroundColor Gray

    pip install -r requirements-simple.txt

    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n⚠️  Some packages failed to install." -ForegroundColor Yellow
        Write-Host "The app will work but may use basic clustering instead of AI.`n" -ForegroundColor Yellow
    } else {
        Write-Host "`n✓ All dependencies installed`n" -ForegroundColor Green
    }
} else {
    Write-Host "✓ Dependencies already installed`n" -ForegroundColor Green
}

# Run the app
Write-Host "Starting YouTube Analyzer..." -ForegroundColor Cyan
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "🚀 App starting! Your browser will open shortly." -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the app`n" -ForegroundColor Yellow

streamlit run simple_analyzer.py
