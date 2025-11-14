# CLAUDE.md - AI Assistant Guide for YouTubeAudit

**Last Updated:** 2025-01-21
**Version:** 2.0
**Purpose:** Comprehensive guide for AI assistants working on the YouTube Audit Engine codebase

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Codebase Structure](#codebase-structure)
3. [Architecture Overview](#architecture-overview)
4. [Development Environment Setup](#development-environment-setup)
5. [Key Technologies & Patterns](#key-technologies--patterns)
6. [Core Workflows](#core-workflows)
7. [Database Schema & Models](#database-schema--models)
8. [API Endpoints](#api-endpoints)
9. [Configuration Management](#configuration-management)
10. [Error Handling](#error-handling)
11. [Testing Strategy](#testing-strategy)
12. [Common Development Tasks](#common-development-tasks)
13. [Git Workflow](#git-workflow)
14. [Code Style & Conventions](#code-style--conventions)
15. [Important Implementation Notes](#important-implementation-notes)
16. [Debugging & Troubleshooting](#debugging--troubleshooting)

---

## Project Overview

### What is YouTube Audit Engine?

YouTube Audit Engine is a sophisticated data analysis tool that:
- Ingests YouTube Takeout watch history data (`watch-history.json`)
- Enriches video metadata using YouTube Data API v3
- Generates semantic embeddings using sentence-transformers
- Clusters videos into thematic topics using K-Means
- Scores clusters for content opportunity analysis
- Provides interactive CLI and Web interfaces for exploration

### Primary Use Case

Help content creators discover their strongest thematic niches by analyzing viewing patterns and identifying high-opportunity content clusters.

### Project Status

**Current State (v2.0):**
- ✅ Production-ready YouTube API integration
- ✅ Real embeddings with sentence-transformers (all-MiniLM-L6-v2)
- ✅ PostgreSQL database with Alembic migrations
- ✅ Redis caching and quota management
- ✅ Comprehensive error handling with custom exceptions
- ✅ Structured logging with correlation IDs
- ✅ CLI interface with Rich output
- ✅ Docker Compose orchestration
- ⚠️ Synchronous API (async Celery implementation in progress)
- ❌ No test coverage yet

---

## Codebase Structure

```
YouTubeAudit/
├── backend/                        # Flask API server (primary logic)
│   ├── main.py                    # Flask app entry point, routes
│   ├── config.py                  # Pydantic configuration (CRITICAL)
│   ├── database.py                # SQLAlchemy engine & session
│   ├── cache.py                   # Redis client singleton
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── validators.py              # Input validation layer
│   │
│   ├── middleware/                # Flask middleware
│   │   ├── correlation.py        # Request ID tracking
│   │   └── error_handler.py      # Global error handler
│   │
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── analysis.py           # Analysis job tracking
│   │   ├── video.py              # Video metadata & embeddings
│   │   └── cluster.py            # Cluster results
│   │
│   ├── modules/                   # Core analysis pipeline
│   │   ├── ingestion.py          # Parse Takeout ZIP/JSON
│   │   ├── enrichment.py         # YouTube API metadata fetching
│   │   ├── embedding.py          # Generate embeddings
│   │   ├── clustering.py         # K-Means clustering
│   │   ├── labeling.py           # Cluster naming
│   │   └── scoring.py            # Opportunity scoring
│   │
│   ├── services/                  # External integrations
│   │   ├── youtube_api.py        # YouTube API client
│   │   ├── quota_manager.py      # Quota tracking
│   │   └── metadata_cache.py     # Redis metadata cache
│   │
│   ├── utils/                     # Utility functions
│   │   ├── logging_config.py     # Structured logging setup
│   │   └── retry.py              # Exponential backoff decorators
│   │
│   └── Dockerfile                 # Backend container definition
│
├── frontend/                       # Streamlit web UI
│   ├── app.py                     # Main Streamlit application
│   └── Dockerfile
│
├── cli/                            # Command-line interface
│   └── interface.py               # Rich CLI with progress bars
│
├── alembic/                        # Database migrations
│   ├── versions/                  # Migration scripts
│   │   └── 20250121_0000_001_initial_schema.py
│   ├── env.py                     # Alembic environment
│   └── alembic.ini
│
├── docker-compose.yml              # Multi-container orchestration
├── requirements.txt                # Python dependencies
├── launcher.py                     # Interactive CLI/Web launcher
├── launcher.ps1                    # Windows PowerShell launcher
│
├── .env                            # Environment variables (CREATE MANUALLY)
│
└── Documentation/
    ├── README.md                   # User documentation
    ├── ARCHITECTURE.md             # Detailed architecture
    ├── CLI_GUIDE.md                # CLI usage guide
    ├── WINDOWS_SETUP.md            # Windows setup
    └── CLAUDE.md                   # This file (AI assistant guide)
```

### Key File Locations

| Purpose | File Path | Notes |
|---------|-----------|-------|
| Main API routes | `backend/main.py` | Flask app, `/analyze` endpoint |
| Configuration | `backend/config.py` | Pydantic settings, single source of truth |
| Database models | `backend/models/*.py` | SQLAlchemy ORM definitions |
| Analysis pipeline | `backend/modules/*.py` | 5-step processing pipeline |
| Error definitions | `backend/exceptions.py` | Hierarchical custom exceptions |
| Logging setup | `backend/utils/logging_config.py` | Structlog configuration |
| YouTube API client | `backend/services/youtube_api.py` | API v3 integration |
| CLI interface | `cli/interface.py` | Rich terminal UI |
| Frontend UI | `frontend/app.py` | Streamlit application |
| Database migrations | `alembic/versions/*.py` | Schema versioning |
| Docker orchestration | `docker-compose.yml` | 7 services defined |

---

## Architecture Overview

### System Architecture (Current - v2.0)

```
┌─────────────┐
│   USER      │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  INTERFACES                              │
│  ┌────────────┐      ┌────────────┐     │
│  │ CLI Mode   │      │ Web Mode   │     │
│  │ (Rich)     │      │ (Streamlit)│     │
│  └─────┬──────┘      └─────┬──────┘     │
└────────┼───────────────────┼─────────────┘
         │                   │
         │  POST /analyze    │
         ▼                   ▼
┌──────────────────────────────────────────┐
│  FLASK BACKEND (Port 8000)               │
│  ┌────────────────────────────────────┐  │
│  │ Middleware Stack:                  │  │
│  │ • Correlation ID                   │  │
│  │ • Error Handler                    │  │
│  │ • Bearer Token Auth                │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ Processing Pipeline (Synchronous): │  │
│  │ 1. Ingestion  ──────────────────┐  │  │
│  │ 2. Enrichment (YouTube API)     │  │  │
│  │ 3. Embedding (sentence-trans.)  │  │  │
│  │ 4. Clustering (K-Means)         │  │  │
│  │ 5. Scoring                      │  │  │
│  └────────────┬────────────────────┘  │  │
└───────────────┼───────────────────────┘
                │
       ┌────────┼────────┐
       │        │        │
       ▼        ▼        ▼
┌──────────┐ ┌─────┐ ┌────────────┐
│PostgreSQL│ │Redis│ │YouTube API │
│  :5432   │ │:6379│ │   (v3)     │
└──────────┘ └─────┘ └────────────┘
```

### Data Flow

```
1. File Upload (ZIP or JSON)
   └─> Backend validates file (size, type, bearer token)

2. Ingestion Module
   ├─> Parse ZIP/JSON
   ├─> Extract video IDs
   └─> Create Analysis record (DB)

3. Enrichment Module
   ├─> Check Redis cache for metadata
   ├─> Batch fetch missing videos (YouTube API, 50/request)
   ├─> Track quota usage (Redis)
   └─> Cache results (7-day TTL)

4. Embedding Module
   ├─> Load sentence-transformers model
   ├─> Generate 384-dim embeddings for titles
   └─> Store vectors in DB

5. Clustering Module
   ├─> Determine optimal K (3-15 clusters)
   ├─> Run K-Means algorithm
   └─> Assign videos to clusters

6. Scoring Module
   ├─> Calculate demand (video count, total views)
   ├─> Calculate competition (avg views)
   └─> Calculate opportunity score

7. Return Results
   └─> JSON response with clusters, videos, scores
```

### Service Dependencies

```
Docker Compose Stack:
├── postgres (Database)
│   └─> Volume: postgres_data
├── redis (Cache/Broker)
│   └─> Volume: redis_data
├── backend (Flask API)
│   └─> Depends: postgres, redis
├── celery_worker (Background jobs) [FUTURE]
│   └─> Depends: postgres, redis
├── celery_beat (Scheduler) [FUTURE]
│   └─> Depends: redis
├── flower (Celery monitoring) [FUTURE]
│   └─> Depends: redis
└── frontend (Streamlit)
    └─> Depends: backend
```

---

## Development Environment Setup

### Prerequisites

- Python 3.10+ (3.11 recommended)
- Docker & Docker Compose (for full stack)
- Google API Key (YouTube Data API v3 enabled)
- PostgreSQL 15 (if running without Docker)
- Redis 7 (if running without Docker)

### Quick Start (Docker)

1. **Clone repository:**
   ```bash
   git clone <repo-url>
   cd YouTubeAudit
   ```

2. **Create `.env` file:**
   ```env
   # Required
   API_BEARER_TOKEN="secure-token-min-16-chars"
   GOOGLE_API_KEY="your-google-api-key"

   # Optional (has defaults)
   ENVIRONMENT=development
   DATABASE_URL=postgresql://youtube_audit:youtube_audit_password@postgres:5432/youtube_audit
   REDIS_URL=redis://redis:6379/0
   ```

3. **Start services:**
   ```bash
   docker-compose up --build
   ```

4. **Access interfaces:**
   - Web UI: http://localhost:8501
   - Backend API: http://localhost:8000
   - Flower (Celery): http://localhost:5555
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

### Local Development (Without Docker)

**Terminal 1 - Backend:**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

export API_BEARER_TOKEN="dev-token"
export GOOGLE_API_KEY="your-key"

cd backend
flask run --host=0.0.0.0 --port=8000
```

**Terminal 2 - Frontend:**
```bash
source venv/bin/activate
cd frontend
streamlit run app.py
```

**Terminal 3 - CLI:**
```bash
source venv/bin/activate
python -m cli.interface --interactive
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# View migration history
alembic history
```

---

## Key Technologies & Patterns

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Backend** | Flask | 3.0+ | Lightweight REST API |
| **WSGI Server** | Gunicorn | 21.2+ | Production serving |
| **Task Queue** | Celery | 5.3+ | Async jobs (future) |
| **Message Broker** | Redis | 7 | Caching + queue |
| **Database** | PostgreSQL | 15 | Data persistence |
| **ORM** | SQLAlchemy | 2.0+ | Database abstraction |
| **Migrations** | Alembic | 1.12+ | Schema versioning |
| **Config** | Pydantic | 2.0+ | Type-safe settings |
| **Logging** | Structlog | 23.1+ | Structured logs |
| **ML/Embeddings** | sentence-transformers | 2.2+ | Semantic embeddings |
| **Clustering** | scikit-learn | 1.3+ | K-Means algorithm |
| **Vector Store** | FAISS | 1.7.4 | Similarity search |
| **Frontend** | Streamlit | 1.28+ | Web UI |
| **CLI** | Rich | 13.5+ | Terminal UI |
| **HTTP Client** | Requests | 2.31+ | API calls |
| **YouTube API** | google-api-python-client | 2.100+ | Video metadata |

### Design Patterns Used

1. **Singleton Pattern**
   - `backend/database.py`: SQLAlchemy engine
   - `backend/cache.py`: Redis client

2. **Factory Pattern**
   - `backend/config.py`: Configuration loading
   - `backend/utils/logging_config.py`: Logger creation

3. **Middleware Pattern**
   - `backend/middleware/correlation.py`: Request tracing
   - `backend/middleware/error_handler.py`: Error handling

4. **Repository Pattern**
   - `backend/models/*.py`: Data access layer

5. **Strategy Pattern**
   - `backend/modules/clustering.py`: Clustering algorithms
   - `backend/modules/scoring.py`: Scoring strategies

6. **Decorator Pattern**
   - `backend/utils/retry.py`: Retry decorators
   - Rate limiting decorators

### Configuration Hierarchy

```
Priority (Highest to Lowest):
1. Environment variables (os.environ)
2. .env file (python-dotenv)
3. Default values (config.py)
```

### Logging Strategy

**Structured Logging with Correlation IDs:**

```python
# Every request gets a unique correlation_id
logger.info(
    "Enrichment complete",
    correlation_id="abc-123-def-456",
    video_count=1000,
    quota_used=20,
    cache_hit_rate=0.82
)
```

**Output Format (JSON):**
```json
{
  "timestamp": "2025-01-21T10:30:45.123Z",
  "level": "INFO",
  "event": "Enrichment complete",
  "correlation_id": "abc-123-def-456",
  "video_count": 1000,
  "quota_used": 20,
  "cache_hit_rate": 0.82
}
```

---

## Core Workflows

### 1. Processing Pipeline

**Location:** `backend/modules/`

**Flow:** Ingestion → Enrichment → Embedding → Clustering → Scoring

**Entry Point:** `backend/main.py:analyze_endpoint()`

```python
# Simplified workflow
def analyze_watch_history(file_path, api_key):
    # 1. Ingestion
    video_ids = ingestion.parse_takeout(file_path)

    # 2. Enrichment
    metadata = enrichment.enrich_videos(video_ids, api_key)

    # 3. Embedding
    embeddings = embedding.generate_embeddings(metadata)

    # 4. Clustering
    clusters = clustering.cluster_videos(embeddings)

    # 5. Scoring
    scored_clusters = scoring.score_clusters(clusters)

    return scored_clusters
```

### 2. YouTube API Integration

**Location:** `backend/services/youtube_api.py`

**Key Features:**
- Batch requests (50 videos per call)
- Quota tracking (10,000 units/day default)
- Redis caching (7-day TTL)
- Exponential backoff retry
- Rate limiting

**Usage Pattern:**
```python
from backend.services.youtube_api import YouTubeAPIClient

client = YouTubeAPIClient(api_key="your-key")

# Batch fetch metadata
metadata = client.get_videos_metadata(
    video_ids=["dQw4w9WgXcQ", "jNQXAC9IVRw"],
    use_cache=True
)
```

### 3. Caching Strategy

**Location:** `backend/services/metadata_cache.py`

**Cache Types:**

1. **Metadata Cache** (Redis, TTL: 7 days)
   ```
   Key: video_metadata:{video_id}
   Value: {title, channel, stats, ...}
   ```

2. **Quota Tracking** (Redis, TTL: 24 hours)
   ```
   Key: youtube_quota:2025-01-21
   Value: 1247  # units used today
   ```

**Cache Checking Flow:**
```python
# 1. Check cache first
cached = metadata_cache.get_metadata(video_ids)

# 2. Identify cache misses
missing_ids = [vid for vid in video_ids if vid not in cached]

# 3. Fetch missing from API
if missing_ids:
    fresh_data = youtube_api.fetch(missing_ids)
    metadata_cache.set_metadata(fresh_data)

# 4. Return combined results
return {**cached, **fresh_data}
```

### 4. Error Handling Flow

**Location:** `backend/exceptions.py`, `backend/middleware/error_handler.py`

**Exception Hierarchy:**
```
YouTubeAuditError (base)
├── ConfigurationError
├── ValidationError
│   ├── FileValidationError
│   │   ├── FileSizeError
│   │   └── FileTypeError
│   └── APIKeyValidationError
├── IngestionError
├── EnrichmentError
│   ├── YouTubeAPIError
│   ├── QuotaExceededError
│   └── RateLimitError
├── EmbeddingError
└── ClusteringError
```

**Handling Pattern:**
```python
from backend.exceptions import QuotaExceededError

try:
    metadata = fetch_from_youtube(video_ids)
except QuotaExceededError as e:
    logger.error(
        "YouTube API quota exceeded",
        correlation_id=request.correlation_id,
        quota_used=e.quota_used
    )
    raise  # Middleware converts to HTTP 503
```

---

## Database Schema & Models

### Models Overview

**Location:** `backend/models/`

```
analyses (1) ----< (M) videos
         \-----< (M) clusters

videos (M) >---- (1) cluster
```

### Analysis Model

**File:** `backend/models/analysis.py`

**Purpose:** Track each analysis job

```python
class Analysis(Base):
    __tablename__ = 'analyses'

    id = Column(Integer, primary_key=True)
    status = Column(Enum(AnalysisStatus))  # PENDING/PROCESSING/COMPLETED/FAILED
    created_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    total_videos = Column(Integer)
    total_clusters = Column(Integer, nullable=True)
    quota_used = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Relationships
    videos = relationship("Video", back_populates="analysis")
    clusters = relationship("Cluster", back_populates="analysis")
```

**Status Flow:**
```
PENDING → PROCESSING → COMPLETED
                    └─> FAILED
```

### Video Model

**File:** `backend/models/video.py`

**Purpose:** Store video metadata and embeddings

```python
class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey('analyses.id'))
    video_id = Column(String(11))  # YouTube video ID
    title = Column(String(500))
    channel_id = Column(String(100))
    channel_name = Column(String(200))
    published_at = Column(DateTime)
    watched_at = Column(DateTime)

    # Metrics
    duration = Column(Integer)  # seconds
    view_count = Column(Integer)
    like_count = Column(Integer)
    comment_count = Column(Integer)

    # Embeddings
    embedding = Column(ARRAY(Float))  # 384-dim vector
    embedding_model = Column(String(100))  # "all-MiniLM-L6-v2"

    # Clustering
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=True)
    cluster_label = Column(String(200), nullable=True)
    distance_to_center = Column(Float, nullable=True)

    # Status
    is_processed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
```

**Indexes:**
```python
__table_args__ = (
    Index('idx_analysis_video', 'analysis_id', 'video_id', unique=True),
    Index('idx_cluster', 'cluster_id'),
)
```

### Cluster Model

**File:** `backend/models/cluster.py`

**Purpose:** Group videos by semantic similarity

```python
class Cluster(Base):
    __tablename__ = 'clusters'

    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey('analyses.id'))
    cluster_number = Column(Integer)
    cluster_label = Column(String(200))
    topic_label = Column(String(200))

    # Metrics
    video_count = Column(Integer)
    total_views = Column(Integer)
    avg_views = Column(Float)

    # Scores
    demand_score = Column(Float)
    competition_score = Column(Float)
    opportunity_score = Column(Float)

    # Metadata
    weight = Column(Float)  # % of total videos
    summary_stats = Column(JSON)  # Additional stats

    # Relationships
    videos = relationship("Video", back_populates="cluster")
```

### Database Queries

**Common Patterns:**

```python
from backend.database import get_db
from backend.models.analysis import Analysis
from backend.models.video import Video

# Create analysis
with get_db() as db:
    analysis = Analysis(
        status=AnalysisStatus.PENDING,
        total_videos=1000
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

# Query videos by cluster
videos = db.query(Video).filter(
    Video.cluster_id == cluster_id
).order_by(
    Video.view_count.desc()
).limit(10).all()

# Update analysis status
analysis = db.query(Analysis).get(analysis_id)
analysis.status = AnalysisStatus.COMPLETED
analysis.completed_at = datetime.utcnow()
db.commit()
```

---

## API Endpoints

### Current Endpoints (v2.0)

**Base URL:** `http://localhost:8000`

**Authentication:** Bearer token in `Authorization` header

#### 1. Health Check

```http
GET /
```

**Response:**
```json
{
  "status": "ok",
  "message": "YouTube Audit Engine API is running"
}
```

#### 2. Analyze Watch History

```http
POST /analyze
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <watch-history.json or Takeout.zip>
api_key: <google-api-key>
```

**Response (200 OK):**
```json
{
  "analysis_id": 123,
  "summary": {
    "total_videos": 1000,
    "total_clusters": 8,
    "quota_used": 20
  },
  "clusters": [
    {
      "cluster_number": 0,
      "label": "Machine Learning Tutorials",
      "video_count": 150,
      "total_views": 5000000,
      "opportunity_score": 0.85,
      "top_videos": [...]
    }
  ],
  "top_channels": [
    {
      "channel_name": "3Blue1Brown",
      "video_count": 25,
      "total_views": 1200000
    }
  ]
}
```

**Error Responses:**

| Status | Error | Reason |
|--------|-------|--------|
| 400 | FileValidationError | Invalid file size/type |
| 401 | InvalidTokenError | Missing/invalid bearer token |
| 503 | QuotaExceededError | YouTube API quota exceeded |
| 500 | InternalServerError | Processing error |

### Future Endpoints (Async - Planned)

```http
POST /analyze          → Returns job_id (202 Accepted)
GET  /jobs/{id}        → Job status & progress
GET  /jobs/{id}/results → Results when complete
GET  /analyses         → List all analyses
GET  /analyses/{id}    → Specific analysis
```

---

## Configuration Management

### Configuration File

**Location:** `backend/config.py`

**Type:** Pydantic Settings (type-safe, validated)

**Key Sections:**

1. **Security**
   ```python
   API_BEARER_TOKEN: str  # Required, min 16 chars
   SECRET_KEY: str = field(default_factory=generate_secret)
   CORS_ORIGINS: List[str] = ["http://localhost:8501"]
   ```

2. **Database**
   ```python
   DATABASE_URL: str = "postgresql://..."
   DATABASE_POOL_SIZE: int = 10
   DATABASE_MAX_OVERFLOW: int = 20
   ```

3. **Redis**
   ```python
   REDIS_URL: str = "redis://localhost:6379/0"
   REDIS_MAX_CONNECTIONS: int = 50
   ```

4. **YouTube API**
   ```python
   GOOGLE_API_KEY: str  # Required
   YOUTUBE_API_TIMEOUT: int = 30
   YOUTUBE_API_RETRY_ATTEMPTS: int = 3
   YOUTUBE_API_BATCH_SIZE: int = 50
   YOUTUBE_QUOTA_LIMIT: int = 10000
   ```

5. **Embeddings**
   ```python
   EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
   EMBEDDING_DIMENSION: int = 384
   EMBEDDING_BATCH_SIZE: int = 32
   ```

6. **Clustering**
   ```python
   CLUSTERING_MIN_CLUSTERS: int = 3
   CLUSTERING_MAX_CLUSTERS: int = 15
   CLUSTERING_ALGORITHM: str = "kmeans"
   ```

### Environment Variables

**Required:**
```env
API_BEARER_TOKEN=your-secure-token-min-16-chars
GOOGLE_API_KEY=your-google-api-key
```

**Optional (with defaults):**
```env
ENVIRONMENT=development
DATABASE_URL=postgresql://user:pass@localhost/youtube_audit
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE_MB=100
CACHE_TTL_SECONDS=3600
```

### Configuration Access

```python
from backend.config import get_config

config = get_config()

# Type-safe access
api_key = config.GOOGLE_API_KEY
batch_size = config.YOUTUBE_API_BATCH_SIZE
```

---

## Error Handling

### Exception Hierarchy

**Location:** `backend/exceptions.py`

**Base Exception:**
```python
class YouTubeAuditError(Exception):
    """Base exception for all custom errors"""
    error_code: str = "GENERAL_000"
    user_message: str = "An error occurred"
    status_code: int = 500
```

**Key Exception Types:**

1. **ValidationError** (400)
   - `FileSizeError`: File exceeds limit
   - `FileTypeError`: Invalid file type
   - `APIKeyValidationError`: Invalid API key format

2. **AuthenticationError** (401)
   - `InvalidTokenError`: Bearer token invalid

3. **EnrichmentError** (503)
   - `QuotaExceededError`: YouTube API quota exceeded
   - `RateLimitError`: API rate limit hit
   - `YouTubeAPIError`: General API error

4. **EmbeddingError** (500)
   - `ModelLoadError`: Failed to load ML model
   - `VectorStoreError`: FAISS error

5. **ClusteringError** (500)
   - `InsufficientDataError`: Too few videos to cluster

### Error Handler Middleware

**Location:** `backend/middleware/error_handler.py`

**Functionality:**
- Catches all `YouTubeAuditError` exceptions
- Maps to appropriate HTTP status codes
- Returns standardized JSON response
- Logs with correlation ID
- Sanitizes sensitive data

**Response Format:**
```json
{
  "error": "QuotaExceededError",
  "error_code": "ENRICHMENT_003",
  "message": "YouTube API quota exceeded for today",
  "user_message": "Daily API limit reached. Please try again tomorrow.",
  "correlation_id": "abc-123-def-456",
  "status_code": 503
}
```

### Logging Errors

**Pattern:**
```python
logger.error(
    "YouTube API quota exceeded",
    correlation_id=correlation_id,
    quota_used=quota_used,
    quota_limit=quota_limit,
    exc_info=True  # Include stack trace
)
```

---

## Testing Strategy

### Current Status

⚠️ **No tests currently implemented**

### Recommended Testing Structure

```
tests/
├── conftest.py                 # Pytest fixtures
├── unit/                       # Unit tests (fast, isolated)
│   ├── test_config.py
│   ├── test_validators.py
│   ├── test_exceptions.py
│   ├── test_modules/
│   │   ├── test_ingestion.py
│   │   ├── test_enrichment.py
│   │   ├── test_embedding.py
│   │   ├── test_clustering.py
│   │   └── test_scoring.py
│   └── test_services/
│       ├── test_youtube_api.py
│       ├── test_quota_manager.py
│       └── test_metadata_cache.py
├── integration/                # Integration tests (DB, Redis, API)
│   ├── test_api_endpoints.py
│   ├── test_database.py
│   ├── test_redis_cache.py
│   └── test_full_pipeline.py
├── fixtures/                   # Test data
│   ├── sample_takeout.json
│   ├── sample_takeout.zip
│   └── mock_youtube_responses.json
└── e2e/                        # End-to-end tests
    └── test_complete_workflow.py
```

### Testing Dependencies

**Already in requirements.txt:**
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0
httpx>=0.24.1
```

### Fixture Examples

**conftest.py:**
```python
import pytest
from backend.database import get_engine, Base
from backend.config import get_config

@pytest.fixture(scope="session")
def test_config():
    """Override config for testing"""
    return get_config(
        DATABASE_URL="sqlite:///test.db",
        REDIS_URL="redis://localhost:6379/15"  # Different DB
    )

@pytest.fixture(scope="function")
def db_session(test_config):
    """Create clean DB session for each test"""
    engine = get_engine(test_config.DATABASE_URL)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session
        session.rollback()

    Base.metadata.drop_all(engine)

@pytest.fixture
def sample_video_data():
    """Sample video metadata for testing"""
    return {
        "video_id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up",
        "channel_name": "RickAstleyVEVO",
        "view_count": 1000000000
    }
```

### Test Example

**tests/unit/test_validators.py:**
```python
import pytest
from backend.validators import validate_file_size, FileSizeError

def test_validate_file_size_success():
    """Test file size within limits"""
    # Should not raise
    validate_file_size(50 * 1024 * 1024)  # 50MB

def test_validate_file_size_exceeds_limit():
    """Test file size exceeds limit"""
    with pytest.raises(FileSizeError) as exc_info:
        validate_file_size(200 * 1024 * 1024)  # 200MB

    assert exc_info.value.status_code == 400
    assert "exceeds maximum" in str(exc_info.value)
```

---

## Common Development Tasks

### Task 1: Add a New Configuration Setting

**Steps:**

1. **Add to `backend/config.py`:**
   ```python
   class Config(BaseSettings):
       # Existing settings...

       # New setting
       NEW_FEATURE_ENABLED: bool = False
       NEW_FEATURE_TIMEOUT: int = 60
   ```

2. **Update `.env` (if needed):**
   ```env
   NEW_FEATURE_ENABLED=true
   NEW_FEATURE_TIMEOUT=120
   ```

3. **Use in code:**
   ```python
   from backend.config import get_config

   config = get_config()
   if config.NEW_FEATURE_ENABLED:
       # Feature logic
   ```

### Task 2: Add a New API Endpoint

**Steps:**

1. **Add route in `backend/main.py`:**
   ```python
   @app.route('/api/v1/new-endpoint', methods=['POST'])
   @require_bearer_token  # Auth decorator
   def new_endpoint():
       correlation_id = request.correlation_id

       try:
           # Validate input
           data = request.get_json()
           validate_new_endpoint_input(data)

           # Process
           result = process_new_feature(data)

           # Log success
           logger.info(
               "New endpoint processed",
               correlation_id=correlation_id,
               data_size=len(data)
           )

           return jsonify(result), 200

       except ValidationError as e:
           logger.error("Validation failed", correlation_id=correlation_id)
           raise
   ```

2. **Add validation in `backend/validators.py`:**
   ```python
   def validate_new_endpoint_input(data):
       if not data.get('required_field'):
           raise ValidationError("Missing required_field")
   ```

3. **Add processing logic:**
   - Create new module in `backend/modules/` or `backend/services/`

4. **Update frontend to call endpoint:**
   ```python
   # frontend/app.py or cli/interface.py
   response = requests.post(
       f"{API_URL}/api/v1/new-endpoint",
       headers={"Authorization": f"Bearer {token}"},
       json={"required_field": "value"}
   )
   ```

### Task 3: Add a New Database Model

**Steps:**

1. **Create model in `backend/models/`:**
   ```python
   # backend/models/new_model.py
   from sqlalchemy import Column, Integer, String, ForeignKey
   from backend.database import Base

   class NewModel(Base):
       __tablename__ = 'new_models'

       id = Column(Integer, primary_key=True)
       name = Column(String(200), nullable=False)
       analysis_id = Column(Integer, ForeignKey('analyses.id'))
   ```

2. **Import in `backend/models/__init__.py`:**
   ```python
   from .new_model import NewModel

   __all__ = ['Analysis', 'Video', 'Cluster', 'NewModel']
   ```

3. **Create migration:**
   ```bash
   alembic revision --autogenerate -m "Add NewModel table"
   ```

4. **Review migration file:**
   ```bash
   # Check alembic/versions/XXXXXX_add_newmodel_table.py
   ```

5. **Apply migration:**
   ```bash
   alembic upgrade head
   ```

### Task 4: Add a Custom Exception

**Steps:**

1. **Define in `backend/exceptions.py`:**
   ```python
   class NewFeatureError(YouTubeAuditError):
       """Raised when new feature fails"""
       error_code = "NEW_FEATURE_001"
       user_message = "New feature encountered an error"
       status_code = 503  # Service Unavailable
   ```

2. **Raise in code:**
   ```python
   from backend.exceptions import NewFeatureError

   if some_failure_condition:
       raise NewFeatureError(
           message="Detailed technical message",
           user_message="User-friendly message"
       )
   ```

3. **Error handler automatically catches it** (no changes needed)

### Task 5: Add a New Processing Module

**Steps:**

1. **Create module file:**
   ```python
   # backend/modules/new_processing.py
   from backend.utils.logging_config import get_logger
   from backend.exceptions import ProcessingError

   logger = get_logger(__name__)

   def process_data(data, correlation_id=None):
       """Process data with new algorithm"""
       logger.info(
           "Starting new processing",
           correlation_id=correlation_id,
           data_size=len(data)
       )

       try:
           # Processing logic
           result = perform_processing(data)

           logger.info(
               "Processing complete",
               correlation_id=correlation_id,
               result_size=len(result)
           )

           return result

       except Exception as e:
           logger.error(
               "Processing failed",
               correlation_id=correlation_id,
               error=str(e),
               exc_info=True
           )
           raise ProcessingError(f"Failed to process: {e}")
   ```

2. **Integrate into pipeline:**
   ```python
   # backend/main.py
   from backend.modules.new_processing import process_data

   # In analyze_endpoint:
   processed_data = process_data(raw_data, correlation_id)
   ```

### Task 6: Update Dependencies

**Steps:**

1. **Update `requirements.txt`:**
   ```
   new-package>=1.0.0
   ```

2. **Install locally:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Rebuild Docker images:**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

4. **Test thoroughly before committing**

---

## Git Workflow

### Branch Strategy

**Main Branch:** `main` (or as specified in session context)

**Feature Branches:** `claude/feature-name-{session-id}`

**Example:** `claude/claude-md-mhyqhbtne9wg6co1-01MWiFfegPpxi9YJS5ijxm4x`

### Development Workflow

1. **Check current branch:**
   ```bash
   git status
   git branch
   ```

2. **Create feature branch (if needed):**
   ```bash
   git checkout -b claude/feature-name-{session-id}
   ```

3. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "feat: Add comprehensive CLAUDE.md documentation

   - Created AI assistant guide
   - Documented codebase structure
   - Added development workflows
   - Included common tasks"
   ```

4. **Push to remote:**
   ```bash
   git push -u origin claude/feature-name-{session-id}
   ```

5. **Create pull request (if needed):**
   ```bash
   # Use GitHub UI or gh CLI
   gh pr create --title "Add CLAUDE.md" --body "Comprehensive AI assistant guide"
   ```

### Commit Message Convention

**Format:**
```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Add/update tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: Add YouTube API quota tracking

- Implemented Redis-based quota counter
- Added daily quota limit checks
- Integrated with enrichment module

Closes #123
```

```
fix: Resolve SQLAlchemy session leak in analysis pipeline

- Added proper session cleanup
- Implemented context manager pattern
- Updated error handling to close sessions

Fixes #456
```

### Git Safety Rules

1. **NEVER:**
   - Force push to main/master
   - Commit secrets (.env files)
   - Skip hooks without explicit user request
   - Amend other developers' commits

2. **ALWAYS:**
   - Use descriptive commit messages
   - Test before committing
   - Push to feature branches starting with `claude/`
   - Check authorship before amending

---

## Code Style & Conventions

### Python Style Guide

**Follow PEP 8** with these specifics:

1. **Line Length:** 100 characters (not 79)
2. **Indentation:** 4 spaces (no tabs)
3. **Imports:**
   ```python
   # Standard library
   import os
   import sys
   from datetime import datetime

   # Third-party
   import requests
   from flask import Flask, request
   from sqlalchemy import Column, Integer

   # Local
   from backend.config import get_config
   from backend.exceptions import ValidationError
   ```

4. **String Formatting:** f-strings preferred
   ```python
   # Good
   message = f"Processed {count} videos in {duration}s"

   # Avoid
   message = "Processed {} videos in {}s".format(count, duration)
   ```

5. **Type Hints:** Use when helpful
   ```python
   def process_videos(video_ids: List[str]) -> Dict[str, Any]:
       """Process videos and return results"""
       ...
   ```

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Variables | snake_case | `video_count`, `api_key` |
| Functions | snake_case | `get_metadata()`, `process_data()` |
| Classes | PascalCase | `YouTubeAPIClient`, `VideoModel` |
| Constants | UPPER_SNAKE_CASE | `MAX_BATCH_SIZE`, `DEFAULT_TIMEOUT` |
| Private | _prefix | `_internal_helper()` |
| Modules | snake_case | `youtube_api.py`, `metadata_cache.py` |

### Docstring Convention

**Use Google-style docstrings:**

```python
def enrich_videos(video_ids: List[str], api_key: str) -> Dict[str, Any]:
    """Enrich videos with metadata from YouTube API.

    Args:
        video_ids: List of YouTube video IDs (11 chars each)
        api_key: Google API key for YouTube Data API v3

    Returns:
        Dictionary mapping video_id to metadata dict containing:
            - title: Video title
            - channel_name: Channel name
            - view_count: Number of views
            - (additional fields)

    Raises:
        QuotaExceededError: If YouTube API quota is exceeded
        YouTubeAPIError: If API request fails

    Example:
        >>> metadata = enrich_videos(["dQw4w9WgXcQ"], api_key)
        >>> metadata["dQw4w9WgXcQ"]["title"]
        "Rick Astley - Never Gonna Give You Up"
    """
```

### Logging Conventions

1. **Use correlation IDs:**
   ```python
   logger.info(
       "Event description",
       correlation_id=correlation_id,
       key_metric=value
   )
   ```

2. **Choose appropriate levels:**
   - `DEBUG`: Detailed diagnostic info
   - `INFO`: General informational messages
   - `WARNING`: Warning messages (recoverable)
   - `ERROR`: Error messages (handled)
   - `CRITICAL`: Critical errors (unrecoverable)

3. **Sanitize sensitive data:**
   ```python
   # Good
   logger.info("API key validated", api_key_prefix=api_key[:8])

   # Bad
   logger.info("API key validated", api_key=api_key)  # Leaks secret!
   ```

---

## Important Implementation Notes

### 1. Database Sessions

**ALWAYS use context managers:**

```python
# Good
from backend.database import get_db

with get_db() as db:
    analysis = db.query(Analysis).get(analysis_id)
    # Session automatically commits and closes

# Bad
db = Session(engine)
analysis = db.query(Analysis).get(analysis_id)
# Session leak! Not closed properly
```

### 2. Redis Client

**Use singleton pattern:**

```python
from backend.cache import get_redis_client

redis_client = get_redis_client()  # Reuses connection pool
```

### 3. Configuration Access

**Use get_config() function:**

```python
from backend.config import get_config

config = get_config()  # Loads once, cached
api_key = config.GOOGLE_API_KEY
```

### 4. Error Handling

**Raise specific exceptions:**

```python
# Good
from backend.exceptions import FileSizeError

if file_size > max_size:
    raise FileSizeError(
        f"File size {file_size} exceeds max {max_size}",
        user_message="File too large. Maximum size is 100MB."
    )

# Bad
if file_size > max_size:
    raise Exception("File too big")  # Generic, not caught by middleware
```

### 5. Logging Context

**Always include correlation_id:**

```python
correlation_id = request.correlation_id  # Set by middleware

logger.info(
    "Processing started",
    correlation_id=correlation_id,  # REQUIRED for tracing
    video_count=len(video_ids)
)
```

### 6. YouTube API Batching

**Always batch requests:**

```python
# Good (batches of 50)
batch_size = 50
for i in range(0, len(video_ids), batch_size):
    batch = video_ids[i:i+batch_size]
    metadata = youtube_api.fetch(batch)

# Bad (one request per video)
for video_id in video_ids:
    metadata = youtube_api.fetch([video_id])  # Wastes quota!
```

### 7. Embedding Storage

**Store embeddings as PostgreSQL arrays:**

```python
# Good
video.embedding = [0.1, 0.2, ..., 0.384]  # List of floats
db.commit()

# Bad
import json
video.embedding_json = json.dumps(embedding)  # String, can't query efficiently
```

### 8. Environment Variables

**Never commit `.env` files:**

```bash
# .gitignore should include:
.env
.env.*
!.env.example
```

**Provide `.env.example`:**

```env
# .env.example (safe to commit)
API_BEARER_TOKEN=your-secure-token-here
GOOGLE_API_KEY=your-google-api-key-here
ENVIRONMENT=development
```

---

## Debugging & Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem:**
```
ModuleNotFoundError: No module named 'backend'
```

**Solution:**
```bash
# Set PYTHONPATH to project root
export PYTHONPATH=/home/user/YouTubeAudit:$PYTHONPATH

# Or run from project root
cd /home/user/YouTubeAudit
python -m backend.main
```

#### 2. Database Connection Failed

**Problem:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions:**

1. Check PostgreSQL is running:
   ```bash
   docker-compose ps postgres
   # or
   systemctl status postgresql
   ```

2. Verify connection string in `.env`:
   ```env
   DATABASE_URL=postgresql://user:pass@localhost:5432/youtube_audit
   ```

3. Test connection manually:
   ```bash
   psql postgresql://user:pass@localhost:5432/youtube_audit
   ```

#### 3. Redis Connection Failed

**Problem:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions:**

1. Check Redis is running:
   ```bash
   docker-compose ps redis
   # or
   redis-cli ping  # Should return "PONG"
   ```

2. Verify REDIS_URL:
   ```env
   REDIS_URL=redis://localhost:6379/0
   ```

#### 4. YouTube API Quota Exceeded

**Problem:**
```
QuotaExceededError: YouTube API quota exceeded for today
```

**Solutions:**

1. Check quota usage:
   ```python
   from backend.services.quota_manager import QuotaManager

   manager = QuotaManager()
   used = manager.get_daily_usage()
   print(f"Quota used: {used}/10000")
   ```

2. Wait until quota resets (midnight Pacific Time)

3. Request quota increase from Google

4. Use caching to reduce API calls

#### 5. Embedding Model Not Found

**Problem:**
```
OSError: Can't load tokenizer for 'all-MiniLM-L6-v2'
```

**Solution:**
```bash
# Download model manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Debugging Tools

#### 1. Check Logs

```bash
# Docker logs
docker-compose logs backend -f
docker-compose logs celery_worker -f

# Local logs
tail -f backend.log
```

#### 2. Database Inspection

```bash
# Connect to database
docker-compose exec postgres psql -U youtube_audit -d youtube_audit

# List tables
\dt

# Check analysis records
SELECT id, status, total_videos, created_at FROM analyses ORDER BY created_at DESC LIMIT 10;

# Check videos
SELECT COUNT(*) FROM videos WHERE analysis_id = 123;
```

#### 3. Redis Inspection

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check keys
KEYS video_metadata:*
KEYS youtube_quota:*

# Get value
GET video_metadata:dQw4w9WgXcQ

# Check quota
GET youtube_quota:2025-01-21
```

#### 4. Interactive Python Shell

```python
# Start shell with context
python
>>> from backend.config import get_config
>>> from backend.database import get_db
>>> from backend.models.analysis import Analysis
>>>
>>> config = get_config()
>>> with get_db() as db:
...     analyses = db.query(Analysis).all()
...     print(len(analyses))
```

#### 5. API Testing

```bash
# Health check
curl http://localhost:8000/

# Analyze (with file)
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer your-token" \
  -F "file=@watch-history.json" \
  -F "api_key=your-google-api-key"
```

### Performance Profiling

**Add timing to identify bottlenecks:**

```python
import time

start = time.time()
result = expensive_operation()
duration = time.time() - start

logger.info(
    "Operation completed",
    correlation_id=correlation_id,
    operation="expensive_operation",
    duration_seconds=duration
)
```

---

## Appendix: Quick Reference

### Key Commands

| Task | Command |
|------|---------|
| Start all services | `docker-compose up --build` |
| Start backend only | `python backend/main.py` |
| Start frontend only | `streamlit run frontend/app.py` |
| Run CLI interactive | `python -m cli.interface --interactive` |
| Apply migrations | `alembic upgrade head` |
| Create migration | `alembic revision --autogenerate -m "message"` |
| Check logs | `docker-compose logs -f backend` |
| Connect to DB | `docker-compose exec postgres psql -U youtube_audit` |
| Connect to Redis | `docker-compose exec redis redis-cli` |

### Important File Paths

| What | Path |
|------|------|
| Configuration | `backend/config.py` |
| Main API | `backend/main.py` |
| Database models | `backend/models/` |
| Processing modules | `backend/modules/` |
| YouTube API | `backend/services/youtube_api.py` |
| Exceptions | `backend/exceptions.py` |
| Logging config | `backend/utils/logging_config.py` |
| Migrations | `alembic/versions/` |
| Docker Compose | `docker-compose.yml` |
| Dependencies | `requirements.txt` |

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `API_BEARER_TOKEN` | ✅ | - | API authentication |
| `GOOGLE_API_KEY` | ✅ | - | YouTube API access |
| `DATABASE_URL` | ⚠️ | SQLite | Database connection |
| `REDIS_URL` | ⚠️ | fakeredis | Cache connection |
| `ENVIRONMENT` | ❌ | development | Environment name |
| `LOG_LEVEL` | ❌ | INFO | Logging verbosity |
| `MAX_UPLOAD_SIZE_MB` | ❌ | 100 | File size limit |

### Default Ports

| Service | Port | Access URL |
|---------|------|------------|
| Flask Backend | 8000 | http://localhost:8000 |
| Streamlit Frontend | 8501 | http://localhost:8501 |
| PostgreSQL | 5432 | postgresql://localhost:5432 |
| Redis | 6379 | redis://localhost:6379 |
| Flower (Celery UI) | 5555 | http://localhost:5555 |

---

## Conclusion

This guide provides a comprehensive foundation for AI assistants working on the YouTube Audit Engine codebase. Key takeaways:

1. **Architecture**: Two-service (backend + frontend) with PostgreSQL and Redis
2. **Pipeline**: 5-step processing (Ingestion → Enrichment → Embedding → Clustering → Scoring)
3. **Configuration**: Centralized in `backend/config.py` with Pydantic validation
4. **Error Handling**: Hierarchical custom exceptions with middleware
5. **Database**: SQLAlchemy with Alembic migrations
6. **API**: Flask REST API with bearer token auth
7. **Logging**: Structured logging with correlation IDs
8. **Testing**: Infrastructure ready, tests pending implementation

**For Further Reading:**
- [README.md](README.md) - User guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed architecture
- [CLI_GUIDE.md](CLI_GUIDE.md) - CLI usage
- [WINDOWS_SETUP.md](WINDOWS_SETUP.md) - Windows setup

**Last Updated:** 2025-01-21
**Maintainer:** AI Development Team
**Version:** 2.0
