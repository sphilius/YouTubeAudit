# Windows 11 Setup Guide

## Option 1: Native Windows Setup (No Docker)

### Prerequisites
```powershell
# Check Python version (requires 3.10+)
python --version

# Check pip
pip --version
```

### Install PostgreSQL (Windows)
1. **Download:** https://www.postgresql.org/download/windows/
2. **Install:** Run installer, use these settings:
   - Port: 5432
   - Username: postgres
   - Password: (set your password)
3. **Create database:**
```powershell
# Open psql (search "SQL Shell" in Start Menu)
CREATE DATABASE youtube_audit;
CREATE USER youtube_audit WITH PASSWORD 'youtube_audit_password';
GRANT ALL PRIVILEGES ON DATABASE youtube_audit TO youtube_audit;
```

### Install Redis (Windows)
**Option A: Memurai (Redis for Windows)**
1. Download: https://www.memurai.com/get-memurai
2. Install and start service
3. Runs on port 6379 by default

**Option B: Redis via WSL2**
```powershell
# Install WSL2
wsl --install

# In WSL2 terminal
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

**Option C: Use fakeredis (Testing only)**
```powershell
pip install fakeredis
```

### Install Python Dependencies
```powershell
# Navigate to project
cd YouTubeAudit

# Create virtual environment
python -m venv venv

# Activate (PowerShell)
.\venv\Scripts\Activate.ps1

# If you get execution policy error:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables (Windows)
```powershell
# Create .env file in project root
@"
# Database (adjust if using different password)
DATABASE_URL=postgresql://youtube_audit:youtube_audit_password@localhost:5432/youtube_audit

# Redis (or use fakeredis)
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# YouTube API
GOOGLE_API_KEY=your-api-key-here

# Auth
API_BEARER_TOKEN=your-secure-token-here

# Environment
ENVIRONMENT=development
DEBUG=False
"@ | Out-File -FilePath .env -Encoding utf8
```

### Run Backend (Windows)
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Set PYTHONPATH
$env:PYTHONPATH = "$PWD"

# Run Flask
python backend/main.py
```

### Run Celery Worker (Windows)
```powershell
# Open NEW PowerShell window
cd YouTubeAudit
.\venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"

# Celery on Windows requires eventlet
pip install eventlet

# Run worker
celery -A backend.celery_app worker --pool=solo --loglevel=info
```

### Run Frontend (Windows)
```powershell
# Open NEW PowerShell window
cd YouTubeAudit
.\venv\Scripts\Activate.ps1

# Run Streamlit
streamlit run frontend/app.py
```

---

## Option 2: Docker Desktop for Windows

### Install Docker Desktop
1. Download: https://www.docker.com/products/docker-desktop/
2. Install and restart
3. Enable WSL2 integration (Settings > Resources > WSL Integration)

### Run with Docker
```powershell
# Navigate to project
cd YouTubeAudit

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

---

## Option 3: Cloud Services (No Local Install)

### Use Cloud Database & Cache
```powershell
# .env configuration
DATABASE_URL=postgresql://user:pass@your-postgres-host.com:5432/youtube_audit
REDIS_URL=redis://your-redis-host.com:6379/0

# Free options:
# - PostgreSQL: https://supabase.com (free tier)
# - Redis: https://upstash.com (free tier)
# - Redis: https://redis.com/try-free/
```

---

## Option 4: SQLite + In-Memory (Simplest, Testing Only)

### Modify config for SQLite
```python
# backend/config.py
database_url: str = Field(
    default="sqlite:///./youtube_audit.db",  # SQLite instead of PostgreSQL
    description="Database connection URL"
)

redis_url: str = Field(
    default="redis://localhost:6379/0",  # Can use fakeredis
    description="Redis connection URL"
)
```

### Use fakeredis
```python
# backend/cache.py
import fakeredis

def get_redis_client():
    # For testing without Redis
    return fakeredis.FakeRedis(decode_responses=True)
```

### Run
```powershell
# No PostgreSQL or Redis needed!
python backend/main.py
```

---

## Testing the API (Windows)

### PowerShell (instead of curl)
```powershell
# Test health check
Invoke-WebRequest -Uri http://localhost:8000/ -Method GET

# Test analyze endpoint
$headers = @{
    "Authorization" = "Bearer your-token-here"
}

$form = @{
    file = Get-Item "path\to\watch-history.json"
    api_key = "your-google-api-key"
}

Invoke-WebRequest -Uri http://localhost:8000/analyze `
    -Method POST `
    -Headers $headers `
    -Form $form
```

### Using Python Requests
```python
# test_api.py
import requests

# Health check
response = requests.get('http://localhost:8000/')
print(response.json())

# Analyze
files = {'file': open('watch-history.json', 'rb')}
data = {'api_key': 'your-api-key'}
headers = {'Authorization': 'Bearer your-token'}

response = requests.post(
    'http://localhost:8000/analyze',
    files=files,
    data=data,
    headers=headers
)
print(response.json())
```

---

## Troubleshooting Windows Issues

### Issue: PowerShell execution policy
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Port already in use
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <pid> /F
```

### Issue: Module not found
```powershell
# Ensure PYTHONPATH is set
$env:PYTHONPATH = "$PWD"

# Or use -m flag
python -m backend.main
```

### Issue: Celery on Windows
```powershell
# Celery 5.x requires eventlet or gevent on Windows
pip install eventlet

# Use solo pool (single worker)
celery -A backend.celery_app worker --pool=solo
```

### Issue: Redis connection refused
```powershell
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If using Memurai
net start Memurai

# If using WSL2
wsl
sudo service redis-server status
```

---

## Quick Start Script (Windows)

### setup_windows.ps1
```powershell
# YouTube Audit Engine - Windows Setup Script

Write-Host "YouTube Audit Engine - Windows Setup" -ForegroundColor Green

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Activate
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Create .env if not exists
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    @"
DATABASE_URL=sqlite:///./youtube_audit.db
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
GOOGLE_API_KEY=
API_BEARER_TOKEN=dev-token-12345678
ENVIRONMENT=development
DEBUG=True
"@ | Out-File -FilePath .env -Encoding utf8
}

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env and add your GOOGLE_API_KEY"
Write-Host "2. Run: python backend/main.py"
Write-Host "3. In new terminal: streamlit run frontend/app.py"
```

### run_windows.ps1
```powershell
# YouTube Audit Engine - Windows Run Script

param(
    [string]$Component = "all"
)

$env:PYTHONPATH = $PWD

switch ($Component) {
    "backend" {
        Write-Host "Starting Backend..." -ForegroundColor Green
        python backend/main.py
    }
    "frontend" {
        Write-Host "Starting Frontend..." -ForegroundColor Green
        streamlit run frontend/app.py
    }
    "worker" {
        Write-Host "Starting Celery Worker..." -ForegroundColor Green
        celery -A backend.celery_app worker --pool=solo --loglevel=info
    }
    "all" {
        Write-Host "Starting all components..." -ForegroundColor Green
        Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow

        # Start backend in background
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $PWD; .\venv\Scripts\Activate.ps1; `$env:PYTHONPATH='$PWD'; python backend/main.py"

        Start-Sleep -Seconds 3

        # Start frontend in background
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $PWD; .\venv\Scripts\Activate.ps1; streamlit run frontend/app.py"

        Write-Host "Services started!" -ForegroundColor Green
        Write-Host "Backend: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "Frontend: http://localhost:8501" -ForegroundColor Cyan
    }
}
```

---

## Summary: Best Options for Windows 11

### For Quick Testing (Easiest)
1. Install Python
2. Use SQLite (no PostgreSQL needed)
3. Use fakeredis (no Redis needed)
4. Run: `python backend/main.py`

### For Full Features (Recommended)
1. Install Docker Desktop for Windows
2. Run: `docker-compose up`
3. Access at http://localhost:8501

### For Production/Development (Most Control)
1. Install PostgreSQL + Memurai (or Redis via WSL2)
2. Use virtual environment
3. Run backend, worker, frontend separately

Choose based on your needs! 🚀
