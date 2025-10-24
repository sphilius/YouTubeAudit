"""
YouTube Topic Audit Engine - Main Flask Application

This is the main entry point for the backend Flask application that provides
the analysis API for processing YouTube watch history.
"""

from flask import Flask, request, jsonify
import os
import tempfile
from werkzeug.utils import secure_filename
from typing import Dict, Any
from datetime import datetime

# Import configuration and logging
from backend.config import get_config, validate_config
from backend.utils.logging_config import configure_logging, get_logger

# Import middleware
from backend.middleware.correlation import CorrelationMiddleware
from backend.middleware.error_handler import ErrorHandlerMiddleware

# Import validators
from backend.validators import (
    validate_file_upload,
    validate_saved_file,
    validate_google_api_key,
    validate_bearer_token,
    sanitize_filename
)

# Import exceptions
from backend.exceptions import YouTubeAuditError, ValidationError

# Import database and models
from backend.database import get_session
from backend.models.analysis import Analysis, AnalysisStatus
from backend.models.video import Video
from backend.models.cluster import Cluster

# Import Celery tasks
from backend.tasks.analysis import analyze_watch_history

# Import analysis modules (for legacy sync endpoint if needed)
from backend.modules import ingestion, enrichment, embedding, clustering, scoring

# ============================================================================
# Application Initialization
# ============================================================================

# Load and validate configuration
config = get_config()
is_valid, config_errors = validate_config()
if not is_valid:
    print("Configuration errors found:")
    for error in config_errors:
        print(f"  - {error}")
    print("Proceeding with warnings...")

# Configure logging
configure_logging(
    log_level=config.log_level,
    log_format=config.log_format,
    log_file=config.log_file,
    enable_sanitization=config.sanitize_logs,
    development_mode=config.is_development()
)

log = get_logger(__name__)
log.info(
    "Starting YouTube Audit Engine",
    environment=config.environment,
    debug=config.debug,
    log_level=config.log_level
)

# Create Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = config.secret_key
app.config['UPLOAD_FOLDER'] = str(config.upload_folder)
app.config['MAX_CONTENT_LENGTH'] = config.max_upload_size_bytes

# Initialize middleware
CorrelationMiddleware(app)
ErrorHandlerMiddleware(app)

log.info("Flask application initialized", upload_folder=config.upload_folder)


# ============================================================================
# Pipeline Functions
# ============================================================================

def run_analysis_pipeline(file_path: str, api_key: str) -> Dict[str, Any]:
    """
    Synchronously runs the entire analysis pipeline.

    Args:
        file_path: Path to the uploaded Takeout file
        api_key: Google API key for YouTube API

    Returns:
        Dictionary containing analysis results

    Raises:
        YouTubeAuditError: If any step of the pipeline fails
    """
    log.info("Analysis pipeline started", file_path=file_path)

    try:
        # Step 1: Ingestion
        log.info("Step 1/5: Ingesting data")
        raw_data = ingestion.parse_takeout_file(file_path)

        # Extract video IDs from the raw data
        video_ids = []
        for item in raw_data:
            content_details = item.get('contentDetails', {})
            if 'videoId' in content_details:
                video_ids.append(content_details['videoId'])

        log.info("Ingestion complete", video_count=len(video_ids))

        if len(video_ids) == 0:
            raise ValidationError(
                message="No video IDs found in the watch history",
                user_message="Your watch history appears to be empty or in an unexpected format."
            )

        # Step 2: Enrichment
        log.info("Step 2/5: Enriching video metadata", video_count=len(video_ids))
        # Note: api_key is passed but enrichment module is currently a placeholder
        metadata = enrichment.enrich_video_metadata(video_ids)
        log.info("Enrichment complete", metadata_count=len(metadata))

        # Step 3: Embedding
        log.info("Step 3/5: Generating embeddings", video_count=len(metadata))
        video_embeddings = embedding.get_video_embeddings(metadata)
        log.info("Embedding generation complete", embeddings_shape=video_embeddings.shape)

        # Step 4: Clustering
        log.info("Step 4/5: Clustering videos")

        # Determine optimal number of clusters
        num_clusters = min(
            config.max_clusters,
            max(config.min_clusters, len(video_ids) // 5)
        )
        num_clusters = max(num_clusters, config.min_clusters)

        log.info("Calculated cluster count", num_clusters=num_clusters, video_count=len(video_ids))

        clusters = clustering.cluster_videos(video_embeddings, num_clusters=num_clusters)
        log.info("Clustering complete", cluster_count=len(clusters))

        # Step 5: Scoring
        log.info("Step 5/5: Scoring clusters", cluster_count=len(clusters))
        scored_results = scoring.score_clusters(clusters, metadata)
        log.info("Scoring complete")

        # Build final results
        results = {
            "status": "success",
            "summary": {
                "total_videos": len(video_ids),
                "total_clusters": len(clusters),
                "cluster_distribution": {k: len(v) for k, v in clusters.items()}
            },
            "clusters": scored_results
        }

        log.info("Analysis pipeline completed successfully",
                 total_videos=len(video_ids),
                 total_clusters=len(clusters))

        return results

    except YouTubeAuditError as e:
        log.error("Pipeline failed with known error",
                 error_type=type(e).__name__,
                 error_code=e.error_code,
                 message=e.message)
        raise

    except Exception as e:
        log.error("Pipeline failed with unexpected error",
                 error_type=type(e).__name__,
                 error=str(e),
                 exc_info=True)
        raise


# ============================================================================
# API Endpoints
# ============================================================================

@app.route("/", methods=["GET"])
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON response with application status
    """
    return jsonify({
        "status": "ok",
        "service": "youtube-audit-engine",
        "version": "1.0.0",
        "environment": config.environment
    })


@app.route("/health", methods=["GET"])
def detailed_health():
    """
    Detailed health check with component status.

    Returns:
        JSON response with detailed health information
    """
    health_status = {
        "status": "healthy",
        "components": {
            "api": "ok",
            "configuration": "ok" if is_valid else "degraded",
            "upload_folder": "ok" if os.access(config.upload_folder, os.W_OK) else "error"
        },
        "configuration_errors": config_errors if not is_valid else []
    }

    status_code = 200 if health_status["status"] == "healthy" else 503

    return jsonify(health_status), status_code


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Async analysis endpoint - queues analysis job and returns immediately.

    Accepts file upload and API key to run the analysis pipeline asynchronously.

    Request:
        - Headers: Authorization: Bearer <token>
        - Form data:
            - file: YouTube Takeout file (.zip or .json)
            - api_key: Google API key (optional if set in config)
            - num_clusters: Number of clusters (optional, default 10)

    Returns:
        HTTP 202 Accepted with:
        - task_id: Celery task ID for tracking
        - analysis_id: Database analysis ID
        - status_url: URL to check job status
        - estimated_time: Estimated completion time

    Raises:
        Various YouTubeAuditError exceptions for different failure cases
    """
    log.info("Received analysis request",
             method=request.method,
             content_type=request.content_type)

    # 1. Authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        log.warning("Missing or malformed authorization header")
        raise ValidationError(
            message="Authorization header missing or malformed",
            error_code="AUTH_001",
            user_message="Authentication required. Please provide a valid Bearer token."
        )

    token = auth_header.split(" ")[1]
    validate_bearer_token(token, config.api_bearer_token)
    log.debug("Authentication successful")

    # 2. File Upload Validation
    if 'file' not in request.files:
        log.error("No file in request")
        raise ValidationError(
            message="No file part in the request",
            user_message="Please upload a file."
        )

    file = request.files['file']
    validate_file_upload(file)
    log.info("File upload validated", filename=file.filename)

    # 3. API Key Validation
    api_key = request.form.get("api_key")
    if api_key:
        api_key = validate_google_api_key(api_key)
        log.debug("Google API key validated")
    else:
        # API key is optional if config has one
        if config.google_api_key:
            api_key = config.google_api_key
            log.debug("Using API key from configuration")
        else:
            raise ValidationError(
                message="No API key provided",
                user_message="Please provide a Google API key for video metadata enrichment."
            )

    # 4. Get optional parameters
    num_clusters = request.form.get("num_clusters", 10, type=int)

    # 5. Save File Securely (don't cleanup yet - task will need it)
    filename = secure_filename(file.filename)
    filename = sanitize_filename(filename)

    # Use uploads directory instead of temp
    uploads_dir = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    file_path = os.path.join(uploads_dir, f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}")
    file.save(file_path)
    log.info("File saved", path=file_path, size_bytes=os.path.getsize(file_path))

    # Validate saved file
    validate_saved_file(file_path)

    # 6. Create Analysis database record
    session = get_session()
    try:
        analysis = Analysis(
            task_id="pending",  # Will update after task creation
            status=AnalysisStatus.PENDING,
            created_at=datetime.utcnow()
        )
        session.add(analysis)
        session.commit()
        analysis_id = analysis.id

        log.info("Analysis record created", analysis_id=analysis_id)

        # 7. Queue Celery task
        task = analyze_watch_history.apply_async(
            args=[file_path, analysis_id],
            kwargs={'api_key': api_key, 'num_clusters': num_clusters}
        )

        # Update analysis record with task_id
        analysis.task_id = task.id
        session.commit()

        log.info(
            "Analysis task queued",
            task_id=task.id,
            analysis_id=analysis_id,
            file_path=file_path
        )

        # 8. Return response immediately
        return jsonify({
            'status': 'accepted',
            'message': 'Analysis job queued successfully',
            'task_id': task.id,
            'analysis_id': analysis_id,
            'status_url': f'/jobs/{task.id}',
            'results_url': f'/jobs/{task.id}/results',
            'estimated_time_minutes': 5,  # Rough estimate
            'created_at': datetime.utcnow().isoformat()
        }), 202

    except Exception as e:
        session.rollback()
        log.error("Failed to queue analysis", error=str(e))
        raise
    finally:
        session.close()


@app.route("/jobs/<task_id>", methods=["GET"])
@app.route("/status/<task_id>", methods=["GET"])
def get_job_status(task_id):
    """
    Get status of an analysis job.

    Args:
        task_id: Celery task ID

    Returns:
        JSON response with job status and progress
    """
    from celery.result import AsyncResult

    log.debug("Job status request", task_id=task_id)

    # Get task result
    task = AsyncResult(task_id)

    # Get analysis from database
    session = get_session()
    try:
        analysis = session.query(Analysis).filter(Analysis.task_id == task_id).first()

        if not analysis:
            log.warning("Analysis not found for task", task_id=task_id)
            return jsonify({
                'task_id': task_id,
                'state': task.state,
                'status': 'unknown',
                'message': 'Analysis record not found'
            }), 404

        response = {
            'task_id': task_id,
            'analysis_id': analysis.id,
            'state': task.state,
            'status': analysis.status.value if hasattr(analysis.status, 'value') else str(analysis.status),
            'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
            'started_at': analysis.started_at.isoformat() if analysis.started_at else None,
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
        }

        if task.state == 'PENDING':
            response['message'] = 'Job is waiting in queue'
            response['progress'] = 0

        elif task.state == 'PROGRESS':
            # Get progress info
            info = task.info or {}
            response['message'] = info.get('status', 'Processing...')
            response['progress'] = info.get('percent', 0)
            response['current'] = info.get('current', 0)
            response['total'] = info.get('total', 100)

        elif task.state == 'SUCCESS':
            response['message'] = 'Analysis complete'
            response['progress'] = 100
            response['result'] = task.result
            response['results_url'] = f'/jobs/{task_id}/results'

        elif task.state == 'FAILURE':
            response['message'] = 'Analysis failed'
            response['error'] = str(task.info) if task.info else 'Unknown error'
            response['error_message'] = analysis.error_message

        elif task.state == 'RETRY':
            response['message'] = 'Job is being retried'
            response['retry_count'] = task.info.get('retry_count', 0) if task.info else 0

        elif task.state == 'REVOKED':
            response['message'] = 'Job was cancelled'

        else:
            response['message'] = f'Job state: {task.state}'

        # Add statistics if available
        if analysis.total_videos > 0:
            response['statistics'] = {
                'total_videos': analysis.total_videos,
                'processed_videos': analysis.processed_videos,
                'failed_videos': analysis.failed_videos,
                'unique_channels': analysis.unique_channels,
                'num_clusters': analysis.num_clusters
            }

        return jsonify(response), 200

    finally:
        session.close()


@app.route("/jobs/<task_id>/results", methods=["GET"])
def get_job_results(task_id):
    """
    Get results of a completed analysis job.

    Args:
        task_id: Celery task ID

    Returns:
        JSON response with full analysis results
    """
    from celery.result import AsyncResult

    log.debug("Job results request", task_id=task_id)

    # Get task result
    task = AsyncResult(task_id)

    if task.state != 'SUCCESS':
        return jsonify({
            'error': 'Results not available',
            'message': f'Job is in state: {task.state}',
            'status_url': f'/jobs/{task_id}'
        }), 400

    # Get analysis from database with all related data
    session = get_session()
    try:
        analysis = session.query(Analysis).filter(Analysis.task_id == task_id).first()

        if not analysis:
            return jsonify({
                'error': 'Analysis not found',
                'task_id': task_id
            }), 404

        # Build response with full results
        response = {
            'analysis_id': analysis.id,
            'task_id': task_id,
            'status': 'completed',
            'created_at': analysis.created_at.isoformat(),
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
            'duration_seconds': analysis.duration_seconds,
            'summary': {
                'total_videos': analysis.total_videos,
                'processed_videos': analysis.processed_videos,
                'failed_videos': analysis.failed_videos,
                'unique_channels': analysis.unique_channels,
                'num_clusters': analysis.num_clusters,
                'total_watch_time_hours': analysis.total_watch_time_hours,
                'date_range': {
                    'start': analysis.date_range_start.isoformat() if analysis.date_range_start else None,
                    'end': analysis.date_range_end.isoformat() if analysis.date_range_end else None
                },
                'quota_used': analysis.quota_used,
                'embedding_model': analysis.embedding_model,
                'clustering_algorithm': analysis.clustering_algorithm
            }
        }

        # Get clusters
        clusters = session.query(Cluster).filter(Cluster.analysis_id == analysis.id).all()
        response['clusters'] = [cluster.to_dict() for cluster in clusters]

        # Get top channels (aggregate from videos)
        from sqlalchemy import func
        top_channels = session.query(
            Video.channel_name,
            func.count(Video.id).label('video_count')
        ).filter(
            Video.analysis_id == analysis.id,
            Video.channel_name.isnot(None)
        ).group_by(
            Video.channel_name
        ).order_by(
            func.count(Video.id).desc()
        ).limit(20).all()

        response['top_channels'] = [
            {'channel_name': name, 'video_count': count}
            for name, count in top_channels
        ]

        # Optionally include sample videos per cluster
        include_videos = request.args.get('include_videos', 'false').lower() == 'true'
        if include_videos:
            response['clusters_with_videos'] = []
            for cluster in clusters:
                cluster_videos = session.query(Video).filter(
                    Video.cluster_id == cluster.id
                ).limit(10).all()

                response['clusters_with_videos'].append({
                    'cluster': cluster.to_dict(),
                    'sample_videos': [v.to_dict() for v in cluster_videos]
                })

        return jsonify(response), 200

    finally:
        session.close()


@app.route("/jobs/<task_id>", methods=["DELETE"])
def cancel_job(task_id):
    """
    Cancel a running analysis job.

    Args:
        task_id: Celery task ID

    Returns:
        JSON response confirming cancellation
    """
    from celery.result import AsyncResult
    from backend.celery_app import celery_app

    log.info("Job cancellation request", task_id=task_id)

    # Get task
    task = AsyncResult(task_id)

    if task.state in ['SUCCESS', 'FAILURE']:
        return jsonify({
            'error': 'Cannot cancel completed job',
            'task_id': task_id,
            'state': task.state
        }), 400

    # Revoke task
    celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')

    # Update analysis record
    session = get_session()
    try:
        analysis = session.query(Analysis).filter(Analysis.task_id == task_id).first()
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = "Job cancelled by user"
            analysis.completed_at = datetime.utcnow()
            session.commit()

        log.info("Job cancelled", task_id=task_id)

        return jsonify({
            'message': 'Job cancelled successfully',
            'task_id': task_id,
            'analysis_id': analysis.id if analysis else None,
            'cancelled_at': datetime.utcnow().isoformat()
        }), 200

    finally:
        session.close()


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    log.info(
        "Starting Flask development server",
        host=config.host,
        port=config.port,
        debug=config.debug
    )

    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug
    )