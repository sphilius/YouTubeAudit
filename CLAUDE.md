# CLAUDE.md - AI Assistant Guide for YouTube Audit Engine

**Purpose:** Guide for AI assistants (Claude, GPT, etc.) working on this codebase
**Last Updated:** 2025-11-17
**Project:** YouTube Topic Audit Engine

---

## Quick Start for AI Assistants

### 1. What is This Project?
A YouTube watch history analyzer that:
- Parses YouTube Takeout files
- Enriches video metadata via YouTube API
- Generates semantic embeddings using transformers
- Clusters videos by topic
- Scores clusters by opportunity/demand

### 2. Current State (Read This First!)
- ✅ **Working:** YouTube API, embeddings, clustering, configuration, error handling
- ⚠️ **Partial:** Database models exist but not integrated with pipeline
- ❌ **Missing:** Async job processing (Celery), real scoring algorithm, persistence layer

**Critical:** The `/analyze` endpoint is **synchronous** and blocks for 15+ minutes!

### 3. Essential Reading
Before making changes, read:
1. `UPDATES.md` - Current project status
2. `ARCHITECTURE.md` - System design
3. `backend/config.py` - All configuration settings
4. `backend/exceptions.py` - Error handling hierarchy

---

## Codebase Structure

### High-Level Architecture
```
┌─────────────────────────────────────────────────────┐
│ Frontend (Streamlit) - frontend/app.py             │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP POST /analyze
                   ▼
┌─────────────────────────────────────────────────────┐
│ Backend (Flask) - backend/main.py                  │
│ ├── Middleware (correlation, error_handler)        │
│ ├── Validators (file, API key, bearer token)       │
│ └── Pipeline Orchestration (5 steps)               │
└──────────────────┬──────────────────────────────────┘
                   │
      ┌────────────┴────────────┐
      ▼                         ▼
┌─────────────┐         ┌──────────────┐
│ PostgreSQL  │         │ Redis Cache  │
│ (Models)    │         │ + Quota Mgr  │
└─────────────┘         └──────────────┘
                               │
                               ▼
                     ┌──────────────────┐
                     │ YouTube Data API │
                     └──────────────────┘
```

### Directory Map (Top-Level)
```
YouTubeAudit/
├── backend/              # Flask API (PRIMARY WORK AREA)
│   ├── modules/         # Analysis pipeline stages
│   ├── services/        # External service clients
│   ├── models/          # SQLAlchemy ORM models
│   ├── middleware/      # Request/response processing
│   ├── utils/           # Helpers (logging, retry)
│   ├── main.py          # Flask app + endpoints
│   ├── config.py        # Pydantic configuration
│   ├── database.py      # Database connection
│   ├── cache.py         # Redis connection
│   ├── exceptions.py    # Custom exceptions
│   └── validators.py    # Input validation
├── frontend/            # Streamlit UI
│   └── app.py
├── cli/                 # Terminal interface
│   └── interface.py
├── alembic/             # Database migrations
│   ├── versions/        # Migration scripts
│   └── env.py
├── docker-compose.yml   # Service orchestration
├── requirements.txt     # Python dependencies
└── [docs]/              # 7 markdown guides
```

### Backend Module Breakdown
```
backend/modules/
├── ingestion.py       # Parse Takeout files → video IDs
├── enrichment.py      # Fetch metadata from YouTube API
├── embedding.py       # Generate semantic vectors
├── clustering.py      # K-Means topic grouping
├── labeling.py        # Generate cluster labels
└── scoring.py         # ⚠️ PLACEHOLDER - needs real metrics

backend/services/
├── youtube_api.py     # YouTube Data API v3 client
├── metadata_cache.py  # Redis caching (7-day TTL)
└── quota_manager.py   # Daily quota tracking

backend/models/
├── analysis.py        # Analysis job metadata
├── video.py           # Video records
└── cluster.py         # Cluster definitions

backend/middleware/
├── correlation.py     # Request ID tracking
└── error_handler.py   # Global error handling
```

---

## Key Files & What They Do

### Critical Files (Must Understand)

#### `backend/config.py` (578 lines)
**Purpose:** Centralized configuration with Pydantic validation
**Contains:** 60+ settings for database, Redis, YouTube API, embeddings, clustering
**Pattern:** Singleton via `get_config()`
**Usage:**
```python
from backend.config import get_config
config = get_config()
print(config.max_clusters)  # 15
```

#### `backend/main.py` (345 lines)
**Purpose:** Flask application entry point
**Endpoints:**
- `GET /` - Health check
- `GET /health` - Detailed health
- `POST /analyze` - Main analysis (⚠️ SYNCHRONOUS)

**Pipeline Flow:**
1. Validate bearer token
2. Validate file upload
3. Run analysis pipeline (BLOCKS!)
4. Return JSON results

#### `backend/exceptions.py`
**Purpose:** Hierarchical exception system
**Base:** `YouTubeAuditError`
**Children:** 15+ specific exceptions (ValidationError, EnrichmentError, etc.)
**Pattern:** All exceptions have `error_code`, `message`, `user_message`

#### `backend/database.py` (159 lines)
**Purpose:** SQLAlchemy connection management
**Exports:**
- `Base` - Declarative base for models
- `get_engine()` - Database engine
- `get_db()` - Session generator

**⚠️ Note:** Database is configured but NOT integrated with main pipeline yet!

### Service Files (External Integrations)

#### `backend/services/youtube_api.py` (394 lines)
**Purpose:** Production YouTube API client
**Features:**
- Batch requests (50 videos/call)
- Quota tracking
- Cache integration
- Retry with exponential backoff

**Key Methods:**
- `get_video_metadata(video_ids, use_cache=True)` → List[Dict]
- `get_quota_stats()` → Dict
- `get_cache_stats()` → Dict

**Usage:**
```python
from backend.services.youtube_api import YouTubeAPIClient

client = YouTubeAPIClient(api_key="...")
metadata = client.get_video_metadata(["dQw4w9WgXcQ"])
```

#### `backend/services/metadata_cache.py`
**Purpose:** Redis-backed metadata cache
**TTL:** 7 days
**Pattern:** Video ID → metadata Dict

#### `backend/services/quota_manager.py`
**Purpose:** Track YouTube API quota usage
**Limit:** 10,000 units/day (default)
**Auto-reset:** Midnight UTC

### Pipeline Modules

#### `backend/modules/ingestion.py`
**Input:** ZIP or JSON file
**Output:** List of video IDs
**Status:** ✅ Working

#### `backend/modules/enrichment.py` (154 lines)
**Input:** List of video IDs
**Output:** List of metadata Dicts
**Status:** ✅ Working (uses production YouTube API)
**Features:**
- Check cache first
- Quota prediction
- Graceful degradation

#### `backend/modules/embedding.py` (301 lines)
**Input:** List of metadata Dicts
**Output:** numpy array (N x 384)
**Model:** `all-MiniLM-L6-v2` (sentence-transformers)
**Status:** ✅ Working (real embeddings)
**Pattern:** Singleton model loading

#### `backend/modules/clustering.py`
**Input:** numpy array of embeddings
**Output:** Dict of {cluster_id: [video_indices]}
**Algorithm:** K-Means
**Status:** ✅ Working

#### `backend/modules/scoring.py`
**Input:** Clusters + metadata
**Output:** Clusters with scores
**Status:** ⚠️ **PLACEHOLDER** - Returns random scores!
**TODO:** Implement real demand/competition calculation

---

## Development Workflows

### Common Tasks

#### Task 1: Add a New Configuration Setting
**File:** `backend/config.py`

1. Add field to `AppConfig` class:
```python
new_setting: int = Field(
    default=10,
    description="Description here",
    ge=1,  # Validation
    le=100
)
```

2. Access in code:
```python
config = get_config()
print(config.new_setting)
```

3. Override via environment variable:
```bash
export NEW_SETTING=20
```

#### Task 2: Add a New API Endpoint
**File:** `backend/main.py`

1. Define route:
```python
@app.route("/new_endpoint", methods=["GET"])
def new_endpoint():
    """Docstring explaining purpose."""
    log.info("New endpoint called")

    try:
        # Your logic here
        result = {"status": "ok"}
        return jsonify(result)
    except YouTubeAuditError as e:
        # Error handler middleware will catch this
        raise
```

2. Add to ARCHITECTURE.md documentation

#### Task 3: Add a New Custom Exception
**File:** `backend/exceptions.py`

1. Choose parent class in hierarchy
2. Define exception:
```python
class NewError(YouTubeAuditError):
    """Description."""
    def __init__(self, details: str, **kwargs):
        super().__init__(
            message=f"New error: {details}",
            error_code="NEW_001",
            user_message="User-friendly message",
            **kwargs
        )
```

#### Task 4: Add Database Persistence
**File:** `backend/tasks/analysis.py` (when created)

1. Import models:
```python
from backend.models.analysis import Analysis, AnalysisStatus
from backend.models.video import Video
from backend.database import get_db
```

2. In task, save results:
```python
db = next(get_db())
try:
    analysis = Analysis(
        task_id=task_id,
        status=AnalysisStatus.COMPLETED,
        total_videos=len(video_ids),
        # ... more fields
    )
    db.add(analysis)
    db.commit()
finally:
    db.close()
```

#### Task 5: Run Database Migration
```bash
# Create migration after model changes
docker-compose run backend alembic revision --autogenerate -m "Description"

# Apply migration
docker-compose run backend alembic upgrade head

# Rollback
docker-compose run backend alembic downgrade -1
```

#### Task 6: Test YouTube API Integration
```bash
# Set environment variables
export GOOGLE_API_KEY="your-key"
export API_BEARER_TOKEN="test-token"

# Run backend
cd backend
python main.py

# In another terminal, test endpoint
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer test-token" \
  -F "file=@watch-history.json" \
  -F "api_key=$GOOGLE_API_KEY"
```

---

## Key Conventions & Patterns

### Code Style

#### 1. Imports (Order Matters)
```python
# Standard library
import os
from typing import List, Dict

# Third-party
import numpy as np
from flask import Flask

# Local
from backend.config import get_config
from backend.exceptions import YouTubeAuditError
```

#### 2. Logging
**Always use structured logging:**
```python
from backend.utils.logging_config import get_logger

log = get_logger(__name__)

# Good
log.info("Processing videos", video_count=len(videos), user_id=user_id)

# Bad
log.info(f"Processing {len(videos)} videos for user {user_id}")
```

#### 3. Error Handling
**Always use custom exceptions:**
```python
# Good
if not video_ids:
    raise ValidationError(
        message="No videos found",
        user_message="Your watch history is empty."
    )

# Bad
if not video_ids:
    raise ValueError("No videos")
```

#### 4. Configuration Access
**Always use `get_config()`:**
```python
# Good
config = get_config()
max_size = config.max_upload_size_bytes

# Bad
MAX_SIZE = 100 * 1024 * 1024  # Hardcoded
```

#### 5. Database Sessions
**Always use context managers:**
```python
# Good
db = next(get_db())
try:
    result = db.query(Analysis).all()
    db.commit()
finally:
    db.close()

# Better (when available)
with get_db() as db:
    result = db.query(Analysis).all()
```

### Naming Conventions

- **Variables:** `snake_case`
- **Functions:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private:** `_leading_underscore`
- **Modules:** `lowercase` (no underscores if possible)

### File Naming

- **Models:** `singular.py` (e.g., `analysis.py`, not `analyses.py`)
- **Services:** `descriptive_name.py` (e.g., `youtube_api.py`)
- **Utils:** `purpose.py` (e.g., `logging_config.py`)

---

## Testing Guidelines (When Implementing)

### Test Structure
```
tests/
├── __init__.py
├── conftest.py          # Pytest fixtures
├── test_models.py       # Database model tests
├── test_services.py     # Service integration tests
├── test_pipeline.py     # Pipeline module tests
└── test_api.py          # API endpoint tests
```

### Common Fixtures Needed
```python
# conftest.py
import pytest
from backend.config import get_config, reload_config

@pytest.fixture
def config():
    """Provide test configuration."""
    return get_config()

@pytest.fixture
def mock_youtube_api(mocker):
    """Mock YouTube API responses."""
    return mocker.patch('backend.services.youtube_api.build')

@pytest.fixture
def sample_metadata():
    """Sample video metadata for testing."""
    return [{
        'id': 'test123',
        'snippet': {
            'title': 'Test Video',
            'channelTitle': 'Test Channel'
        },
        'statistics': {
            'viewCount': '1000'
        }
    }]
```

### Running Tests (Future)
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_services.py

# Run with coverage
pytest --cov=backend --cov-report=html

# Run with verbose output
pytest -v -s
```

---

## Git Workflow

### Branch Naming
- Feature: `claude/feature-name-<session-id>`
- Bugfix: `claude/fix-issue-<session-id>`
- Current: `claude/document-repo-status-01Uuya5yBvtsM2LhWahPcvtK`

### Commit Messages
**Format:** `<type>: <description>`

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code restructuring
- `docs:` Documentation
- `test:` Tests
- `chore:` Maintenance

**Examples:**
```bash
feat: Add async job processing with Celery
fix: Correct quota calculation in YouTube API client
refactor: Extract scoring logic into separate module
docs: Update ARCHITECTURE.md with async flow
test: Add unit tests for clustering module
```

### Committing Changes
```bash
# Stage changes
git add file1.py file2.py

# Commit with message
git commit -m "feat: Add real scoring algorithm"

# Push to remote
git push -u origin claude/feature-name-<session-id>
```

### Pull Request Workflow
1. Ensure all changes committed
2. Push to remote branch
3. Create PR targeting `main` branch
4. Include description of changes
5. Reference related issues

---

## Environment Variables

### Required
```env
GOOGLE_API_KEY=AIza...              # YouTube Data API v3 key
API_BEARER_TOKEN=secure-token       # Flask authentication
```

### Optional (with defaults)
```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/youtube_audit

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Embedding
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# Clustering
MIN_CLUSTERS=3
MAX_CLUSTERS=15
```

### Loading Environment Variables
```python
# .env file is automatically loaded by pydantic-settings
config = get_config()

# Manual override for testing
import os
os.environ['MAX_CLUSTERS'] = '20'
config = reload_config()
```

---

## Docker & Local Development

### Starting Services
```bash
# Full stack with Docker Compose
docker-compose up --build

# Individual services
docker-compose up backend
docker-compose up frontend
docker-compose up postgres
docker-compose up redis
```

### Service Ports
- **Frontend (Streamlit):** 8501
- **Backend (Flask):** 8000
- **PostgreSQL:** 5432
- **Redis:** 6379
- **Flower (Celery Monitor):** 5555

### Local Development (No Docker)
```bash
# Terminal 1: Backend
cd backend
export GOOGLE_API_KEY="..."
export API_BEARER_TOKEN="..."
python main.py

# Terminal 2: Frontend
cd frontend
export API_URL="http://localhost:8000"
streamlit run app.py
```

### Database Access
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U youtube_audit

# Run migrations
docker-compose run backend alembic upgrade head

# Reset database (DANGER!)
docker-compose run backend alembic downgrade base
docker-compose run backend alembic upgrade head
```

### Redis CLI
```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check keys
KEYS video_metadata:*
KEYS youtube_quota:*

# Clear cache
FLUSHDB
```

---

## Important DO's and DON'Ts

### DO ✅

1. **DO use structured logging**
   ```python
   log.info("Processing batch", batch_num=1, total=10)
   ```

2. **DO use type hints**
   ```python
   def process_videos(video_ids: List[str]) -> Dict[str, Any]:
   ```

3. **DO use custom exceptions**
   ```python
   raise EnrichmentError("YouTube API failed", error_code="ENRICH_001")
   ```

4. **DO validate inputs early**
   ```python
   if not video_ids:
       raise ValidationError("No video IDs provided")
   ```

5. **DO use configuration system**
   ```python
   config = get_config()
   max_retries = config.youtube_api_max_retries
   ```

6. **DO add docstrings**
   ```python
   def my_function(arg: str) -> int:
       """
       Brief description.

       Args:
           arg: Description

       Returns:
           Description
       """
   ```

7. **DO handle errors gracefully**
   ```python
   try:
       result = risky_operation()
   except SpecificError as e:
       log.error("Operation failed", error=str(e))
       raise
   ```

### DON'T ❌

1. **DON'T hardcode configuration**
   ```python
   # Bad
   MAX_SIZE = 100 * 1024 * 1024

   # Good
   config.max_upload_size_bytes
   ```

2. **DON'T use generic exceptions**
   ```python
   # Bad
   raise Exception("Something went wrong")

   # Good
   raise YouTubeAuditError("Specific error", error_code="ERR_001")
   ```

3. **DON'T log sensitive data**
   ```python
   # Bad
   log.info(f"API key: {api_key}")

   # Good (sanitization is automatic in logging_config)
   log.info("API key validated")
   ```

4. **DON'T modify main.py pipeline without understanding flow**
   - Read ARCHITECTURE.md first
   - Understand all 5 pipeline stages
   - Test changes thoroughly

5. **DON'T commit API keys or secrets**
   - Use `.env` file (gitignored)
   - Use environment variables
   - Never commit `.env` to git

6. **DON'T create database migrations manually**
   ```bash
   # Bad: Editing migration files directly

   # Good: Using alembic
   alembic revision --autogenerate -m "Add new field"
   ```

7. **DON'T bypass validation layer**
   ```python
   # Bad
   file_path = request.files['file'].filename

   # Good
   file = request.files['file']
   validate_file_upload(file)
   ```

---

## Common Pitfalls & Solutions

### Pitfall 1: "Module not found" errors
**Cause:** Python path not set correctly
**Solution:**
```bash
# Always run from project root
cd YouTubeAudit
python -m backend.main

# Or set PYTHONPATH
export PYTHONPATH=$PWD:$PYTHONPATH
```

### Pitfall 2: Database connection fails
**Cause:** PostgreSQL not running or wrong credentials
**Solution:**
```bash
# Check service status
docker-compose ps

# Restart database
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Pitfall 3: YouTube API quota exceeded
**Cause:** Too many API calls
**Solution:**
```python
# Check quota before calling
quota_stats = client.get_quota_stats()
if quota_stats['remaining'] < 100:
    log.warning("Low quota", remaining=quota_stats['remaining'])
```

### Pitfall 4: Embedding model download slow
**Cause:** First-time model download
**Solution:**
```python
# Pre-download in Docker build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Pitfall 5: Pipeline blocking frontend
**Cause:** Synchronous processing
**Solution:** Implement Celery (see IMPLEMENTATION_TASKS.md Phase 6-7)

### Pitfall 6: Cache growing too large
**Cause:** No expiration on cache entries
**Solution:** TTL is already set to 7 days in MetadataCache

### Pitfall 7: Tests failing on local machine
**Cause:** Environment differences
**Solution:**
```bash
# Use Docker for consistent environment
docker-compose run backend pytest
```

---

## Quick Reference Commands

### Development
```bash
# Start full stack
docker-compose up --build

# Restart specific service
docker-compose restart backend

# View logs
docker-compose logs -f backend

# Shell into container
docker-compose exec backend bash

# Run Python REPL with app context
docker-compose exec backend python
>>> from backend.config import get_config
>>> config = get_config()
```

### Database
```bash
# Create migration
docker-compose run backend alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose run backend alembic upgrade head

# View current version
docker-compose run backend alembic current

# View migration history
docker-compose run backend alembic history
```

### Testing (Future)
```bash
# Run all tests
docker-compose run backend pytest

# Run specific test
docker-compose run backend pytest tests/test_services.py::test_youtube_api

# Coverage report
docker-compose run backend pytest --cov=backend --cov-report=term
```

### Debugging
```bash
# Check configuration
docker-compose run backend python -c "from backend.config import print_config; print_config()"

# Test YouTube API
docker-compose run backend python -c "
from backend.services.youtube_api import YouTubeAPIClient
import os
client = YouTubeAPIClient(os.environ['GOOGLE_API_KEY'])
print(client.get_quota_stats())
"

# Check database connection
docker-compose run backend python -c "
from backend.database import health_check
print('DB healthy:', health_check())
"
```

---

## Priority Areas for Development

### Phase 6: Celery Setup (Next Priority)
**Files to create:**
- `backend/celery_app.py` - Celery application instance
- `backend/tasks/__init__.py` - Task module
- `backend/tasks/analysis.py` - Async analysis task

**Changes needed:**
- Update `backend/main.py` - Add job endpoints
- Update `docker-compose.yml` - Add Celery worker service

### Phase 7: Async Integration
**Files to modify:**
- `backend/main.py` - Change `/analyze` to queue task
- `frontend/app.py` - Add polling logic

**New endpoints:**
- `GET /jobs/{id}` - Job status
- `GET /jobs/{id}/results` - Fetch results
- `DELETE /jobs/{id}` - Cancel job

### Phase 5.3: Real Scoring (Critical)
**File to fix:**
- `backend/modules/scoring.py` - Replace placeholder logic

**Required:**
- Calculate demand from view counts
- Calculate competition from channel metrics
- Compute opportunity score (demand / competition)
- Rank clusters

---

## Debugging Tips

### Enable Verbose Logging
```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in config
LOG_LEVEL=DEBUG docker-compose up backend
```

### Check Request Flow
1. **Frontend sends request** → Check browser DevTools Network tab
2. **Backend receives request** → Check `backend/main.py` logs
3. **Pipeline executes** → Check module-specific logs
4. **Response sent** → Check frontend console

### Use Correlation IDs
Every request has a correlation ID for tracing:
```python
# In logs
"correlation_id": "abc-123-def-456"

# Filter logs by correlation ID
docker-compose logs backend | grep "abc-123"
```

### Profile Performance
```python
import time
start = time.time()
result = slow_function()
elapsed = time.time() - start
log.info("Performance", function="slow_function", elapsed_ms=elapsed*1000)
```

---

## Resources & Links

### Internal Documentation
- `README.md` - Setup and usage
- `ARCHITECTURE.md` - System design (803 lines)
- `UPDATES.md` - Current status report
- `IMPLEMENTATION_TASKS.md` - Development roadmap
- `CLI_GUIDE.md` - CLI usage
- `WINDOWS_SETUP.md` - Windows-specific setup
- `FEATURE_RECOMMENDATIONS.md` - Future features

### External Documentation
- [YouTube Data API v3](https://developers.google.com/youtube/v3)
- [Sentence Transformers](https://www.sbert.net/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)

### Code Quality Tools
```bash
# Linting (if configured)
flake8 backend/
pylint backend/

# Type checking (if configured)
mypy backend/

# Formatting (if configured)
black backend/
isort backend/
```

---

## Final Notes for AI Assistants

### When Asked to Implement a Feature

1. **Read relevant documentation first**
   - UPDATES.md for current state
   - ARCHITECTURE.md for design
   - IMPLEMENTATION_TASKS.md for task breakdown

2. **Check existing patterns**
   - Look at similar modules
   - Follow naming conventions
   - Use existing utilities

3. **Test your changes**
   - Manual testing with curl
   - Check logs for errors
   - Verify database changes

4. **Update documentation**
   - Add docstrings
   - Update ARCHITECTURE.md if needed
   - Add to UPDATES.md

### When Debugging Issues

1. **Check logs first**
   ```bash
   docker-compose logs -f backend
   ```

2. **Verify configuration**
   ```python
   from backend.config import get_config, validate_config
   config = get_config()
   is_valid, errors = validate_config()
   ```

3. **Test components in isolation**
   ```python
   # Test YouTube API
   from backend.services.youtube_api import YouTubeAPIClient
   client = YouTubeAPIClient(api_key="...")
   result = client.get_quota_stats()
   ```

4. **Use correlation IDs**
   - Find request's correlation ID
   - Trace through all logs

### When Refactoring

1. **Don't break the working parts**
   - YouTube API integration is solid
   - Embedding generation is working
   - Configuration system is robust

2. **Focus on missing pieces**
   - Async processing (Priority 1)
   - Real scoring (Priority 1)
   - Database integration (Priority 2)

3. **Maintain conventions**
   - Follow existing patterns
   - Keep error handling consistent
   - Use structured logging

---

**End of AI Assistant Guide**

For questions or clarification, refer to:
- Project owner via GitHub issues
- ARCHITECTURE.md for system design
- UPDATES.md for current status
