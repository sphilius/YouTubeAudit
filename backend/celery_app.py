"""
Celery application configuration for YouTube Audit Engine.

This module initializes the Celery app for distributed task processing.
Tasks are queued to Redis and processed by worker processes.

Supports fakeredis for testing without Redis installation.
"""

from celery import Celery
from backend.config import get_config

# Load configuration
config = get_config()

# Helper function to convert fakeredis URLs to redis URLs for Celery
def normalize_redis_url(url: str) -> str:
    """
    Convert fakeredis:// URLs to redis:// for Celery compatibility.

    Args:
        url: Redis or fakeredis URL

    Returns:
        Normalized redis:// URL
    """
    if url.startswith('fakeredis://'):
        # Celery doesn't understand fakeredis://, so convert to redis://
        # The actual fakeredis usage is handled by backend.cache module
        return url.replace('fakeredis://', 'redis://')
    return url

# Normalize URLs for Celery
broker_url = normalize_redis_url(config.celery_broker_url)
backend_url = normalize_redis_url(config.celery_result_backend)

# Create Celery app instance
celery_app = Celery(
    'youtube_audit',
    broker=broker_url,
    backend=backend_url,
    include=['backend.tasks.analysis']  # Auto-discover task modules
)

# Celery Configuration
celery_app.conf.update(
    # Result Backend
    result_backend=config.celery_result_backend,
    result_expires=3600 * 24 * 7,  # Results expire after 7 days
    result_extended=True,  # Store additional task metadata

    # Task Configuration
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,

    # Task Execution
    task_track_started=True,  # Track when tasks start
    task_time_limit=3600 * 2,  # 2 hour hard limit
    task_soft_time_limit=3600 * 1.5,  # 1.5 hour soft limit
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Requeue if worker dies

    # Worker Configuration
    worker_prefetch_multiplier=1,  # Fetch one task at a time (fair distribution)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (prevent memory leaks)
    worker_disable_rate_limits=False,

    # Retry Configuration
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,  # Max 3 retries

    # Monitoring
    worker_send_task_events=True,  # Send task events for monitoring
    task_send_sent_event=True,  # Send event when task is sent

    # Broker Configuration
    broker_connection_retry_on_startup=True,  # Retry connection on startup
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # Result Backend Configuration
    result_backend_transport_options={
        'master_name': 'mymaster',
        'retry_on_timeout': True,
        'socket_keepalive': True,
    },

    # Beat Schedule (for periodic tasks - future use)
    beat_schedule={
        # Example periodic task (currently disabled)
        # 'cleanup-old-analyses': {
        #     'task': 'backend.tasks.maintenance.cleanup_old_analyses',
        #     'schedule': crontab(hour=3, minute=0),  # Run at 3 AM daily
        # },
    },
)


# Task routes (optional - for task prioritization)
celery_app.conf.task_routes = {
    'backend.tasks.analysis.*': {'queue': 'analysis'},
    'backend.tasks.export.*': {'queue': 'export'},
    'backend.tasks.maintenance.*': {'queue': 'maintenance'},
}


# Custom task base class (optional - for common task behavior)
class BaseTask(celery_app.Task):
    """Base task class with common functionality."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Handler called on task failure.

        Args:
            exc: Exception raised
            task_id: Task ID
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        from backend.utils.logging_config import get_logger
        logger = get_logger(__name__)

        logger.error(
            "Task failed",
            task_id=task_id,
            task_name=self.name,
            exception=str(exc),
            args=args,
            kwargs=kwargs
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Handler called on task retry.

        Args:
            exc: Exception that caused retry
            task_id: Task ID
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        from backend.utils.logging_config import get_logger
        logger = get_logger(__name__)

        logger.warning(
            "Task retry",
            task_id=task_id,
            task_name=self.name,
            exception=str(exc),
            retry_count=self.request.retries
        )

    def on_success(self, retval, task_id, args, kwargs):
        """
        Handler called on task success.

        Args:
            retval: Return value of task
            task_id: Task ID
            args: Task positional arguments
            kwargs: Task keyword arguments
        """
        from backend.utils.logging_config import get_logger
        logger = get_logger(__name__)

        logger.info(
            "Task completed successfully",
            task_id=task_id,
            task_name=self.name
        )


# Set base task class
celery_app.Task = BaseTask


# Celery signals (optional - for monitoring)
from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    worker_ready,
    worker_shutdown
)


@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    """Signal handler for worker ready event."""
    from backend.utils.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Celery worker is ready", worker=sender)


@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs):
    """Signal handler for worker shutdown event."""
    from backend.utils.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Celery worker is shutting down", worker=sender)


@task_prerun.connect
def on_task_prerun(task_id=None, task=None, **kwargs):
    """Signal handler for task pre-run event."""
    from backend.utils.logging_config import get_logger, bind_context
    logger = get_logger(__name__)

    # Bind task_id to logging context
    bind_context(task_id=task_id)

    logger.debug(
        "Task starting",
        task_id=task_id,
        task_name=task.name
    )


@task_postrun.connect
def on_task_postrun(task_id=None, task=None, state=None, **kwargs):
    """Signal handler for task post-run event."""
    from backend.utils.logging_config import get_logger
    logger = get_logger(__name__)

    logger.debug(
        "Task finished",
        task_id=task_id,
        task_name=task.name,
        state=state
    )


@task_failure.connect
def on_task_failure(task_id=None, exception=None, **kwargs):
    """Signal handler for task failure event."""
    from backend.utils.logging_config import get_logger
    logger = get_logger(__name__)

    logger.error(
        "Task failed (signal)",
        task_id=task_id,
        exception=str(exception)
    )


if __name__ == '__main__':
    # For testing: python -m backend.celery_app worker --loglevel=info
    celery_app.start()
