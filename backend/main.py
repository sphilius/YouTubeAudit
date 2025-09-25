import logging
import structlog
import uuid
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from celery.result import AsyncResult

from backend.config import settings
from backend.tasks import run_analysis_pipeline, celery

# --- Logging Setup ---
# Configure standard logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
log = structlog.get_logger()


# --- Authentication ---
API_KEY_HEADER = APIKeyHeader(name="Authorization", auto_error=False)

def get_api_key(api_key_header: str = Security(API_KEY_HEADER)):
    """
    Dependency to validate the API key from the Authorization header.
    Expects "Bearer <token>".
    """
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    try:
        scheme, token = api_key_header.split()
        if scheme.lower() != "bearer" or token != settings.API_BEARER_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or malformed API key",
            )
        return token
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed authorization header",
        )

# --- FastAPI App ---
app = FastAPI(
    title="YouTube Topic Audit Engine",
    description="API for running topic analysis on YouTube data.",
    version="0.1.0",
)

# In-memory "database" for storing job task IDs (for prototype)
jobs = {}

@app.post("/run-analysis", status_code=status.HTTP_202_ACCEPTED)
def start_analysis(api_key: str = Depends(get_api_key)):
    """
    Starts an asynchronous analysis pipeline.
    """
    job_id = str(uuid.uuid4())
    log.info("Starting analysis", job_id=job_id)

    # Start the Celery task
    task = run_analysis_pipeline.delay(job_id)

    jobs[job_id] = {"task_id": task.id}

    return {"job_id": job_id, "status": "Analysis started"}


@app.get("/status/{job_id}")
def get_job_status(job_id: str, api_key: str = Depends(get_api_key)):
    """
    Gets the status of a running analysis job.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    task_id = job["task_id"]
    task_result = AsyncResult(task_id, app=celery)

    status = task_result.state

    log.info("Fetching status for job", job_id=job_id, task_id=task_id, status=status)
    return {"job_id": job_id, "status": status}


@app.get("/results/{job_id}")
def get_job_results(job_id: str, api_key: str = Depends(get_api_key)):
    """
    Gets the results of a completed analysis job.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    task_id = job["task_id"]
    task_result = AsyncResult(task_id, app=celery)

    if task_result.state != "SUCCESS":
        return {"job_id": job_id, "status": task_result.state, "message": "Results are not ready yet."}

    log.info("Fetching results for job", job_id=job_id, task_id=task_id)
    return {"job_id": job_id, "status": task_result.state, "results": task_result.result}


@app.get("/")
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok"}