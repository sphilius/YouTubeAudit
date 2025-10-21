# Implementation Tasks - Ordered Breakdown

## Legend
- 🟢 **Simple** (< 30 min)
- 🟡 **Medium** (30-60 min)
- 🔴 **Complex** (1-2 hours)

---

## Phase 1: Infrastructure Setup (No Dependencies)

### 1.1 Add All Dependencies to requirements.txt 🟢
**Estimated Time:** 5 min
**Dependencies:** None
**Description:** Add all required Python packages for all 3 features
- Redis client
- Celery
- SQLAlchemy, Alembic, psycopg2
- Flower (Celery monitoring)

### 1.2 Update docker-compose.yml with Redis 🟢
**Estimated Time:** 10 min
**Dependencies:** None
**Description:** Add Redis service to docker-compose.yml
- Redis 7-alpine image
- Expose port 6379
- Add volume for persistence

### 1.3 Update docker-compose.yml with PostgreSQL 🟢
**Estimated Time:** 10 min
**Dependencies:** None
**Description:** Add PostgreSQL service to docker-compose.yml
- PostgreSQL 15 image
- Expose port 5432
- Environment variables (user, password, database)
- Add volume for persistence

---

## Phase 2: Database Foundation (Depends on 1.3)

### 2.1 Create database connection module 🟢
**Estimated Time:** 15 min
**Dependencies:** 1.1, 1.3
**Description:** Create backend/database.py
- SQLAlchemy engine setup
- Session factory
- Base model class

### 2.2 Create Analysis model 🟡
**Estimated Time:** 30 min
**Dependencies:** 2.1
**Description:** Create backend/models/analysis.py
- Analysis table schema
- Relationships
- Helper methods

### 2.3 Create Video model 🟢
**Estimated Time:** 20 min
**Dependencies:** 2.1
**Description:** Create backend/models/video.py
- Video table schema
- Deduplication logic

### 2.4 Create Cluster model 🟢
**Estimated Time:** 20 min
**Dependencies:** 2.1, 2.2
**Description:** Create backend/models/cluster.py
- Cluster table schema
- Foreign key to Analysis

### 2.5 Initialize Alembic for migrations 🟢
**Estimated Time:** 15 min
**Dependencies:** 2.1-2.4
**Description:** Setup Alembic
- Initialize alembic
- Create initial migration
- Configure alembic.ini

### 2.6 Create initial database migration 🟡
**Estimated Time:** 20 min
**Dependencies:** 2.5
**Description:** Generate migration for all tables
- Run alembic revision --autogenerate
- Review generated migration
- Test migration

---

## Phase 3: Caching Layer (Depends on 1.2)

### 3.1 Create Redis connection module 🟢
**Estimated Time:** 10 min
**Dependencies:** 1.1, 1.2
**Description:** Create backend/cache.py
- Redis client setup
- Connection pool

### 3.2 Create metadata cache service 🟡
**Estimated Time:** 30 min
**Dependencies:** 3.1
**Description:** Create backend/services/metadata_cache.py
- Cache get/set methods
- Batch operations
- TTL management

### 3.3 Create quota manager service 🟡
**Estimated Time:** 40 min
**Dependencies:** 3.1
**Description:** Create backend/services/quota_manager.py
- Daily quota tracking
- Quota consumption
- Quota checking
- Auto-reset at midnight

---

## Phase 4: YouTube API Integration (Depends on Phase 3)

### 4.1 Create YouTube API client wrapper 🔴
**Estimated Time:** 90 min
**Dependencies:** 1.1, 3.2, 3.3
**Description:** Create backend/services/youtube_api.py
- API client initialization
- get_video_metadata method
- Batch request handling
- Error handling (quota, rate limit)
- Integration with quota manager

### 4.2 Update enrichment module to use YouTube API 🟡
**Estimated Time:** 45 min
**Dependencies:** 4.1
**Description:** Modify backend/modules/enrichment.py
- Remove placeholder implementation
- Use YouTubeAPIClient
- Check cache before API calls
- Handle API errors
- Cache results

### 4.3 Test YouTube API integration 🟡
**Estimated Time:** 30 min
**Dependencies:** 4.2
**Description:** Manual testing
- Test with real API key
- Verify caching works
- Verify quota tracking
- Test error scenarios

---

## Phase 5: Real Embeddings (Depends on Phase 4)

### 5.1 Update embedding module to load sentence-transformers 🟡
**Estimated Time:** 30 min
**Dependencies:** 1.1
**Description:** Modify backend/modules/embedding.py
- Load sentence-transformers model
- Model caching (singleton)
- Error handling for model loading

### 5.2 Generate real embeddings from metadata 🟡
**Estimated Time:** 40 min
**Dependencies:** 5.1, 4.2
**Description:** Update get_video_embeddings function
- Combine title + description + tags
- Batch encoding
- Progress tracking
- Test with real data

### 5.3 Update scoring with real metrics 🔴
**Estimated Time:** 60 min
**Dependencies:** 5.2
**Description:** Modify backend/modules/scoring.py
- Calculate demand from view counts
- Calculate competition from channel metrics
- Calculate opportunity score
- Remove random scores

---

## Phase 6: Celery Setup (Depends on 1.1, 1.2)

### 6.1 Create Celery app configuration 🟢
**Estimated Time:** 20 min
**Dependencies:** 1.1, 1.2
**Description:** Create backend/celery_app.py
- Celery instance
- Broker/backend URLs
- Configuration (serializer, task tracking)

### 6.2 Create simple test task 🟢
**Estimated Time:** 10 min
**Dependencies:** 6.1
**Description:** Create backend/tasks/__init__.py
- Simple add(x, y) task
- Test task execution

### 6.3 Add Celery worker to docker-compose 🟢
**Estimated Time:** 15 min
**Dependencies:** 6.1
**Description:** Update docker-compose.yml
- Celery worker service
- Command: celery worker
- Depends on Redis and backend

### 6.4 Add Flower monitoring (optional) 🟢
**Estimated Time:** 10 min
**Dependencies:** 6.3
**Description:** Update docker-compose.yml
- Flower service
- Expose port 5555
- Web UI for monitoring

---

## Phase 7: Async Job Processing (Depends on Phase 6 + Database)

### 7.1 Create analysis Celery task 🔴
**Estimated Time:** 90 min
**Dependencies:** 6.1, 2.1-2.4
**Description:** Create backend/tasks/analysis.py
- analyze_async task
- Progress tracking
- Error handling
- Result storage in database

### 7.2 Update /analyze endpoint to queue tasks 🟡
**Estimated Time:** 40 min
**Dependencies:** 7.1
**Description:** Modify backend/main.py
- Change from sync to async
- Queue Celery task
- Return job_id (HTTP 202)
- Create Analysis record in database

### 7.3 Create GET /jobs/{id} endpoint 🟡
**Estimated Time:** 30 min
**Dependencies:** 7.1
**Description:** Add to backend/main.py
- Get task status from Celery
- Return progress information
- Return result URL if complete

### 7.4 Create GET /jobs/{id}/results endpoint 🟢
**Estimated Time:** 20 min
**Dependencies:** 7.3
**Description:** Add to backend/main.py
- Get results from database
- Format response
- Handle not found errors

### 7.5 Add DELETE /jobs/{id} (cancel) endpoint 🟡
**Estimated Time:** 30 min
**Dependencies:** 7.3
**Description:** Add to backend/main.py
- Revoke Celery task
- Update database status
- Return confirmation

---

## Phase 8: Analysis History & Persistence

### 8.1 Create GET /analyses endpoint 🟡
**Estimated Time:** 30 min
**Dependencies:** 2.1-2.4
**Description:** Add to backend/main.py
- Query all analyses
- Filter by user (future)
- Pagination support
- Sort by date

### 8.2 Create GET /analyses/{id} endpoint 🟢
**Estimated Time:** 20 min
**Dependencies:** 2.1-2.4
**Description:** Add to backend/main.py
- Query specific analysis
- Include clusters
- Include videos
- Format response

### 8.3 Update pipeline to persist results 🟡
**Estimated Time:** 45 min
**Dependencies:** 7.1, 2.1-2.4
**Description:** Modify analysis task
- Save videos to database
- Save clusters to database
- Update analysis status
- Deduplicate videos

### 8.4 Create comparison utility 🔴
**Estimated Time:** 90 min
**Dependencies:** 8.2
**Description:** Create backend/utils/comparison.py
- Compare two analyses
- Identify new/retired topics
- Calculate growth rates
- Generate insights

### 8.5 Create GET /analyses/compare endpoint 🟡
**Estimated Time:** 40 min
**Dependencies:** 8.4
**Description:** Add to backend/main.py
- Parse query params (2 analysis IDs)
- Call comparison utility
- Format response

---

## Phase 9: Export Functionality

### 9.1 Create CSV export utility 🟡
**Estimated Time:** 30 min
**Dependencies:** 8.2
**Description:** Create backend/utils/export.py
- Generate CSV from analysis
- Include clusters and videos

### 9.2 Create JSON export utility 🟢
**Estimated Time:** 15 min
**Dependencies:** 8.2
**Description:** Add to backend/utils/export.py
- Generate JSON export
- Pretty formatting

### 9.3 Create PDF export utility 🔴
**Estimated Time:** 90 min
**Dependencies:** 8.2
**Description:** Add to backend/utils/export.py
- Generate PDF with charts
- Use ReportLab or WeasyPrint
- Include summary and clusters

### 9.4 Create GET /analyses/{id}/export endpoint 🟡
**Estimated Time:** 30 min
**Dependencies:** 9.1-9.3
**Description:** Add to backend/main.py
- Query param for format (csv/json/pdf)
- Call appropriate export utility
- Return file download

---

## Phase 10: Frontend Updates

### 10.1 Update frontend for async job submission 🟡
**Estimated Time:** 45 min
**Dependencies:** 7.2
**Description:** Modify frontend/app.py
- Submit file and get job_id
- Store job_id in session state

### 10.2 Add job status polling 🔴
**Estimated Time:** 60 min
**Dependencies:** 7.3, 10.1
**Description:** Modify frontend/app.py
- Poll GET /jobs/{id} every 2 seconds
- Display progress bar
- Update status messages

### 10.3 Add results retrieval 🟡
**Estimated Time:** 30 min
**Dependencies:** 7.4, 10.2
**Description:** Modify frontend/app.py
- Fetch results when complete
- Display results as before

### 10.4 Add analysis history page 🔴
**Estimated Time:** 90 min
**Dependencies:** 8.1
**Description:** Create new frontend page
- List all past analyses
- Show date, video count, status
- Link to view results

### 10.5 Add comparison view 🔴
**Estimated Time:** 120 min
**Dependencies:** 8.5, 10.4
**Description:** Create comparison UI
- Select two analyses
- Display comparison results
- Visualize growth/decline

### 10.6 Add export buttons 🟢
**Estimated Time:** 20 min
**Dependencies:** 9.4
**Description:** Add to results display
- CSV download button
- JSON download button
- PDF download button

---

## Phase 11: Testing & Refinement

### 11.1 Write unit tests for models 🟡
**Estimated Time:** 45 min
**Dependencies:** 2.1-2.4
**Description:** Create tests/test_models.py
- Test Analysis model
- Test Cluster model
- Test Video model

### 11.2 Write integration tests for API 🔴
**Estimated Time:** 90 min
**Dependencies:** All previous
**Description:** Create tests/test_api.py
- Test /analyze endpoint
- Test /jobs endpoints
- Test /analyses endpoints

### 11.3 Write tests for YouTube API client 🟡
**Estimated Time:** 45 min
**Dependencies:** 4.1
**Description:** Create tests/test_youtube_api.py
- Mock YouTube API
- Test quota management
- Test caching

### 11.4 Load testing with concurrent requests 🔴
**Estimated Time:** 60 min
**Dependencies:** All previous
**Description:** Performance testing
- Use locust or pytest-benchmark
- Test 10 concurrent analyses
- Measure response times

### 11.5 Documentation updates 🟡
**Estimated Time:** 30 min
**Dependencies:** All previous
**Description:** Update README.md
- New architecture
- Setup instructions
- API documentation

---

## Summary by Priority

### Critical Path (Must Do First)
1. Infrastructure setup (1.1-1.3) - 25 min
2. Redis connection (3.1) - 10 min
3. YouTube API client (4.1) - 90 min
4. Update enrichment (4.2) - 45 min
5. Real embeddings (5.1-5.2) - 70 min
6. Real scoring (5.3) - 60 min
**Total: ~5 hours** → App becomes functional

### High Priority (Async + Persistence)
7. Database setup (2.1-2.6) - 120 min
8. Celery setup (6.1-6.4) - 55 min
9. Async jobs (7.1-7.5) - 210 min
**Total: ~6.5 hours** → App becomes scalable

### Medium Priority (History + Export)
10. Analysis history (8.1-8.3) - 95 min
11. Export (9.1-9.4) - 165 min
**Total: ~4.3 hours** → Added features

### Lower Priority (Frontend + Polish)
12. Frontend updates (10.1-10.6) - 365 min
13. Testing (11.1-11.5) - 270 min
**Total: ~10.6 hours** → Complete system

---

## Grand Total
**Estimated Time: 26.4 hours (~3.3 developer days)**

## Next Task to Execute
**Task 1.1: Add All Dependencies to requirements.txt** (5 min)
