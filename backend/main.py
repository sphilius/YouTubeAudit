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

# Import analysis modules
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
    Main analysis endpoint.

    Accepts file upload and API key to run the analysis pipeline.

    Request:
        - Headers: Authorization: Bearer <token>
        - Form data:
            - file: YouTube Takeout file (.zip or .json)
            - api_key: Google API key

    Returns:
        JSON response with analysis results

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

    # 4. Save File Securely
    filename = secure_filename(file.filename)
    filename = sanitize_filename(filename)

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, filename)

    file.save(file_path)
    log.info("File saved temporarily", path=file_path, size_bytes=os.path.getsize(file_path))

    try:
        # Validate saved file
        validate_saved_file(file_path)

        # 5. Run Analysis Pipeline
        log.info("Starting analysis pipeline")
        results = run_analysis_pipeline(file_path, api_key)

        log.info("Analysis request completed successfully")
        return jsonify(results)

    finally:
        # 6. Cleanup
        if config.cleanup_temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    log.debug("Temporary file removed", path=file_path)

                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
                    log.debug("Temporary directory removed", path=temp_dir)
            except Exception as e:
                log.warning("Failed to cleanup temporary files",
                           error=str(e),
                           file_path=file_path)


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