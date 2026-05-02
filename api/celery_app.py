import os
from celery import Celery
from celery.schedules import crontab

from utils.config_utils import get_pipeline_config

celery = Celery(
    "jobos",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    include=[
        'tasks.jd_tasks',
        'tasks.resume_tasks',
        'tasks.matching_tasks',
        'tasks.notification_tasks',
        'tasks.pipeline_tasks',
        'tasks.feedback_tasks',
        'tasks.retention_tasks',
    ]
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

_monitor_interval = int(get_pipeline_config().get("monitor_interval_minutes", 30))
celery.conf.beat_schedule = {
    "check-stage-breaches": {
        "task": "tasks.pipeline_tasks.check_stage_breaches",
        "schedule": crontab(minute=f"*/{_monitor_interval}"),
    },
    "send-weekly-feedback-digest": {
        "task": "tasks.feedback_tasks.send_weekly_digest",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Every Monday 09:00 UTC
    },
    "check-retention-clock": {
        "task": "tasks.retention_tasks.check_retention_clock",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight UTC
    },
}
