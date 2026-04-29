import uuid
import logging
from datetime import datetime, timedelta

from celery_app import celery
from utils.client_utils import get_db
from utils.config_utils import get_pipeline_config
from utils.email_utils import send_email

logger = logging.getLogger(__name__)


def _stage_due_at(entered_at: datetime, sla_hours: int) -> datetime:
    return entered_at + timedelta(hours=sla_hours)


def _active_extension_until(stage: dict, now: datetime):
    ext = stage.get("extension")
    if not ext or not ext.get("approved"):
        return None
    until = ext.get("approved_until")
    if until and until > now:
        return until
    return None


def _effective_due(stage: dict, now: datetime) -> datetime:
    return _active_extension_until(stage, now) or stage.get("due_at")


def _format_stage_name(name: str) -> str:
    return name.replace("_", " ").title()


def _warning_email(jd_title: str, candidate_name: str, stage_name: str, due_at: datetime) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;padding:24px">
  <div style="max-width:640px;margin:0 auto;background:#1e293b;padding:24px;border-radius:12px">
    <h2 style="color:#f59e0b;margin:0 0 12px 0">Stage SLA Warning (75%)</h2>
    <p style="color:#cbd5e1">Candidate <b>{candidate_name}</b> for <b>{jd_title}</b> is at 75% of the SLA window for stage <b>{_format_stage_name(stage_name)}</b>.</p>
    <p style="color:#94a3b8;font-size:13px">Stage due: {due_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
    <p style="color:#94a3b8;font-size:12px;margin-top:24px">JobOS · Closure Engine</p>
  </div>
</body></html>"""


def _escalation_email(jd_title: str, candidate_name: str, stage_name: str, due_at: datetime, recruiter_email: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;padding:24px">
  <div style="max-width:640px;margin:0 auto;background:#1e293b;padding:24px;border-radius:12px">
    <h2 style="color:#ef4444;margin:0 0 12px 0">Stage SLA Breach — Escalation</h2>
    <p style="color:#cbd5e1">Candidate <b>{candidate_name}</b> for <b>{jd_title}</b> has breached the SLA for stage <b>{_format_stage_name(stage_name)}</b>.</p>
    <p style="color:#94a3b8;font-size:13px">Was due: {due_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
    <p style="color:#94a3b8;font-size:13px">Recruiter: {recruiter_email or '—'}</p>
    <p style="color:#94a3b8;font-size:12px;margin-top:24px">JobOS · Closure Engine</p>
  </div>
</body></html>"""


def _store_notification(db, recipient_email: str, ntype: str, title: str, body: str, data: dict):
    db.notifications.insert_one({
        "notification_id": str(uuid.uuid4()),
        "type": ntype,
        "recipient_email": recipient_email,
        "title": title,
        "body": body,
        "data": data,
        "is_read": False,
        "created_at": datetime.utcnow(),
    })


def _resolve_recipients(db, roles: list) -> list:
    return list(db.users.find(
        {"roles": {"$in": roles}},
        {"email": 1, "username": 1, "roles": 1},
    ))


@celery.task(name="tasks.pipeline_tasks.check_stage_breaches")
def check_stage_breaches():
    """Periodic monitor: scans pipeline_stages for 75% warnings and 100% escalations."""
    db = get_db()
    cfg = get_pipeline_config()
    warning_threshold = float(cfg.get("warning_threshold", 0.75))
    escalation_roles = cfg.get("escalation_roles", ["manager", "admin"])

    now = datetime.utcnow()
    pipelines = list(db.pipeline_stages.find({}))
    if not pipelines:
        logger.info("check_stage_breaches: no pipeline_stages records found")
        return {"warned": 0, "escalated": 0}

    warned = 0
    escalated = 0
    ops_recipients = _resolve_recipients(db, escalation_roles)

    for doc in pipelines:
        jd_id = doc.get("jd_id")
        candidate_id = doc.get("candidate_id")
        current = doc.get("current_stage")
        stages = doc.get("stages", [])
        if not current or not stages:
            continue

        stage_idx = next((i for i, s in enumerate(stages) if s.get("name") == current), -1)
        if stage_idx < 0:
            continue
        stage = stages[stage_idx]
        if stage.get("completed_at"):
            continue

        due_at = _effective_due(stage, now)
        if not due_at:
            continue
        entered_at = stage.get("entered_at")
        if not entered_at:
            continue

        sla_seconds = (due_at - entered_at).total_seconds()
        if sla_seconds <= 0:
            continue
        elapsed_seconds = (now - entered_at).total_seconds()
        progress = elapsed_seconds / sla_seconds

        jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"structured_data": 1, "title": 1, "assigned_to": 1})
        jd_title = (jd.get("structured_data") or {}).get("title") if jd else jd_id
        jd_title = jd_title or jd_id
        cand = db.candidates.find_one({"candidate_id": candidate_id}, {"name": 1, "email": 1})
        candidate_name = (cand or {}).get("name") or candidate_id

        recruiter_email = None
        if jd and jd.get("assigned_to"):
            rec = db.users.find_one({"keycloak_id": jd["assigned_to"]}, {"email": 1}) \
                or db.users.find_one({"username": jd["assigned_to"]}, {"email": 1})
            recruiter_email = (rec or {}).get("email")

        if progress >= 1.0 and not stage.get("escalated_at"):
            html = _escalation_email(jd_title, candidate_name, current, due_at, recruiter_email)
            subject = f"[JobOS] SLA Breach — {candidate_name} · {_format_stage_name(current)}"
            for r in ops_recipients:
                email = r.get("email")
                if not email:
                    continue
                _store_notification(
                    db, email, "stage_escalation",
                    f"SLA breach — {candidate_name}",
                    f"{_format_stage_name(current)} stage breached for {jd_title}.",
                    {"jd_id": jd_id, "candidate_id": candidate_id, "stage": current, "due_at": due_at.isoformat()},
                )
                send_email(email, subject, html)
            db.pipeline_stages.update_one(
                {"_id": doc["_id"]},
                {"$set": {f"stages.{stage_idx}.escalated_at": now, "updated_at": now}},
            )
            escalated += 1
            logger.warning(f"Escalated breach for {candidate_id} / {jd_id} stage={current}")

        elif progress >= warning_threshold and not stage.get("warned_at") and not stage.get("escalated_at"):
            if recruiter_email:
                html = _warning_email(jd_title, candidate_name, current, due_at)
                subject = f"[JobOS] SLA Warning — {candidate_name} · {_format_stage_name(current)}"
                _store_notification(
                    db, recruiter_email, "stage_warning",
                    f"SLA warning — {candidate_name}",
                    f"{_format_stage_name(current)} stage approaching breach for {jd_title}.",
                    {"jd_id": jd_id, "candidate_id": candidate_id, "stage": current, "due_at": due_at.isoformat()},
                )
                send_email(recruiter_email, subject, html)
            db.pipeline_stages.update_one(
                {"_id": doc["_id"]},
                {"$set": {f"stages.{stage_idx}.warned_at": now, "updated_at": now}},
            )
            warned += 1
            logger.info(f"Warned recruiter for {candidate_id} / {jd_id} stage={current}")

    logger.info(f"check_stage_breaches complete: warned={warned}, escalated={escalated}")
    return {"warned": warned, "escalated": escalated}
