# Celery Tasks

This directory contains all Celery tasks for asynchronous processing in the YouTube Audit Engine.

## Task Organization

- `__init__.py` - Simple test tasks for verification
- `analysis.py` - Main analysis tasks (video processing, clustering)
- `export.py` - Export tasks (CSV, PDF, JSON generation)
- `maintenance.py` - Maintenance tasks (cleanup, optimization)

## Running Workers

### Using Docker Compose (Recommended)

```bash
# Start all services including Celery workers
docker-compose up

# Start only worker services
docker-compose up celery_worker celery_beat
```

### Local Development

```bash
# Set environment variables
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Start worker
celery -A backend.celery_app worker --loglevel=info

# Start beat scheduler (for periodic tasks)
celery -A backend.celery_app beat --loglevel=info

# Start both worker and beat
celery -A backend.celery_app worker --beat --loglevel=info
```

## Monitoring with Flower

Flower provides a web-based UI for monitoring Celery workers and tasks.

### Access Flower

- **URL:** http://localhost:5555
- **Features:**
  - View active workers
  - Monitor task progress
  - View task history
  - Inspect task results
  - Revoke running tasks

### Start Flower

```bash
# Using Docker Compose
docker-compose up flower

# Local development
celery -A backend.celery_app flower --port=5555
```

## Testing Tasks

### Test Simple Tasks

```python
from backend.tasks import add, multiply, sleep_task

# Execute task synchronously
result = add(4, 5)
print(f"Result: {result}")  # 9

# Execute task asynchronously
async_result = add.delay(10, 20)
print(f"Task ID: {async_result.id}")
print(f"Status: {async_result.status}")
print(f"Result: {async_result.get()}")  # Blocks until complete

# Execute with countdown (delay execution)
async_result = multiply.apply_async((5, 3), countdown=10)

# Execute at specific time
from datetime import datetime, timedelta
eta = datetime.utcnow() + timedelta(minutes=5)
async_result = sleep_task.apply_async((30,), eta=eta)
```

### Test Progress Tracking

```python
from backend.tasks import sleep_task

# Start long-running task
result = sleep_task.delay(10)

# Poll for progress
while not result.ready():
    if result.state == 'PROGRESS':
        info = result.info
        print(f"Progress: {info['current']}/{info['total']} - {info['status']}")
    time.sleep(1)

print(f"Complete! Result: {result.get()}")
```

### Test Task Chaining

```python
from celery import chain
from backend.tasks import add, multiply

# Chain tasks together
workflow = chain(
    add.s(2, 2),      # Returns 4
    multiply.s(3),    # Receives 4, returns 12
    add.s(8)          # Receives 12, returns 20
)

result = workflow.apply_async()
print(f"Chain result: {result.get()}")  # 20
```

### Test Parallel Execution

```python
from celery import group
from backend.tasks import add, multiply

# Execute tasks in parallel
job = group([
    add.s(2, 2),
    multiply.s(4, 5),
    add.s(10, 15)
])

result = job.apply_async()
results = result.get()
print(f"Group results: {results}")  # [4, 20, 25]
```

## Task Status States

- `PENDING` - Task is waiting to be executed
- `STARTED` - Task has been started
- `PROGRESS` - Task is in progress (custom state)
- `SUCCESS` - Task completed successfully
- `FAILURE` - Task failed with an error
- `RETRY` - Task is being retried
- `REVOKED` - Task was cancelled

## Configuration

Task configuration is defined in `backend/celery_app.py`:

- **Time limits:** 2 hour hard limit, 1.5 hour soft limit
- **Retries:** Max 3 retries with 60 second delay
- **Result expiration:** 7 days
- **Worker concurrency:** Configured per worker
- **Task routing:** Tasks routed to specific queues

## Best Practices

1. **Keep tasks idempotent** - Tasks should produce the same result when run multiple times
2. **Don't pass large objects** - Pass IDs and fetch from database
3. **Set time limits** - Prevent tasks from running forever
4. **Handle exceptions** - Use try/except and log errors
5. **Update progress** - Use `self.update_state()` for long tasks
6. **Use retries wisely** - Retry transient failures, not permanent errors
7. **Monitor workers** - Use Flower to track performance

## Debugging

### Check Worker Status

```bash
# List active workers
celery -A backend.celery_app inspect active

# List scheduled tasks
celery -A backend.celery_app inspect scheduled

# List reserved tasks
celery -A backend.celery_app inspect reserved
```

### View Task Results

```bash
# Get result by task ID
celery -A backend.celery_app result <task-id>
```

### Purge All Tasks

```bash
# Clear all pending tasks (BE CAREFUL!)
celery -A backend.celery_app purge
```

### Revoke Task

```python
from backend.celery_app import celery_app

# Revoke specific task
celery_app.control.revoke('task-id', terminate=True)
```

## Troubleshooting

### Worker Not Starting

1. Check Redis is running: `redis-cli ping`
2. Check broker URL in config: `echo $CELERY_BROKER_URL`
3. Check worker logs: `docker-compose logs celery_worker`

### Tasks Not Executing

1. Verify worker is registered: `celery -A backend.celery_app inspect active_queues`
2. Check task is imported: `celery -A backend.celery_app inspect registered`
3. Monitor in Flower: http://localhost:5555

### Tasks Failing

1. Check worker logs for errors
2. View exception in Flower
3. Test task directly in Python shell
4. Check database/Redis connectivity

## Production Considerations

1. **Scale workers** - Run multiple worker instances
2. **Use dedicated queues** - Separate high/low priority tasks
3. **Monitor resources** - Track CPU, memory, queue length
4. **Set up alerts** - Alert on failed tasks or slow queues
5. **Configure autoscaling** - Scale workers based on load
6. **Use result backend cleanup** - Regularly clean old results

## Next Steps

1. Implement `backend/tasks/analysis.py` for video analysis
2. Implement `backend/tasks/export.py` for exports
3. Update endpoints to use async tasks
4. Add progress tracking to frontend
