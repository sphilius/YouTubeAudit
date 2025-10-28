# YouTube Watch History Analyzer - Simple Version

**One file. One command. Instant insights.**

This is a streamlined version of the YouTube Audit Engine that focuses on core functionality without complex infrastructure.

## ✨ Features

- 📤 Upload your YouTube watch history JSON
- 🤖 AI-powered topic clustering (or basic clustering if AI unavailable)
- 📊 Interactive visualizations
- 💡 Content creation insights and recommendations
- 📺 Channel and viewing pattern analysis
- 💾 Export results as JSON

## 🚀 Quick Start

### 1. Get Your Watch History

1. Go to [Google Takeout](https://takeout.google.com/)
2. Deselect all, select only **YouTube**
3. Click "All YouTube data included" → Select only **history**
4. Download and extract
5. Find `watch-history.json`

### 2. Get YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable "YouTube Data API v3"
4. Create credentials → API Key
5. Copy the key

### 3. Run the Analyzer

**Windows:**
```powershell
.\run-simple.ps1
```

**Mac/Linux:**
```bash
chmod +x run-simple.sh
./run-simple.sh
```

**Or manually:**
```bash
pip install -r requirements-simple.txt
streamlit run simple_analyzer.py
```

The app will open in your browser at `http://localhost:8501`

## 📋 Requirements

- Python 3.10+
- ~2GB disk space (with AI models)
- ~500MB disk space (without AI models, basic clustering)

## 🎯 What You Get

### 1. Content Theme Analysis
- Automatically groups videos into topics
- Identifies your primary content interests
- Shows viewing patterns

### 2. Channel Insights
- Top channels you watch
- Content creator overlap with your interests
- Potential collaboration opportunities

### 3. Content Creation Recommendations
- Your strongest knowledge areas
- Diversification opportunities
- Audience overlap insights

## ⚙️ Configuration

In the app sidebar:
- **YouTube API Key**: Your Google API key
- **Number of clusters**: How many themes to identify (3-15)
- **Use AI analysis**: Toggle semantic vs. basic clustering

## 🔧 Troubleshooting

### "API quota exceeded"
- YouTube API has daily limits (10,000 units/day)
- Each video costs ~1-2 units
- Try analyzing fewer videos or wait 24 hours

### "sentence-transformers not installed"
- The app falls back to basic clustering
- Still works, just less accurate
- To enable AI: `pip install sentence-transformers torch`

### App won't start
```powershell
# Delete and recreate virtual environment
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-simple.txt
```

## 📦 What's Different From Full Version?

**Removed (for simplicity):**
- ❌ Flask backend API
- ❌ Celery task queue
- ❌ Redis message broker
- ❌ PostgreSQL database
- ❌ Complex async processing
- ❌ Multi-service architecture

**Kept (core functionality):**
- ✅ YouTube API integration
- ✅ AI-powered clustering
- ✅ Interactive visualizations
- ✅ Insights and recommendations
- ✅ Data export

**Result:**
- 🚀 10x faster to set up
- 💾 70% less disk space
- 🐛 Easier to debug
- 📝 Simpler code (1 file vs. 50+ files)

## 🤝 Contributing

This is a simplified educational version. For the full production-ready version with async processing, database persistence, and advanced features, see the main project.

## 📄 License

MIT License - see LICENSE file for details
