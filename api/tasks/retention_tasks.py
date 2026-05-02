import uuid
import logging
from datetime import datetime, timedelta
from celery_app import celery
from utils.client_utils import get_db
from utils.email_utils import send_email

logger = logging.getLogger(__name__)


@celery.task(name="tasks.retention_tasks.start_retention_clock")
def start_retention_clock(jd_id: str, candidate_id: str):
    """Create retention tracking record when candidate reaches 'joined' stage."""
    logger.info(f"start_retention_clock: {candidate_id} for {jd_id}")
    db = get_db()

    existing = db.retention_tracking.find_one({
        "jd_id": jd_id,
        "candidate_id": candidate_id,
    })
    if existing:
        logger.info(f"Retention record already exists for {candidate_id}/{jd_id}")
        return

    now = datetime.utcnow()
    record = {
        "retention_id": str(uuid.uuid4()),
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "joined_at": now,
        "90_day_warning_sent": False,
        "180_day_reminder_sent": False,
        "created_at": now,
        "updated_at": now,
    }

    db.retention_tracking.insert_one(record)
    logger.info(f"Retention clock started for {candidate_id}/{jd_id}, due at {now + timedelta(days=180)}")


@celery.task(name="tasks.retention_tasks.check_retention_clock")
def check_retention_clock():
    """Daily task to check retention milestones (90d warning, 180d reminder)."""
    logger.info("check_retention_clock running")
    db = get_db()

    now = datetime.utcnow()

    # Check for 90-day warnings
    ninety_day_milestone = now - timedelta(days=90)
    warning_records = list(db.retention_tracking.find({
        "joined_at": {"$lte": ninety_day_milestone},
        "90_day_warning_sent": False,
    }))

    for record in warning_records:
        try:
            _send_90day_warning(db, record)
            db.retention_tracking.update_one(
                {"_id": record["_id"]},
                {"$set": {"90_day_warning_sent": True, "updated_at": now}},
            )
            logger.info(f"90-day warning sent for {record['candidate_id']}")
        except Exception as e:
            logger.error(f"Failed to send 90-day warning for {record['candidate_id']}: {e}")

    # Check for 180-day reminders
    one_eighty_day_milestone = now - timedelta(days=180)
    reminder_records = list(db.retention_tracking.find({
        "joined_at": {"$lte": one_eighty_day_milestone},
        "180_day_reminder_sent": False,
    }))

    for record in reminder_records:
        try:
            _send_180day_reminder(db, record)
            db.retention_tracking.update_one(
                {"_id": record["_id"]},
                {"$set": {"180_day_reminder_sent": True, "updated_at": now}},
            )
            logger.info(f"180-day invoice reminder sent for {record['candidate_id']}")
        except Exception as e:
            logger.error(f"Failed to send 180-day reminder for {record['candidate_id']}: {e}")

    logger.info(f"check_retention_clock complete: {len(warning_records)} 90d warnings, {len(reminder_records)} 180d reminders")


def _send_90day_warning(db, record: dict):
    """Send manager warning at 90-day mark."""
    candidate_id = record["candidate_id"]
    jd_id = record["jd_id"]

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"name": 1})
    jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"title": 1})

    cand_name = candidate.get("name", candidate_id) if candidate else candidate_id
    jd_title = jd.get("title", jd_id) if jd else jd_id

    managers = list(db.users.find(
        {"roles": {"$in": ["manager", "admin"]}},
        {"email": 1, "username": 1}
    ))

    if not managers:
        logger.warning(f"No managers found for 90-day warning of {candidate_id}")
        return

    subject = f"[JobOS] Retention Alert: 90 Days to Review — {cand_name}"
    html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Retention Alert</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <h2 style="color:#f59e0b;margin:0 0 16px 0;font-size:18px">90-Day Retention Checkpoint</h2>
      <p style="color:#94a3b8;margin:0 0 16px 0">
        Candidate <strong style="color:#f1f5f9">{cand_name}</strong> is approaching their 90-day mark on the <strong style="color:#f1f5f9">{jd_title}</strong> position.
      </p>
      <div style="background:#0f172a;padding:16px;border-radius:8px;margin-bottom:16px">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px 0">Action Items</p>
        <ul style="color:#94a3b8;margin:0;padding-left:20px">
          <li style="margin-bottom:8px">Review candidate's 90-day performance</li>
          <li style="margin-bottom:8px">Schedule retention check-in meeting</li>
          <li>Document any concerns or confirmations</li>
        </ul>
      </div>
      <p style="color:#94a3b8;font-size:13px;margin:0">
        You have 90 days remaining before the final retention invoice is due on day 180.
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""

    for manager in managers:
        email = manager.get("email")
        if not email:
            continue

        db.notifications.insert_one({
            "notification_id": str(uuid.uuid4()),
            "type": "retention_90day_warning",
            "recipient_email": email,
            "recipient_roles": manager.get("roles", []),
            "title": f"Retention Alert: 90 days to review — {cand_name}",
            "body": f"Candidate {cand_name} has reached their 90-day mark on {jd_title}. Review and assess retention risk.",
            "data": {
                "candidate_id": candidate_id,
                "jd_id": jd_id,
                "candidate_name": cand_name,
                "jd_title": jd_title,
                "days_remaining": 90,
            },
            "is_read": False,
            "created_at": datetime.utcnow(),
        })

        send_email(email, subject, html)
        logger.info(f"90-day warning email sent to {email} for {candidate_id}")


def _send_180day_reminder(db, record: dict):
    """Send invoice reminder at 180-day mark."""
    candidate_id = record["candidate_id"]
    jd_id = record["jd_id"]

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"name": 1})
    jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"title": 1})

    cand_name = candidate.get("name", candidate_id) if candidate else candidate_id
    jd_title = jd.get("title", jd_id) if jd else jd_id

    managers = list(db.users.find(
        {"roles": {"$in": ["manager", "admin"]}},
        {"email": 1, "username": 1}
    ))

    if not managers:
        logger.warning(f"No managers found for 180-day reminder of {candidate_id}")
        return

    subject = f"[JobOS] Retention Invoice Due — {cand_name} (180 Days)"
    html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Retention Invoice Reminder</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <h2 style="color:#ef4444;margin:0 0 16px 0;font-size:18px">180-Day Retention Invoice Due</h2>
      <p style="color:#94a3b8;margin:0 0 16px 0">
        Candidate <strong style="color:#f1f5f9">{cand_name}</strong> has completed 180 days on the <strong style="color:#f1f5f9">{jd_title}</strong> position.
      </p>
      <div style="background:#0f172a;padding:16px;border-radius:8px;margin-bottom:16px;border-left:4px solid #ef4444">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px 0">Immediate Action Required</p>
        <p style="color:#f1f5f9;margin:0 0 8px 0;font-weight:500">Final retention invoice must be generated and submitted immediately.</p>
        <p style="color:#94a3b8;font-size:13px;margin:0">This milestone marks the end of the 180-day retention tracking period.</p>
      </div>
      <p style="color:#94a3b8;font-size:13px;margin:0">
        Please review the candidate's performance and confirm their continued employment status.
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""

    for manager in managers:
        email = manager.get("email")
        if not email:
            continue

        db.notifications.insert_one({
            "notification_id": str(uuid.uuid4()),
            "type": "retention_180day_invoice",
            "recipient_email": email,
            "recipient_roles": manager.get("roles", []),
            "title": f"Retention Invoice Due — {cand_name} (180 Days)",
            "body": f"Final retention invoice for {cand_name} ({jd_title}) is due now. Candidate has completed 180 days.",
            "data": {
                "candidate_id": candidate_id,
                "jd_id": jd_id,
                "candidate_name": cand_name,
                "jd_title": jd_title,
                "milestone": "180_days",
            },
            "is_read": False,
            "created_at": datetime.utcnow(),
        })

        send_email(email, subject, html)
        logger.info(f"180-day invoice reminder sent to {email} for {candidate_id}")
