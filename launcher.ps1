# YouTube Audit Engine - Windows PowerShell Launcher
# Provides interactive menu to choose between CLI and Web modes

$ErrorActionPreference = "Stop"

# Colors
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Show-Banner {
    Clear-Host
    Write-ColorOutput Cyan @"

╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎬  YouTube Audit Engine                             ║
║                                                           ║
║     Analyze your YouTube watch history                   ║
║     Discover patterns, clusters, and insights            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

"@
}

function Test-BackendRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Start-Backend {
    Write-ColorOutput Cyan "Starting backend server..."

    # Set PYTHONPATH
    $env:PYTHONPATH = $PWD.Path

    # Start backend in background
    $backendJob = Start-Job -ScriptBlock {
        param($WorkingDir)
        Set-Location $WorkingDir
        $env:PYTHONPATH = $WorkingDir
        python backend/main.py
    } -ArgumentList $PWD.Path

    # Wait for startup
    Start-Sleep -Seconds 3

    if (Test-BackendRunning) {
        Write-ColorOutput Green "✓ Backend started successfully"
        return $backendJob
    }
    else {
        Write-ColorOutput Yellow "⚠ Backend may still be starting..."
        return $backendJob
    }
}

function Start-CLI {
    Clear-Host
    Write-ColorOutput Cyan @"
╔═══════════════════════════════════════════════════════════╗
║          YouTube Audit Engine - CLI Mode                  ║
╚═══════════════════════════════════════════════════════════╝

"@

    # Check if backend is running
    if (-not (Test-BackendRunning)) {
        Write-ColorOutput Yellow "`nBackend is not running."
        $start = Read-Host "Start backend automatically? (yes/no) [yes]"

        if (-not $start -or $start -eq "yes") {
            $backendJob = Start-Backend
        }
        else {
            Write-ColorOutput Yellow "`nPlease start the backend manually:"
            Write-Host "  python backend/main.py"
            Write-Host "`nThen restart this launcher."
            Read-Host "`nPress Enter to continue"
            return
        }
    }

    # Set PYTHONPATH
    $env:PYTHONPATH = $PWD.Path

    # Run CLI
    Write-ColorOutput Cyan "`nLaunching CLI interface...`n"
    python -m cli.interface --interactive
}

function Start-Web {
    Clear-Host
    Write-ColorOutput Cyan @"
╔═══════════════════════════════════════════════════════════╗
║          YouTube Audit Engine - Web Mode                  ║
╚═══════════════════════════════════════════════════════════╝

"@

    $backendJob = $null

    # Check if backend is running
    if (-not (Test-BackendRunning)) {
        Write-ColorOutput Yellow "`nBackend is not running."
        $start = Read-Host "Start backend automatically? (yes/no) [yes]"

        if (-not $start -or $start -eq "yes") {
            $backendJob = Start-Backend
        }
        else {
            Write-ColorOutput Yellow "`nPlease start the backend manually:"
            Write-Host "  python backend/main.py"
            Read-Host "`nPress Enter to continue"
            return
        }
    }

    # Launch Streamlit
    Write-ColorOutput Cyan "`nLaunching Streamlit web interface..."
    Write-Host "The web interface will open in your browser.`n"

    try {
        streamlit run frontend/app.py
    }
    catch {
        Write-ColorOutput Red "Error launching Streamlit: $_"
    }
    finally {
        if ($backendJob) {
            Write-ColorOutput Cyan "Stopping backend server..."
            Stop-Job $backendJob
            Remove-Job $backendJob
        }
    }
}

function Show-Help {
    Clear-Host
    Write-ColorOutput Cyan @"
╔═══════════════════════════════════════════════════════════╗
║          YouTube Audit Engine - Help                      ║
╚═══════════════════════════════════════════════════════════╝

"@

    Write-Host @"
GETTING STARTED:

1. Make sure you have a .env file with your configuration:
   - GOOGLE_API_KEY (required for metadata enrichment)
   - DATABASE_URL (PostgreSQL connection)
   - REDIS_URL (Redis connection)
   - API_BEARER_TOKEN (for API authentication)

2. Install dependencies:
   pip install -r requirements.txt

3. Start required services (if not using Docker):
   - PostgreSQL database
   - Redis server (or Memurai on Windows)

CLI MODE:
- Terminal-based interface
- Perfect for automation and scripting
- Can be used without a web browser

  Usage:
    python -m cli.interface watch-history.json
    python -m cli.interface --interactive

WEB MODE:
- Browser-based interface using Streamlit
- Rich visualizations and charts
- Interactive data exploration

  Access at: http://localhost:8501

WINDOWS SETUP:
See WINDOWS_SETUP.md for detailed Windows-specific instructions including:
- Native Windows setup (no Docker)
- Docker Desktop setup
- SQLite + fakeredis (testing only)
- Troubleshooting common issues

DOCUMENTATION:
- README.md - Overview and features
- ARCHITECTURE.md - System design
- FEATURE_RECOMMENDATIONS.md - Roadmap
- WINDOWS_SETUP.md - Windows-specific guide

TROUBLESHOOTING:
- Backend not starting: Check Python version (3.10+)
- Database errors: Verify DATABASE_URL in .env
- Redis errors: Install Memurai or use WSL2
- Port conflicts: Check netstat -ano | findstr :8000

"@

    Read-Host "`nPress Enter to return to main menu"
}

function Show-MainMenu {
    Show-Banner

    Write-Host "Choose your interface:`n"
    Write-Host "  [1] CLI Mode     - Command-line interface (terminal-based)"
    Write-Host "  [2] Web Mode     - Browser-based interface (Streamlit)"
    Write-Host "  [3] Help         - Setup and usage information"
    Write-Host "  [4] Exit`n"

    $choice = Read-Host "Select mode [2]"
    if (-not $choice) { $choice = "2" }

    return $choice
}

# Main loop
try {
    while ($true) {
        $choice = Show-MainMenu

        switch ($choice) {
            "1" { Start-CLI }
            "2" { Start-Web }
            "3" { Show-Help }
            "4" {
                Clear-Host
                Write-ColorOutput Cyan "`nThank you for using YouTube Audit Engine!"
                Write-Host "Star us on GitHub if you found this useful 🌟`n"
                exit 0
            }
            default {
                Write-ColorOutput Yellow "Invalid choice. Please select 1-4."
                Start-Sleep -Seconds 2
            }
        }
    }
}
catch {
    Write-ColorOutput Red "`nError: $_"
    Read-Host "`nPress Enter to exit"
    exit 1
}
