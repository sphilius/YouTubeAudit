"""
Celery tasks for YouTube Audit Engine.

This package contains all Celery tasks for async processing:
- Analysis tasks (video analysis, clustering)
- Export tasks (CSV, PDF, JSON generation)
- Maintenance tasks (cleanup, optimization)
"""

from backend.celery_app import celery_app
from backend.utils.logging_config import get_logger
import time

logger = get_logger(__name__)


@celery_app.task(name='tasks.add', bind=True)
def add(self, x: int, y: int) -> int:
    """
    Simple test task that adds two numbers.

    This task is used to verify that Celery is working correctly.

    Args:
        x: First number
        y: Second number

    Returns:
        Sum of x and y

    Example:
        >>> result = add.delay(4, 5)
        >>> result.get()
        9
    """
    logger.info(
        "Executing add task",
        task_id=self.request.id,
        x=x,
        y=y
    )

    # Simulate some work
    time.sleep(1)

    result = x + y

    logger.info(
        "Add task completed",
        task_id=self.request.id,
        result=result
    )

    return result


@celery_app.task(name='tasks.multiply', bind=True)
def multiply(self, x: int, y: int) -> int:
    """
    Simple test task that multiplies two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        Product of x and y
    """
    logger.info(
        "Executing multiply task",
        task_id=self.request.id,
        x=x,
        y=y
    )

    time.sleep(0.5)
    result = x * y

    logger.info(
        "Multiply task completed",
        task_id=self.request.id,
        result=result
    )

    return result


@celery_app.task(name='tasks.sleep', bind=True)
def sleep_task(self, seconds: int = 5) -> str:
    """
    Test task that sleeps for a specified duration.

    Useful for testing long-running tasks and progress tracking.

    Args:
        seconds: Number of seconds to sleep

    Returns:
        Completion message
    """
    logger.info(
        "Starting sleep task",
        task_id=self.request.id,
        duration=seconds
    )

    for i in range(seconds):
        time.sleep(1)
        # Update task progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': i + 1,
                'total': seconds,
                'status': f'Sleeping... {i + 1}/{seconds}'
            }
        )

    logger.info(
        "Sleep task completed",
        task_id=self.request.id
    )

    return f"Slept for {seconds} seconds"


@celery_app.task(name='tasks.failing_task', bind=True, max_retries=3)
def failing_task(self, should_fail: bool = True) -> str:
    """
    Test task that can be configured to fail.

    Useful for testing retry logic and error handling.

    Args:
        should_fail: Whether the task should fail

    Returns:
        Success message

    Raises:
        Exception: If should_fail is True
    """
    logger.info(
        "Executing failing task",
        task_id=self.request.id,
        should_fail=should_fail
    )

    if should_fail:
        logger.error(
            "Task intentionally failing",
            task_id=self.request.id
        )
        raise Exception("This task was configured to fail")

    return "Task succeeded"


# Example of chaining tasks
@celery_app.task(name='tasks.chain_example')
def chain_example() -> dict:
    """
    Example task demonstrating task chaining.

    Returns:
        Result dictionary with chain outputs
    """
    from celery import chain

    # Create a chain of tasks
    workflow = chain(
        add.s(2, 2),          # Returns 4
        multiply.s(3),        # Receives 4, returns 12
        add.s(8)              # Receives 12, returns 20
    )

    result = workflow.apply_async()

    return {
        'chain_id': result.id,
        'status': 'Chain started'
    }


# Example of grouping tasks
@celery_app.task(name='tasks.group_example')
def group_example() -> dict:
    """
    Example task demonstrating parallel task execution.

    Returns:
        Result dictionary with group outputs
    """
    from celery import group

    # Create a group of parallel tasks
    job = group([
        add.s(2, 2),
        multiply.s(4, 5),
        add.s(10, 15)
    ])

    result = job.apply_async()

    return {
        'group_id': result.id,
        'status': 'Group started',
        'tasks': len(result.results)
    }


# Health check task
@celery_app.task(name='tasks.health_check')
def health_check() -> dict:
    """
    Health check task to verify Celery is working.

    Returns:
        Health status dictionary
    """
    import datetime
    from backend.config import get_config

    config = get_config()

    return {
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'broker': config.celery_broker_url.split('@')[-1],  # Hide credentials
        'backend': config.celery_result_backend.split('@')[-1],
        'worker': 'running'
    }
