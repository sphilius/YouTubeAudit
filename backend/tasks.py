import os
import time
import structlog
from celery import Celery

from backend.modules import ingestion, enrichment, embedding, clustering, scoring

# --- Celery Setup ---
celery = Celery(
    'tasks',
    broker=os.environ.get('CELERY_BROKER_URL'),
    backend=os.environ.get('CELERY_RESULT_BACKEND')
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# --- Logging ---
log = structlog.get_logger()


@celery.task(bind=True)
def run_analysis_pipeline(self, job_id: str):
    """
    The main analysis pipeline task.
    This simulates the multi-step process of a real analysis job.
    """
    log.info("Pipeline started", job_id=job_id)

    # In a real app, we would update the job status in a persistent database.
    # For the prototype, we'll just log it.

    try:
        # Step 1: Ingestion (Placeholder)
        self.update_state(state='INGESTING', meta={'job_id': job_id})
        log.info("Ingesting data...", job_id=job_id)
        raw_data = ingestion.parse_takeout_file("dummy_path.zip") # Placeholder
        time.sleep(2) # Simulate work

        # Step 2: Enrichment (Placeholder)
        self.update_state(state='ENRICHING', meta={'job_id': job_id})
        log.info("Enriching video metadata...", job_id=job_id)
        video_ids = ["video1", "video2", "video3", "video4", "video5", "video6", "video7", "video8", "video9", "video10"]
        metadata = enrichment.enrich_video_metadata(video_ids)
        time.sleep(2)

        # Step 3: Embedding (Placeholder)
        self.update_state(state='EMBEDDING', meta={'job_id': job_id})
        log.info("Generating embeddings...", job_id=job_id)
        video_embeddings = embedding.get_video_embeddings(metadata)
        time.sleep(3)

        # Step 4: Clustering
        self.update_state(state='CLUSTERING', meta={'job_id': job_id})
        log.info("Clustering videos...", job_id=job_id)
        clusters = clustering.cluster_videos(video_embeddings, num_clusters=3)
        time.sleep(2)

        # Step 5: Scoring
        self.update_state(state='SCORING', meta={'job_id': job_id})
        log.info("Scoring clusters...", job_id=job_id)
        scored_results = scoring.score_clusters(clusters, metadata)
        time.sleep(1)

        log.info("Pipeline finished successfully", job_id=job_id)

        # In a real app, we would store the final results in our database.
        # For the prototype, we can return it, and the main app can update its in-memory store.
        # Note: Celery's result backend is used to store this return value.
        return {'status': 'SUCCESS', 'result': scored_results}

    except Exception as e:
        log.error("Pipeline failed", job_id=job_id, error=str(e))
        self.update_state(state='FAILURE', meta={'job_id': job_id, 'error': str(e)})
        # It's good practice to re-raise the exception if you want Celery to record it as a failure
        raise e