# CLI Guide - YouTube Audit Engine

Complete guide to using the Command-Line Interface for YouTube Audit Engine.

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Interactive Launcher](#interactive-launcher)
- [CLI Mode](#cli-mode)
- [Web Mode](#web-mode)
- [Usage Examples](#usage-examples)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

---

## Overview

YouTube Audit Engine now provides **two interfaces**:

1. **CLI Mode** - Terminal-based interface for automation and scripting
2. **Web Mode** - Browser-based Streamlit interface for interactive exploration

The new **Interactive Launcher** lets you easily switch between modes.

### Why Use CLI Mode?

- **Automation**: Integrate into scripts and workflows
- **Remote Access**: Use over SSH without X11 forwarding
- **Resource Efficient**: No browser required
- **Batch Processing**: Analyze multiple files programmatically
- **CI/CD Integration**: Run in automated pipelines

### Why Use Web Mode?

- **Visualizations**: Rich charts and graphs
- **User-Friendly**: Point-and-click interface
- **Interactive Exploration**: Drill down into results
- **Export Options**: Multiple format support

---

## Quick Start

### Interactive Launcher (Recommended)

The easiest way to get started:

**Linux/Mac:**
```bash
python launcher.py
```

**Windows PowerShell:**
```powershell
.\launcher.ps1
```

The launcher will:
1. Show a friendly menu
2. Check if backend is running
3. Automatically start services if needed
4. Launch your chosen interface

---

## Interactive Launcher

### Main Menu

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎬  YouTube Audit Engine                             ║
║                                                           ║
║     Analyze your YouTube watch history                   ║
║     Discover patterns, clusters, and insights            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Choose your interface:

  1. CLI Mode     - Command-line interface (terminal-based)
  2. Web Mode     - Browser-based interface (Streamlit)
  3. Help         - Setup and usage information
  4. Exit

Select mode [2]:
```

### Features

- **Auto-start backend**: Automatically detects and starts backend if needed
- **Health checking**: Verifies backend connectivity
- **Graceful shutdown**: Properly closes all services
- **Help system**: Built-in documentation

---

## CLI Mode

### Interactive CLI

Run the interactive CLI:

```bash
python -m cli.interface --interactive
```

**Menu Options:**
1. Analyze watch history file
2. Check backend status
3. Exit

### Direct Analysis

Analyze a file directly:

```bash
python -m cli.interface watch-history.json
```

**With output file:**
```bash
python -m cli.interface watch-history.json -o results.json
```

### Command-Line Options

```bash
python -m cli.interface [OPTIONS] [FILE]

Arguments:
  FILE                    Path to watch-history.json file

Options:
  --api-url URL           Backend API URL (default: http://localhost:8000)
  --api-token TOKEN       API bearer token for authentication
  --api-key KEY           Google API key for YouTube Data API
  --output, -o PATH       Output file path for results (JSON)
  --interactive, -i       Run in interactive mode
  --check-health          Check backend health and exit
  -h, --help              Show help message
```

### Environment Variables

The CLI respects these environment variables:

```bash
export API_URL=http://localhost:8000
export API_BEARER_TOKEN=your-token-here
export GOOGLE_API_KEY=your-google-api-key

# Now you can run without flags
python -m cli.interface watch-history.json
```

---

## Web Mode

### Starting Web Interface

Via launcher:
```bash
python launcher.py
# Select option 2
```

Or directly:
```bash
streamlit run frontend/app.py
```

Access at: **http://localhost:8501**

### Features

- Drag-and-drop file upload
- Real-time progress tracking
- Interactive visualizations
- Cluster exploration
- Export to PDF/JSON

---

## Usage Examples

### Example 1: Quick Analysis

```bash
# Start the launcher
python launcher.py

# Select CLI mode (option 1)
# Enter path to your watch-history.json
# View results in terminal
# Optionally export to JSON
```

### Example 2: Automated Script

```bash
#!/bin/bash
# analyze.sh - Automated analysis script

# Start backend (if not running)
python backend/main.py &
BACKEND_PID=$!
sleep 5

# Run analysis
python -m cli.interface \
    watch-history.json \
    --api-key "$GOOGLE_API_KEY" \
    --output "results-$(date +%Y%m%d).json"

# Stop backend
kill $BACKEND_PID
```

### Example 3: Health Check

```bash
# Check if backend is healthy
python -m cli.interface --check-health

# Use in scripts
if python -m cli.interface --check-health; then
    echo "Backend is ready"
else
    echo "Backend is down"
    exit 1
fi
```

### Example 4: Batch Processing

```bash
# Process multiple files
for file in data/*.json; do
    echo "Processing $file..."
    python -m cli.interface "$file" -o "results/${file%.json}_results.json"
done
```

### Example 5: Remote Analysis via SSH

```bash
# On remote server (no GUI needed)
ssh user@server

# Clone and setup
git clone https://github.com/yourusername/YouTubeAudit.git
cd YouTubeAudit
pip install -r requirements.txt

# Start backend
python backend/main.py &

# Run CLI analysis
python -m cli.interface watch-history.json

# Results displayed in terminal
```

---

## Advanced Usage

### Custom API Endpoint

```bash
# Connect to remote backend
python -m cli.interface \
    --api-url https://api.example.com \
    --api-token "$REMOTE_TOKEN" \
    watch-history.json
```

### Programmatic Usage

```python
# script.py
from cli.interface import YouTubeAuditCLI

# Create client
cli = YouTubeAuditCLI(
    api_url="http://localhost:8000",
    api_token="your-token"
)

# Check health
if cli.check_health():
    # Analyze file
    results = cli.analyze_watch_history(
        "watch-history.json",
        google_api_key="your-key"
    )

    # Export results
    if results:
        cli.export_results(results, "output.json")

        # Process results programmatically
        total_videos = results['summary']['total_videos']
        print(f"Analyzed {total_videos} videos")
```

### Integration with Other Tools

**With jq (JSON processing):**
```bash
# Extract top channels
python -m cli.interface watch-history.json -o results.json
cat results.json | jq '.top_channels[] | .channel_name'
```

**With pandas (data analysis):**
```python
import pandas as pd
import json

# Load CLI results
with open('results.json') as f:
    results = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(results['top_channels'])
print(df.head())
```

---

## Troubleshooting

### Backend Connection Failed

**Problem:**
```
✗ Cannot connect to backend at http://localhost:8000
Make sure the backend is running:
  python backend/main.py
```

**Solutions:**
1. Start backend manually:
   ```bash
   python backend/main.py
   ```

2. Use launcher (auto-starts):
   ```bash
   python launcher.py
   ```

3. Check if port is in use:
   ```bash
   # Linux/Mac
   lsof -i :8000

   # Windows
   netstat -ano | findstr :8000
   ```

### File Not Found

**Problem:**
```
✗ File not found: watch-history.json
```

**Solutions:**
1. Use absolute path:
   ```bash
   python -m cli.interface /full/path/to/watch-history.json
   ```

2. Check current directory:
   ```bash
   ls -la watch-history.json
   ```

3. Download from Google Takeout:
   - Visit https://takeout.google.com
   - Select "YouTube and YouTube Music"
   - Download "watch-history.json"

### API Key Required

**Problem:**
```
Enter your Google API Key:
```

**Solutions:**
1. Set environment variable:
   ```bash
   export GOOGLE_API_KEY=your-key-here
   python -m cli.interface watch-history.json
   ```

2. Pass as argument:
   ```bash
   python -m cli.interface --api-key your-key watch-history.json
   ```

3. Add to .env file:
   ```
   GOOGLE_API_KEY=your-key-here
   ```

### Module Not Found

**Problem:**
```
ModuleNotFoundError: No module named 'cli'
```

**Solutions:**
1. Set PYTHONPATH:
   ```bash
   export PYTHONPATH=$(pwd)
   python -m cli.interface watch-history.json
   ```

2. Run from project root:
   ```bash
   cd YouTubeAudit  # Make sure you're in project root
   python -m cli.interface watch-history.json
   ```

### Rich/Streamlit Not Installed

**Problem:**
```
ModuleNotFoundError: No module named 'rich'
```

**Solutions:**
```bash
# Install dependencies
pip install -r requirements.txt

# Or install specific package
pip install rich streamlit
```

### Windows-Specific Issues

**PowerShell Execution Policy:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Celery on Windows:**
```powershell
pip install eventlet
celery -A backend.celery_app worker --pool=solo
```

**Path Issues:**
```powershell
# Use quotes for paths with spaces
python -m cli.interface "C:\Users\Name\Downloads\watch-history.json"
```

---

## Tips and Best Practices

### 1. Use Environment Variables

Create a `.env` file:
```bash
API_URL=http://localhost:8000
API_BEARER_TOKEN=your-secure-token
GOOGLE_API_KEY=your-google-api-key
```

### 2. Keep Backend Running

For multiple analyses:
```bash
# Terminal 1: Backend
python backend/main.py

# Terminal 2: CLI analyses
python -m cli.interface file1.json -o results1.json
python -m cli.interface file2.json -o results2.json
```

### 3. Export Results

Always export for later analysis:
```bash
python -m cli.interface watch-history.json -o results.json
```

### 4. Check Health First

Before running analyses:
```bash
python -m cli.interface --check-health
```

### 5. Use Launcher for Convenience

The launcher handles backend startup automatically:
```bash
python launcher.py  # Easiest way
```

---

## Keyboard Shortcuts

### CLI Mode
- `Ctrl+C` - Cancel current operation
- `Ctrl+D` - Exit interactive mode
- `Enter` - Accept default option

### Web Mode
- `Ctrl+C` (in terminal) - Stop Streamlit
- Browser refresh - Reload interface

---

## Next Steps

1. **Read the full documentation:**
   - [README.md](README.md) - Project overview
   - [ARCHITECTURE.md](ARCHITECTURE.md) - System design
   - [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows instructions

2. **Explore examples:**
   - Try the interactive launcher
   - Analyze your watch history
   - Export and visualize results

3. **Automate workflows:**
   - Create bash/PowerShell scripts
   - Integrate with cron/Task Scheduler
   - Build custom tools with the API

4. **Contribute:**
   - Report issues
   - Suggest features
   - Submit pull requests

---

## Support

- **Documentation**: See README.md and ARCHITECTURE.md
- **Issues**: https://github.com/yourusername/YouTubeAudit/issues
- **Discussions**: https://github.com/yourusername/YouTubeAudit/discussions

---

**Happy Analyzing! 🎬📊**
