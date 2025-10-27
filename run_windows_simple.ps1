# Run YouTube Audit Engine on Windows (Simple Mode)
# Uses SQLite + fakeredis - no external services needed

Write-Host "YouTube Audit Engine - Starting..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "1. Activating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
    Write-Host "   ✓ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "   ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "   Run setup_windows_simple.ps1 first" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Set PYTHONPATH
$env:PYTHONPATH = $PWD
Write-Host "2. Setting PYTHONPATH..." -ForegroundColor Yellow
Write-Host "   PYTHONPATH = $env:PYTHONPATH" -ForegroundColor Gray
Write-Host ""

# Check .env file
Write-Host "3. Checking configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "   ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "   Run setup_windows_simple.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Check if API key is set
$envContent = Get-Content ".env" -Raw
if ($envContent -match "GOOGLE_API_KEY=your-google-api-key-here") {
    Write-Host "   WARNING: Google API Key not set in .env!" -ForegroundColor Yellow
    Write-Host "   The app will start but video enrichment will fail" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "   Continue anyway? (y/n)"
    if ($continue -ne "y") {
        Write-Host "   Please edit .env and add your GOOGLE_API_KEY" -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "   ✓ Configuration looks good" -ForegroundColor Green
}
Write-Host ""

# Initialize database if needed
Write-Host "4. Checking database..." -ForegroundColor Yellow
if (-not (Test-Path "youtube_audit.db")) {
    Write-Host "   Creating database..." -ForegroundColor Gray
    python -c @"
from backend.database import Base, get_engine
Base.metadata.create_all(get_engine())
print('Database created successfully')
"@
    Write-Host "   ✓ Database initialized" -ForegroundColor Green
} else {
    Write-Host "   ✓ Database exists" -ForegroundColor Green
}
Write-Host ""

# Ask user which mode to run
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Select Mode:" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Web Interface (Streamlit)" -ForegroundColor White
Write-Host "   - Browser-based UI" -ForegroundColor Gray
Write-Host "   - Rich visualizations" -ForegroundColor Gray
Write-Host "   - Real-time progress" -ForegroundColor Gray
Write-Host ""
Write-Host "2. CLI Interface" -ForegroundColor White
Write-Host "   - Terminal-based" -ForegroundColor Gray
Write-Host "   - Good for automation" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Interactive Launcher" -ForegroundColor White
Write-Host "   - Choose mode each time" -ForegroundColor Gray
Write-Host ""
$mode = Read-Host "Select mode (1/2/3) [1]"

if (-not $mode) { $mode = "1" }

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan

# Start backend in background
Write-Host "5. Starting backend server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($WorkingDir)
    Set-Location $WorkingDir
    $env:PYTHONPATH = $WorkingDir
    & "$WorkingDir\venv\Scripts\Activate.ps1"
    python backend/main.py
} -ArgumentList $PWD

Start-Sleep -Seconds 3

# Check if backend started
$backendRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        $backendRunning = $true
    }
} catch {
    # Backend might still be starting
}

if ($backendRunning) {
    Write-Host "   ✓ Backend running on http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "   ⚠ Backend may still be starting..." -ForegroundColor Yellow
    Write-Host "   Waiting a bit longer..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}
Write-Host ""

# Start Celery worker in background
Write-Host "6. Starting Celery worker..." -ForegroundColor Yellow
Write-Host "   Note: Using solo pool (Windows compatible)" -ForegroundColor Gray

$celeryJob = Start-Job -ScriptBlock {
    param($WorkingDir)
    Set-Location $WorkingDir
    $env:PYTHONPATH = $WorkingDir
    & "$WorkingDir\venv\Scripts\Activate.ps1"
    celery -A backend.celery_app worker --pool=solo --loglevel=info
} -ArgumentList $PWD

Start-Sleep -Seconds 2
Write-Host "   ✓ Celery worker started" -ForegroundColor Green
Write-Host ""

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "System Ready!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Launch selected mode
switch ($mode) {
    "1" {
        Write-Host "7. Launching Web Interface..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "   Opening browser at http://localhost:8501" -ForegroundColor Gray
        Write-Host "   Press Ctrl+C to stop all services" -ForegroundColor Gray
        Write-Host ""

        try {
            streamlit run frontend/app.py
        } finally {
            Write-Host "`nStopping services..." -ForegroundColor Yellow
            Stop-Job $backendJob, $celeryJob -ErrorAction SilentlyContinue
            Remove-Job $backendJob, $celeryJob -ErrorAction SilentlyContinue
            Write-Host "All services stopped" -ForegroundColor Green
        }
    }
    "2" {
        Write-Host "7. Launching CLI Interface..." -ForegroundColor Yellow
        Write-Host ""

        try {
            python -m cli.interface --interactive
        } finally {
            Write-Host "`nStopping services..." -ForegroundColor Yellow
            Stop-Job $backendJob, $celeryJob -ErrorAction SilentlyContinue
            Remove-Job $backendJob, $celeryJob -ErrorAction SilentlyContinue
            Write-Host "All services stopped" -ForegroundColor Green
        }
    }
    "3" {
        Write-Host "7. Launching Interactive Launcher..." -ForegroundColor Yellow
        Write-Host ""

        try {
            python launcher.py
        } finally {
            Write-Host "`nStopping services..." -ForegroundColor Yellow
            Stop-Job $backendJob, $celeryJob -ErrorAction SilentlyContinue
            Remove-Job $backendJob, $celeryJob -ErrorAction SilentlyContinue
            Write-Host "All services stopped" -ForegroundColor Green
        }
    }
}
