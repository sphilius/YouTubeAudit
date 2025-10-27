# Testing MVP on Windows 11 (No Docker Required)

This guide will help you test the YouTube Audit Engine MVP on Windows 11 **without Docker**.

We'll use **SQLite + fakeredis** for the simplest setup - no database or Redis installation needed!

---

## Prerequisites

### Required:
- **Windows 11** ✅ (You have this)
- **Python 3.10+** (Download from https://www.python.org/downloads/)
- **PowerShell** (Built into Windows)
- **YouTube Data API Key** (We'll get this)

### NOT Required:
- ❌ Docker Desktop
- ❌ PostgreSQL
- ❌ Redis
- ❌ WSL2

---

## Step 1: Get Your YouTube API Key

1. Go to https://console.cloud.google.com
2. Create a new project (or select existing)
3. Click "Enable APIs and Services"
4. Search for "YouTube Data API v3"
5. Click "Enable"
6. Go to "Credentials" → "Create Credentials" → "API Key"
7. Copy your API key (looks like: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXX`)

**Keep this handy - you'll need it in Step 4!**

---

## Step 2: Get Your Watch History File

1. Go to https://takeout.google.com
2. Click "Deselect all"
3. Scroll down and select **"YouTube and YouTube Music"**
4. Click "All YouTube data included"
5. Deselect everything EXCEPT "watch-history" (or select all if you want)
6. Click "Next step" → "Create export"
7. Wait for the email (can take a few hours)
8. Download the file (will be a `.zip` file)
9. Extract it and find `watch-history.json`

**Save this file somewhere easy to find!**

---

## Step 3: Setup the Application

Open **PowerShell** (press `Win + X` → select "Windows PowerShell" or "Terminal")

```powershell
# Navigate to the project directory
cd path\to\YouTubeAudit

# For example:
cd C:\Users\YourName\Downloads\YouTubeAudit

# Run the setup script
.\setup_windows_simple.ps1
```

**What this does:**
- ✅ Checks Python version
- ✅ Creates virtual environment
- ✅ Installs all dependencies (may take 5-10 minutes)
- ✅ Creates `.env` configuration file
- ✅ Sets up SQLite database
- ✅ Installs fakeredis (no Redis server needed!)

**If you get an error about execution policy:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then run setup script again
```

---

## Step 4: Add Your API Key

After setup completes, you need to add your YouTube API key:

1. Open `.env` file in the project folder (use Notepad, VS Code, etc.)
2. Find the line that says:
   ```
   GOOGLE_API_KEY=your-google-api-key-here
   ```
3. Replace `your-google-api-key-here` with your actual API key from Step 1
4. Save the file

**Example:**
```
GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXX
```

---

## Step 5: Run the Application

```powershell
# Still in PowerShell, in the project directory
.\run_windows_simple.ps1
```

**You'll see a menu:**
```
Select Mode:
1. Web Interface (Streamlit)
2. CLI Interface
3. Interactive Launcher

Select mode (1/2/3) [1]:
```

**Choose option 1** (Web Interface) for the best experience!

Press `Enter` or type `1` and press `Enter`.

**What happens:**
- Backend server starts on http://localhost:8000
- Celery worker starts (for background processing)
- Your browser opens to http://localhost:8501
- You'll see the YouTube Audit Engine interface!

---

## Step 6: Analyze Your Watch History

### In the Web Interface:

1. **Sidebar** - You'll see:
   - Google API Key field (should show "Using API Key from secrets" if .env is configured)
   - File uploader

2. **Upload your file:**
   - Click "Browse files"
   - Select your `watch-history.json` file
   - Or upload the entire `.zip` file from Takeout

3. **Configure (optional):**
   - Expand "Advanced Options"
   - Adjust "Number of clusters" (5-20, default is 10)

4. **Click "Analyze Watch History"**

5. **Watch the magic happen:**
   ```
   ✅ Job submitted successfully!
   Task ID: abc-123

   ⏳ Processing Analysis
   [████████████░░░░░░░░] 50%
   Status: Generating semantic embeddings...

   Total Videos: 1,000  |  Processed: 850
   Channels: 120        |  Clusters: 10
   ```

6. **Results appear automatically!**
   - Summary statistics
   - Top channels bar chart
   - Content clusters pie chart
   - Detailed breakdowns

---

## What to Expect

### Timeline:
- **Small files (100-500 videos):** 2-5 minutes
- **Medium files (500-2000 videos):** 5-15 minutes
- **Large files (2000+ videos):** 15-30 minutes

### Progress stages:
1. Parsing watch history file... (5%)
2. Extracting video IDs... (10%)
3. Enriching with YouTube API... (20%)
4. Generating semantic embeddings... (50%)
5. Clustering videos... (70%)
6. Scoring clusters... (85%)
7. Saving results... (90%)
8. Analysis complete! (100%) 🎈

### You'll see:
- **Real-time progress bar** updating every 2 seconds
- **Live statistics** as videos are processed
- **Status messages** showing current stage
- **Cancel button** if you want to stop

---

## Troubleshooting

### Problem: "Python not found"
```powershell
# Check if Python is installed
python --version

# If not found, download from:
# https://www.python.org/downloads/
# Make sure to check "Add Python to PATH" during installation
```

### Problem: "Execution policy error"
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: "Backend not starting"
Check the console output for errors. Common issues:
- Port 8000 already in use
- Missing dependencies
- Incorrect .env configuration

**Solution:** Try running individual components:
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Set PYTHONPATH
$env:PYTHONPATH = $PWD

# Test backend
python backend/main.py

# In another PowerShell window, test Celery:
celery -A backend.celery_app worker --pool=solo --loglevel=info
```

### Problem: "API key not working"
- Make sure you enabled YouTube Data API v3 in Google Cloud Console
- Check for typos in .env file
- Make sure there are no quotes around the key
- Verify the key hasn't been restricted

### Problem: "fakeredis import error"
```powershell
.\venv\Scripts\Activate.ps1
pip install fakeredis[lua]
```

### Problem: "Celery worker fails on Windows"
This is expected - we use `--pool=solo` for Windows compatibility.
The run script handles this automatically.

### Problem: "Browser doesn't open"
Manually navigate to: http://localhost:8501

### Problem: "Analysis stuck at 0%"
- Check that Celery worker is running
- Look for errors in the PowerShell window
- Try a smaller test file first

---

## Testing Tips

### Start Small
Test with a small watch-history.json file first:
- 50-100 videos is perfect for initial testing
- Completes in 1-2 minutes
- Helps verify everything works

### Monitor Progress
Watch the PowerShell window for:
- Backend logs
- Celery worker activity
- Any error messages

### Use Sample Data
If you don't have a watch history yet:
```json
[
  {
    "titleUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "time": "2024-01-15T10:30:00Z"
  },
  {
    "titleUrl": "https://www.youtube.com/watch?v=9bZkp7q19f0",
    "time": "2024-01-16T14:20:00Z"
  }
]
```
Save as `test-history.json` and upload it.

---

## Stopping the Application

Press `Ctrl+C` in the PowerShell window where you ran `run_windows_simple.ps1`

This will:
1. Stop the web interface
2. Stop the Celery worker
3. Stop the backend server

---

## Next Steps After Testing

### If Everything Works:
1. Try analyzing your full watch history
2. Explore the CLI interface (option 2 in the menu)
3. Download results as JSON
4. Experiment with different cluster counts

### If You Want to Deploy for Real Use:
1. Install PostgreSQL for persistent storage
2. Install Redis for better performance
3. See `WINDOWS_SETUP.md` for production setup options

### If You Found Bugs:
1. Check the PowerShell output for error messages
2. Look at the `.env` file to verify configuration
3. Try with a smaller test file
4. Report issues with error logs

---

## Features You're Testing

✅ **Async Processing** - No timeouts, handles large files
✅ **Real-time Progress** - Live updates every 2 seconds
✅ **Real YouTube Data** - Actual video metadata from API
✅ **Real Embeddings** - Semantic analysis with ML
✅ **Clustering** - Automatic topic discovery
✅ **Visualizations** - Charts and graphs
✅ **Dual Interface** - Web and CLI modes
✅ **Windows Compatible** - No Docker needed!

---

## Questions?

**Q: Do I need Docker?**
A: No! This setup uses SQLite + fakeredis, no Docker required.

**Q: Will my data be uploaded anywhere?**
A: No, everything runs locally on your computer. Only YouTube API calls go to Google (to get video metadata).

**Q: How much does the YouTube API cost?**
A: It's free! You get 10,000 quota units per day. One video = ~1 unit. So you can analyze ~10,000 videos per day for free.

**Q: Can I use this offline?**
A: You need internet for the YouTube API calls to get video metadata. But the processing happens locally.

**Q: Is my watch history private?**
A: Yes! Your data never leaves your computer except for the YouTube API requests (which only request public video metadata).

---

## Success! 🎉

If you see results with clusters, charts, and statistics - **you're successfully testing the MVP!**

Enjoy exploring your YouTube viewing patterns! 📊🎬

