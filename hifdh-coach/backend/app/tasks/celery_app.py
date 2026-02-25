"""
Celery application configuration.
Defines task routing, serialization, and worker settings.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hifdh_coach",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Task routing: GPU tasks go to gpu queue, others to default
    task_routes={
        "process_recitation": {"queue": "gpu"},
        "generate_daily_schedules": {"queue": "default"},
        "aggregate_analytics": {"queue": "default"},
        "meter_usage": {"queue": "default"},
    },

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # one task at a time for GPU workers

    # Result settings
    result_expires=86400,  # 24 hours

    # Beat schedule (periodic tasks)
    beat_schedule={
        "generate-daily-schedules": {
            "task": "generate_daily_schedules",
            "schedule": 3600.0 * 4,  # every 4 hours
            "options": {"queue": "default"},
        },
        "aggregate-analytics": {
            "task": "aggregate_analytics",
            "schedule": 3600.0,  # every hour
            "options": {"queue": "default"},
        },
        "decay-retention-scores": {
            "task": "decay_retention_scores",
            "schedule": 3600.0 * 6,  # every 6 hours
            "options": {"queue": "default"},
        },
        "meter-stripe-usage": {
            "task": "meter_usage",
            "schedule": 3600.0,  # every hour
            "options": {"queue": "default"},
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
