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
        'tasks.invoice_tasks',
        'tasks.video_analysis_tasks',
        'tasks.reminder_tasks',
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
    "check-overdue-invoices": {
        "task": "tasks.invoice_tasks.check_overdue_invoices",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8am UTC
    },
    "send-pending-reminders-morning": {
        "task": "tasks.reminder_tasks.process_pending_responses",
        "schedule": crontab(hour=9, minute=0),  # Daily at 9am UTC
    },
    "send-pending-reminders-evening": {
        "task": "tasks.reminder_tasks.process_pending_responses",
        "schedule": crontab(hour=17, minute=0),  # Daily at 5pm UTC
    },
}
