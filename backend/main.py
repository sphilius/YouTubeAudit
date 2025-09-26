from flask import Flask, request, jsonify
import structlog
import os
import tempfile
import json
from werkzeug.utils import secure_filename

# Import your existing analysis modules
from backend.modules import ingestion, enrichment, embedding, clustering, labeling, scoring

# --- Logging Setup ---
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
log = structlog.get_logger()

# --- Flask App ---
app = Flask(__name__)

# --- Configuration ---
# A simple, static token for demonstration purposes.
# In a real application, use a more robust authentication method.
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "a-secure-static-token")
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def run_analysis_pipeline(file_path: str, api_key: str):
    """
    Synchronously runs the entire analysis pipeline.
    """
    log.info("Pipeline started", file_path=file_path)

    try:
        # Step 1: Ingestion
        log.info("Ingesting data...")
        # The ingestion module needs to be adapted to handle the file path
        raw_data = ingestion.parse_takeout_file(file_path)
        video_ids = [item['contentDetails']['videoId'] for item in raw_data if 'videoId' in item.get('contentDetails', {})]
        log.info(f"Ingested {len(video_ids)} video IDs.")

        # Step 2: Enrichment
        log.info("Enriching video metadata...")
        metadata = enrichment.enrich_video_metadata(video_ids, api_key)
        log.info(f"Enriched metadata for {len(metadata)} videos.")

        # Step 3: Embedding
        log.info("Generating embeddings...")
        video_embeddings = embedding.get_video_embeddings(metadata)
        log.info("Embeddings generated.")

        # Step 4: Clustering
        log.info("Clustering videos...")
        # Let's make the number of clusters dynamic or configurable if needed
        num_clusters = min(10, len(video_ids) // 5) # Example logic
        if num_clusters < 2:
            num_clusters = 2
        clusters = clustering.cluster_videos(video_embeddings, num_clusters=num_clusters)
        log.info(f"Clustered videos into {num_clusters} topics.")

        # Step 5: Labeling
        log.info("Generating labels for clusters...")
        labeled_clusters = labeling.label_clusters_with_gpt(clusters, metadata, api_key)
        log.info("Labels generated.")

        # Step 6: Scoring
        log.info("Scoring clusters...")
        scored_results = scoring.score_clusters(labeled_clusters, metadata)
        log.info("Scoring complete.")

        log.info("Pipeline finished successfully")
        return scored_results

    except Exception as e:
        log.error("Pipeline failed", error=str(e), exc_info=True)
        # Re-raise the exception to be caught by the endpoint handler
        raise

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    The main analysis endpoint.
    Accepts file upload and an API key.
    """
    # 1. Authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing or malformed"}), 401

    token = auth_header.split(" ")[1]
    if token != API_BEARER_TOKEN:
        return jsonify({"error": "Invalid API key"}), 401

    # 2. File Handling
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 3. API Key for external services (like Google AI)
    api_key = request.form.get("api_key")
    if not api_key:
        return jsonify({"error": "API key for analysis is missing"}), 400

    if file:
        filename = secure_filename(file.filename)
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        file.save(file_path)
        log.info("File saved temporarily", path=file_path)

        try:
            # 4. Run Pipeline
            results = run_analysis_pipeline(file_path, api_key)
            return jsonify(results)
        except Exception as e:
            return jsonify({"error": "An error occurred during analysis", "details": str(e)}), 500
        finally:
            # 5. Cleanup
            log.info("Cleaning up temporary file", path=file_path)
            os.remove(file_path)
            os.rmdir(temp_dir)

    return jsonify({"error": "An unknown error occurred"}), 500


@app.route("/")
def health_check():
    """A simple health check endpoint."""
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)