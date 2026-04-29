import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.email_utils import send_email
from utils.feedback_utils import generate_rejection_feedback

logger = logging.getLogger(__name__)


@celery.task(name="tasks.feedback_tasks.generate_and_store_feedback")
def generate_and_store_feedback(candidate_id: str, jd_id: str):
    db = get_db()

    candidate = db.candidates.find_one(
        {"candidate_id": candidate_id},
        {"name": 1, "email": 1, "experience_years": 1, "skills": 1}
    )
    if not candidate:
        logger.error(f"Candidate {candidate_id} not found")
        return {"error": "candidate not found"}

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        logger.error(f"JD {jd_id} not found")
        return {"error": "jd not found"}

    pool_record = db.candidate_pools.find_one({"candidate_id": candidate_id, "jd_id": jd_id})
    gaps = pool_record.get("gaps", []) if pool_record else []

    structured_jd = jd.get("structured_data", {})
    feedback_text = generate_rejection_feedback(structured_jd, gaps, candidate)

    record = {
        "candidate_id": candidate_id,
        "jd_id": jd_id,
        "jd_title": structured_jd.get("title", jd.get("title", "")),
        "candidate_name": candidate.get("name", ""),
        "candidate_email": candidate.get("email", ""),
        "feedback_text": feedback_text,
        "gaps_used": gaps,
        "generated_at": datetime.utcnow(),
        "digest_sent": False,
        "digest_sent_at": None,
    }

    db.candidate_feedback.update_one(
        {"candidate_id": candidate_id, "jd_id": jd_id},
        {"$set": record},
        upsert=True
    )

    logger.info(f"Feedback stored for candidate {candidate_id} / JD {jd_id}")
    return {"status": "stored", "candidate_id": candidate_id, "jd_id": jd_id}


@celery.task(name="tasks.feedback_tasks.send_weekly_digest")
def send_weekly_digest():
    db = get_db()

    unsent = list(db.candidate_feedback.find(
        {"digest_sent": False, "candidate_email": {"$nin": [None, ""]}},
    ).limit(500))
    if not unsent:
        logger.info("No unsent feedback records — digest skipped.")
        return {"sent": 0}

    by_email: dict[str, list] = {}
    for record in unsent:
        by_email.setdefault(record["candidate_email"], []).append(record)

    sent_count = 0
    for email, records in by_email.items():
        html = _build_digest_html(records)
        success = send_email(email, "Your JobOS Application Feedback", html)
        if success:
            ids = [r["_id"] for r in records]
            db.candidate_feedback.update_many(
                {"_id": {"$in": ids}},
                {"$set": {"digest_sent": True, "digest_sent_at": datetime.utcnow()}}
            )
            sent_count += 1
            logger.info(f"Digest sent to {email} ({len(records)} item(s))")
        else:
            logger.warning(f"Failed to send digest to {email}")

    return {"sent": sent_count, "total_candidates": len(by_email)}


def _build_digest_html(records: list) -> str:
    items_html = ""
    for r in records:
        items_html += f"""
        <div style="margin-bottom:24px;padding:16px;border-left:4px solid #4F46E5;background:#F9FAFB;">
          <p style="font-weight:600;color:#111827;margin:0 0 8px">{r.get('jd_title', 'Role')}</p>
          <p style="color:#374151;line-height:1.6;margin:0">{r['feedback_text']}</p>
        </div>"""

    return f"""<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#111827">
  <h2 style="color:#4F46E5">Your Application Feedback</h2>
  <p>Thank you for applying through JobOS. Here is constructive feedback on your recent applications:</p>
  {items_html}
  <p style="margin-top:32px;color:#6B7280;font-size:0.875rem">
    This digest is sent weekly. Keep building your skills — the right opportunity is ahead.
  </p>
</body></html>"""
