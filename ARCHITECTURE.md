# YouTube Audit Engine - System Architecture

**Version:** 2.0 (with improvements)
**Date:** 2025-10-20

---

## Table of Contents

1. [Current Architecture (v1.0)](#current-architecture-v10)
2. [Improved Architecture (v2.0 - Proposed)](#improved-architecture-v20-proposed)
3. [Component Breakdown](#component-breakdown)
4. [Data Flow](#data-flow)
5. [Error Handling Architecture](#error-handling-architecture)
6. [Deployment Architecture](#deployment-architecture)

---

## Current Architecture (v1.0)

### High-Level Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                              │
└────────────────┬─────────────────────────────────────────────────┘
                 │
                 │ HTTP Request (file upload)
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    STREAMLIT FRONTEND                             │
│                     (Port 8501)                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  - File Upload UI                                         │   │
│  │  - API Key Input                                          │   │
│  │  - Results Visualization                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────┬─────────────────────────────────────────────────┘
                 │
                 │ POST /analyze (with file + API key)
                 │ **BLOCKS FOR 15 MINUTES**
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                      FLASK BACKEND                                │
│                       (Port 8000)                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. Bearer Token Auth                                     │   │
│  │  2. File Validation                                       │   │
│  │  3. Synchronous Pipeline (BLOCKS!)                        │   │
│  │     ├─ Ingestion                                          │   │
│  │     ├─ Enrichment (PLACEHOLDER - returns dummy data)      │   │
│  │     ├─ Embedding (RANDOM vectors)                         │   │
│  │     ├─ Clustering                                         │   │
│  │     └─ Scoring (RANDOM scores)                            │   │
│  │  4. Return JSON results                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘

                 **NO PERSISTENCE**
                 **NO CACHING**
                 **NO BACKGROUND JOBS**
```

### Problems

❌ Synchronous processing blocks frontend for 15+ minutes
❌ No result persistence (lost on browser close)
❌ Placeholder implementations (no real functionality)
❌ No caching (redundant API calls)
❌ No queue (cannot handle concurrent requests)
❌ No error recovery

---

## Improved Architecture (v2.0 - Proposed)

### Complete System Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                    USER BROWSER                                           │
└──────────────────────┬────────────────────────────────────────────────────────────────────┘
                       │
                       │ 1. Upload file
                       ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                            STREAMLIT FRONTEND (Port 8501)                                 │
│  ┌────────────────────────────────────────────────────────────────────────────────┐      │
│  │  Features:                                                                      │      │
│  │  • File upload + validation                                                    │      │
│  │  • Job submission → immediate job ID                                           │      │
│  │  • Progress polling (GET /jobs/{id})                                           │      │
│  │  • Results retrieval                                                           │      │
│  │  • Analysis history list                                                       │      │
│  │  • Comparison view (timeline)                                                  │      │
│  │  • Export (CSV/JSON/PDF)                                                       │      │
│  └────────────────────────────────────────────────────────────────────────────────┘      │
└──────────────────────┬────────────────────────────────────────────────────────────────────┘
                       │
                       │ 2. POST /analyze → Returns job ID immediately
                       │ 3. Poll GET /jobs/{id} for progress
                       ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                           FLASK API GATEWAY (Port 8000)                                   │
│  ┌────────────────────────────────────────────────────────────────────────────────┐      │
│  │  NEW COMPONENTS:                                                               │      │
│  │  ┌─────────────────────┬──────────────────────┬────────────────────────┐      │      │
│  │  │ Correlation Middleware│ Error Handler        │ Config Management      │      │      │
│  │  │ (Request Tracing)    │ (Centralized)        │ (Pydantic)             │      │      │
│  │  └─────────────────────┴──────────────────────┴────────────────────────┘      │      │
│  │                                                                                 │      │
│  │  ENDPOINTS:                                                                    │      │
│  │  • POST /analyze         → Queue job, return job_id (202 Accepted)           │      │
│  │  • GET  /jobs/{id}       → Job status & progress                              │      │
│  │  • GET  /jobs/{id}/results → Completed results                                │      │
│  │  • GET  /analyses        → List all analyses                                  │      │
│  │  • GET  /analyses/{id}   → Specific analysis                                  │      │
│  │  • GET  /analyses/compare → Compare two analyses                              │      │
│  │  • GET  /health          → Health check                                       │      │
│  └────────────────────────────────────────────────────────────────────────────────┘      │
└──────────────────────┬──────────────────────┬─────────────────────────────────────────────┘
                       │                      │
         4. Queue task │                      │ 7. Read job status/results
                       ▼                      ▼
         ┌──────────────────────┐   ┌────────────────────┐
         │   REDIS (Port 6379)  │   │   POSTGRESQL       │
         │                      │   │   (Port 5432)      │
         │  • Message Queue     │   │                    │
         │  • Job Results       │   │  • Analyses        │
         │  • Metadata Cache    │   │  • Clusters        │
         │  • Quota Tracking    │   │  • Videos          │
         │                      │   │  • Watch Events    │
         └──────────┬───────────┘   └────────────────────┘
                    │                         ▲
         5. Dequeue │                         │ 8. Persist results
                    ▼                         │
         ┌──────────────────────────────────────────┐
         │    CELERY WORKERS (Background)           │
         │  ┌────────────────────────────────────┐  │
         │  │  Analysis Pipeline (Async):        │  │
         │  │  1. Ingestion                      │  │
         │  │  2. Enrichment ──────┐             │  │
         │  │  3. Embedding        │             │  │
         │  │  4. Clustering       │             │  │
         │  │  5. Scoring          │             │  │
         │  └──────────────────────┼─────────────┘  │
         │                         │                 │
         │  Progress Updates:      │                 │
         │  • Step 1/5 complete    │                 │
         │  • Enriched 340/1000    │                 │
         └─────────────────────────┼─────────────────┘
                                   │
                         6. YouTube API calls
                         (with caching & quota mgmt)
                                   ▼
                   ┌────────────────────────────────┐
                   │   YouTube Data API v3          │
                   │                                │
                   │  • Video metadata              │
                   │  • Channel info                │
                   │  • Statistics                  │
                   │                                │
                   │  Rate Limits:                  │
                   │  • 10,000 units/day default    │
                   │  • 50 videos/request           │
                   └────────────────────────────────┘
```

---

## Component Breakdown

### 1. Frontend (Streamlit)

**Purpose:** User interface for uploading files and viewing results

**Components:**
```
frontend/
├── app.py                      # Main Streamlit application
├── components/
│   ├── upload.py              # File upload component
│   ├── progress.py            # Job progress tracker
│   ├── results.py             # Results visualization
│   ├── history.py             # Analysis history
│   └── comparison.py          # Timeline comparison
└── utils/
    ├── api_client.py          # Backend API client
    └── chart_builders.py      # Plotly chart builders
```

**Key Improvements:**
- Non-blocking job submission
- Real-time progress updates
- Historical analysis view
- Comparison mode

### 2. Backend (Flask)

**Purpose:** API gateway and request orchestration

**Components:**
```
backend/
├── main.py                     # Flask app with endpoints
├── config.py                   # Centralized config (Pydantic)
├── exceptions.py               # Custom exception hierarchy
├── validators.py               # Input validation layer
├── middleware/
│   ├── correlation.py         # Request ID tracking
│   └── error_handler.py       # Global error handler
├── modules/
│   ├── ingestion.py           # Parse Takeout files
│   ├── enrichment.py          # YouTube API integration
│   ├── embedding.py           # Generate embeddings
│   ├── clustering.py          # K-Means clustering
│   ├── labeling.py            # Cluster labeling
│   └── scoring.py             # Score clusters
├── services/
│   ├── youtube_api.py         # YouTube API client
│   ├── quota_manager.py       # Quota tracking
│   └── metadata_cache.py      # Redis caching
├── tasks/
│   └── analysis.py            # Celery tasks
├── models/
│   ├── analysis.py            # SQLAlchemy models
│   ├── cluster.py
│   └── video.py
└── utils/
    ├── logging_config.py      # Structured logging
    └── retry.py               # Retry decorators
```

**Key Improvements:**
- Centralized configuration
- Comprehensive error handling
- Structured logging with correlation IDs
- Input validation layer
- Middleware architecture

### 3. Task Queue (Celery + Redis)

**Purpose:** Asynchronous job processing

**Architecture:**
```
┌─────────────────┐
│  Flask API      │
│  (Producer)     │
└────────┬────────┘
         │ task.delay()
         ▼
┌─────────────────┐
│  Redis Queue    │
│  [Job1][Job2]   │
└────────┬────────┘
         │ Dequeue
         ▼
┌─────────────────┐
│ Celery Worker 1 │
│ Celery Worker 2 │
│ Celery Worker 3 │
└────────┬────────┘
         │ Store results
         ▼
┌─────────────────┐
│ Redis Results   │
└─────────────────┘
```

**Configuration:**
```python
# celery_config.py
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/1'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour max
```

### 4. Database (PostgreSQL)

**Purpose:** Persistent storage for all analysis data

**Schema Overview:**
```sql
┌──────────────┐       ┌──────────────┐
│   users      │       │  analyses    │
│──────────────│       │──────────────│
│ id (PK)      │◀─────┼│ id (PK)      │
│ email        │      ││ user_id (FK) │
│ created_at   │      ││ status       │
└──────────────┘      ││ file_hash    │
                      ││ video_count  │
                      │└──────────────┘
                      │       │
                      │       │
┌──────────────┐      │       │       ┌──────────────┐
│   clusters   │      │       │       │   videos     │
│──────────────│      │       │       │──────────────│
│ id (PK)      │      │       │       │ video_id(PK) │
│ analysis_id  │◀─────┘       └──────▶│ title        │
│ (FK)         │                      │ channel_id   │
│ cluster_num  │                      │ view_count   │
│ weight       │                      │ enriched_at  │
│ scores       │                      └──────────────┘
└──────────────┘
```

### 5. Caching Layer (Redis)

**Purpose:** Reduce redundant API calls and improve performance

**Cache Types:**

1. **Metadata Cache** (TTL: 7 days)
   ```
   Key: video_metadata:{video_id}
   Value: {title, channel, stats, ...}
   ```

2. **Quota Tracking** (TTL: 24 hours)
   ```
   Key: youtube_quota:2025-10-20
   Value: 1247  # units used today
   ```

3. **Job Results** (TTL: 24 hours)
   ```
   Key: celery-task-meta-{task_id}
   Value: {status, progress, result}
   ```

### 6. YouTube API Integration

**Request Flow:**
```
┌─────────────────────────────────────────────────────────────┐
│ 1. Enrichment Request (1000 video IDs)                      │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Check Metadata Cache                                     │
│    Cache Hit: 820 videos ✓                                  │
│    Cache Miss: 180 videos                                   │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Check Quota Available                                    │
│    Required: 4 batches × 1 unit = 4 units                  │
│    Available: 9,850 units ✓                                 │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Batch API Requests (180 videos → 4 batches)             │
│    Batch 1: 50 videos                                       │
│    Batch 2: 50 videos                                       │
│    Batch 3: 50 videos                                       │
│    Batch 4: 30 videos                                       │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Cache New Results (180 videos)                          │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Return Combined Results (820 cached + 180 fresh)         │
│    API Efficiency: 82% cache hit rate                       │
│    Quota Saved: 16 units                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Complete Analysis Flow (v2.0)

```
┌─────────┐
│  USER   │
│ Uploads │
│  File   │
└────┬────┘
     │
     ▼
1. Frontend validates file locally
     │
     ▼
2. POST /analyze with file + API key
     │
     ▼
┌────────────────────────────────────┐
│  Flask API                         │
│  1. Validate Bearer token          │
│  2. Validate file (size, type)     │
│  3. Validate API key format        │
│  4. Generate correlation ID        │
│  5. Save file to temp location     │
│  6. Create database record         │
│     (status: queued)               │
│  7. Queue Celery task              │
│  8. Return job_id (HTTP 202)       │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  Redis Queue                       │
│  [Job: abc-123]                    │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  Celery Worker picks up task      │
│  1. Update status: processing      │
│  2. Set progress: 0%               │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  STEP 1: Ingestion                 │
│  • Parse ZIP/JSON                  │
│  • Extract video IDs               │
│  • Validate data                   │
│  • Progress: 20%                   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  STEP 2: Enrichment                │
│  • Check cache (Redis)             │
│  • Fetch missing from YouTube API  │
│  • Batch requests (50/call)        │
│  • Track quota usage               │
│  • Update cache                    │
│  • Progress: 40%                   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  STEP 3: Embedding                 │
│  • Load sentence-transformer       │
│  • Generate embeddings             │
│  • Progress: 60%                   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  STEP 4: Clustering                │
│  • Determine optimal K             │
│  • Run K-Means                     │
│  • Build cluster mappings          │
│  • Progress: 80%                   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  STEP 5: Scoring                   │
│  • Calculate demand metrics        │
│  • Calculate competition           │
│  • Calculate opportunity           │
│  • Progress: 100%                  │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  Store Results                     │
│  • Save to PostgreSQL              │
│  • Update status: completed        │
│  • Store in Redis (24h cache)     │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  Frontend Polling                  │
│  GET /jobs/abc-123                 │
│  Response: {                       │
│    "status": "completed",          │
│    "result_url": "/jobs/.../results"│
│  }                                 │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  Display Results                   │
│  • Cluster visualization           │
│  • Topic breakdown                 │
│  • Opportunity scores              │
└────────────────────────────────────┘
```

---

## Error Handling Architecture

### Exception Hierarchy

```
YouTubeAuditError (Base)
├── ConfigurationError
│   ├── MissingConfigurationError
│   └── InvalidConfigurationError
├── ValidationError
│   ├── FileValidationError
│   │   ├── FileSizeError
│   │   └── FileTypeError
│   └── APIKeyValidationError
├── AuthenticationError
│   └── InvalidTokenError
├── IngestionError
│   ├── TakeoutParseError
│   ├── MissingWatchHistoryError
│   ├── InvalidJSONError
│   └── EmptyDatasetError
├── EnrichmentError
│   ├── YouTubeAPIError
│   ├── QuotaExceededError
│   └── RateLimitError
├── EmbeddingError
│   ├── ModelLoadError
│   ├── VectorStoreError
│   └── DimensionMismatchError
├── ClusteringError
│   ├── InsufficientDataError
│   └── ClusteringAlgorithmError
└── ExternalServiceError
    ├── TimeoutError
    └── NetworkError
```

### Error Flow

```
┌─────────────────┐
│ Exception Raised│
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Is YouTubeAuditError?            │
├────────────┬────────────────┬────┤
│ YES        │ HTTPException  │ NO │
▼            ▼                ▼
┌─────────────────────────────────┐
│ Error Handler Middleware         │
│ 1. Log with correlation ID       │
│ 2. Map to HTTP status code       │
│ 3. Sanitize user message         │
│ 4. Return JSON response          │
└──────────────┬──────────────────┘
               ▼
{
  "error": "QuotaExceededError",
  "error_code": "ENRICHMENT_003",
  "message": "YouTube API quota exceeded",
  "user_message": "Daily API limit reached. Try again tomorrow.",
  "correlation_id": "abc-123-def-456",
  "status_code": 503
}
```

---

## Deployment Architecture

### Docker Compose Setup

```yaml
version: '3.8'

services:
  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://backend:8000
    depends_on:
      - backend

  # Backend API
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/youtube_audit
      - REDIS_URL=redis://redis:6379
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  # Celery Workers
  celery_worker:
    build: ./backend
    command: celery -A backend.tasks.analysis worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/youtube_audit
      - REDIS_URL=redis://redis:6379
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  # Celery Beat (scheduled tasks)
  celery_beat:
    build: ./backend
    command: celery -A backend.tasks.analysis beat --loglevel=info
    depends_on:
      - redis

  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=youtube_audit
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=youtube_audit
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Flower (Celery monitoring - optional)
  flower:
    build: ./backend
    command: celery -A backend.tasks.analysis flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  postgres_data:
  redis_data:
```

### Service Diagram

```
┌──────────────────────────────────────────────────────┐
│               DOCKER COMPOSE NETWORK                  │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  Frontend    │  │  Backend     │                 │
│  │  :8501       │  │  :8000       │                 │
│  └──────────────┘  └──────────────┘                 │
│         │                  │                         │
│         └──────────┬───────┘                         │
│                    │                                 │
│         ┌──────────┴──────────┐                      │
│         │                     │                      │
│  ┌──────▼──────┐      ┌──────▼──────┐               │
│  │  PostgreSQL │      │   Redis     │               │
│  │  :5432      │      │   :6379     │               │
│  └─────────────┘      └──────┬──────┘               │
│         ▲                    │                       │
│         │             ┌──────┴──────┐                │
│         │             │             │                │
│         │      ┌──────▼──────┐ ┌───▼────────┐       │
│         └──────│Celery Worker│ │Celery Beat │       │
│                └─────────────┘ └────────────┘       │
│                                                       │
│  ┌──────────────┐                                    │
│  │  Flower      │  (Monitoring)                      │
│  │  :5555       │                                    │
│  └──────────────┘                                    │
└──────────────────────────────────────────────────────┘
```

---

## Logging & Monitoring

### Structured Logging Format

```json
{
  "timestamp": "2025-10-20T14:32:11.123Z",
  "level": "INFO",
  "app": "youtube-audit",
  "component": "backend.modules.enrichment",
  "correlation_id": "abc-123-def-456",
  "event": "Metadata enrichment complete",
  "video_count": 1247,
  "quota_used": 25,
  "cache_hit_rate": 0.82
}
```

### Observability Stack (Future)

```
┌─────────────┐
│ Application │
│  Logs       │
└──────┬──────┘
       │
       ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Fluentd    │─────▶│Elasticsearch│─────▶│   Kibana    │
│  (Collect)  │      │   (Store)   │      │  (Visualize)│
└─────────────┘      └─────────────┘      └─────────────┘

┌─────────────┐
│  Metrics    │
│ (Prometheus)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Grafana   │
│ (Dashboard) │
└─────────────┘
```

---

## Security Architecture

### Authentication Flow

```
┌────────────┐
│   User     │
└─────┬──────┘
      │ Bearer Token
      ▼
┌──────────────────────────────┐
│  Flask Middleware            │
│  1. Extract Authorization    │
│  2. Validate token format    │
│  3. Compare with config      │
│  4. Reject or continue       │
└──────────────────────────────┘
```

### Data Sanitization

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│  Validators                  │
│  • File size limits          │
│  • File type whitelist       │
│  • Filename sanitization     │
│  • API key format check      │
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Logging Sanitization        │
│  • Redact API keys           │
│  • Redact tokens             │
│  • Redact passwords          │
└──────────────────────────────┘
```

---

## Summary of Improvements

| Aspect | Before (v1.0) | After (v2.0) |
|--------|---------------|--------------|
| **Architecture** | Synchronous, monolithic | Async, microservices-ready |
| **Scalability** | 1 request at a time | 10+ concurrent |
| **Persistence** | None | PostgreSQL + Redis |
| **Error Handling** | Generic exceptions | Hierarchical, typed errors |
| **Logging** | Basic, inconsistent | Structured, correlated |
| **Monitoring** | None | Health checks, metrics |
| **Configuration** | Hardcoded | Centralized, validated |
| **API Integration** | Placeholder | Production-ready |
| **Caching** | None | Multi-layer (Redis) |
| **Job Management** | None | Queue-based (Celery) |

---

## Next Steps

1. **Phase 1:** Implement core improvements (Config, Logging, Error Handling) ✓
2. **Phase 2:** Add YouTube API integration
3. **Phase 3:** Implement async job processing
4. **Phase 4:** Add database persistence
5. **Phase 5:** Deploy to production
