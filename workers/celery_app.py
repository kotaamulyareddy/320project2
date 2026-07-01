"""
Celery Application Configuration.

Central Celery app setup with Redis broker, configured task routing,
and periodic tasks for scheduled operations.
"""

from celery import Celery
from celery.schedules import crontab

from workers.stream_processor import process_frame_task

# Celery Configuration
celery_app = Celery(
    "edge_analytics_workers",
    broker="redis://redis:6379/1",
    backend="redis://redis:6379/2",
    include=["workers.tasks"],
)

# Worker Configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Worker behavior
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_retry_delay=30,
    task_retry_backoff=True,
    task_retry_jitter=True,

    # Performance tuning
    worker_concurrency=4,
    worker_max_tasks_per_child=100,
    worker_keepalive=30,
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes

    # Result backend settings
    result_expires=3600,       # 1 hour
    result_backend_num_workers=2,

    # Periodic tasks (beat schedule)
    beat_schedule={
        "frame-metadata-cleanup": {
            "task": "workers.tasks.cleanup_old_frames",
            "schedule": crontab(minute=0, hour=6),  # Daily at 6 AM
            "args": (),
        },
        "metrics-purge": {
            "task": "workers.tasks.purge_old_metrics",
            "schedule": crontab(minute=30, hour=2),  # Daily at 2:30 AM
            "args": (),
        },
        "alert-cleanup": {
            "task": "workers.tasks.cleanup_resolved_alerts",
            "schedule": crontab(minute=15, hour=1),  # Daily at 1:15 AM
            "args": (),
        },
    },
)

# Task routing
@celery_app.task(bind=True)
def debug_task(self, *args, **kwargs):
    """Debug task to test Celery worker connectivity."""
    print(f"Debug task executed by worker {self.worker_id}")
    return {"status": "ok", "worker_id": self.worker_id, "task_id": self.request.id}