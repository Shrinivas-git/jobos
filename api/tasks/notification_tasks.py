import uuid
import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.email_utils import send_email

logger = logging.getLogger(__name__)


def _build_email_html(jd_title: str, jd_id: str, pool: list) -> str:
    total = len(pool)
    internal = sum(1 for c in pool if c.get("source", "internal") != "external")
    external = total - internal

    rows = ""
    for c in pool[:10]:
        strengths = ", ".join((c.get("strengths") or [])[:3]) or "—"
        gaps = ", ".join((c.get("gaps") or [])[:2]) or "—"
        name = c.get("_name", c.get("candidate_id", "Unknown"))
        score = c.get("composite_score", 0)
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#94a3b8;text-align:center">{c.get("rank","—")}</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#f1f5f9">{name}</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#60a5fa;text-align:center">{score:.1f}%</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#4ade80;font-size:12px">{strengths}</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#f87171;font-size:12px">{gaps}</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#94a3b8;text-align:center;font-size:11px">{c.get("source","internal")}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:800px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Candidate Pool Ready</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h2 style="color:#f1f5f9;margin:0 0 6px 0;font-size:18px">{jd_title}</h2>
      <p style="color:#94a3b8;margin:0 0 20px 0;font-size:13px">JD: <span style="color:#60a5fa">{jd_id}</span></p>
      <div style="display:flex;gap:12px">
        <div style="background:#0f172a;padding:12px 24px;border-radius:8px;text-align:center;min-width:80px">
          <p style="color:#60a5fa;font-size:28px;font-weight:700;margin:0">{total}</p>
          <p style="color:#64748b;font-size:10px;margin:4px 0 0 0;text-transform:uppercase">Total</p>
        </div>
        <div style="background:#0f172a;padding:12px 24px;border-radius:8px;text-align:center;min-width:80px">
          <p style="color:#4ade80;font-size:28px;font-weight:700;margin:0">{internal}</p>
          <p style="color:#64748b;font-size:10px;margin:4px 0 0 0;text-transform:uppercase">Internal</p>
        </div>
        <div style="background:#0f172a;padding:12px 24px;border-radius:8px;text-align:center;min-width:80px">
          <p style="color:#f59e0b;font-size:28px;font-weight:700;margin:0">{external}</p>
          <p style="color:#64748b;font-size:10px;margin:4px 0 0 0;text-transform:uppercase">External</p>
        </div>
      </div>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <h3 style="color:#f1f5f9;margin:0 0 16px 0;font-size:15px">Stack-Ranked Pool</h3>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#0f172a">
            <th style="padding:10px;color:#475569;text-align:center;font-size:10px;text-transform:uppercase;letter-spacing:1px">#</th>
            <th style="padding:10px;color:#475569;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:1px">Candidate</th>
            <th style="padding:10px;color:#475569;text-align:center;font-size:10px;text-transform:uppercase;letter-spacing:1px">Fitment</th>
            <th style="padding:10px;color:#475569;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:1px">Strengths</th>
            <th style="padding:10px;color:#475569;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:1px">Gaps</th>
            <th style="padding:10px;color:#475569;text-align:center;font-size:10px;text-transform:uppercase;letter-spacing:1px">Source</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""


@celery.task(name="tasks.notification_tasks.notify_pool_ready")
def notify_pool_ready(jd_id: str):
    logger.info(f"notify_pool_ready triggered for JD: {jd_id}")
    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        logger.error(f"JD {jd_id} not found — aborting notification")
        return

    structured = jd.get("structured_data", {})
    jd_title = structured.get("title") or jd.get("title", "Job Role")

    pool = list(
        db.candidate_pools.find(
            {"jd_id": jd_id, "status": "pass_2_complete"}
        ).sort("rank", 1).limit(20)
    )

    for entry in pool:
        cand = db.candidates.find_one({"candidate_id": entry["candidate_id"]}, {"name": 1})
        entry["_name"] = cand.get("name", entry["candidate_id"]) if cand else entry["candidate_id"]

    recipients = list(
        db.users.find(
            {"roles": {"$in": ["manager", "hod"]}},
            {"email": 1, "roles": 1, "username": 1}
        )
    )

    if not recipients:
        logger.warning(f"No manager/hod users in users collection for JD {jd_id} — no notifications sent")
        return

    notification_data = {
        "jd_id": jd_id,
        "jd_title": jd_title,
        "pool_size": len(pool),
        "internal_count": sum(1 for c in pool if c.get("source", "internal") != "external"),
        "external_count": sum(1 for c in pool if c.get("source") == "external"),
        "top_candidates": [
            {
                "rank": c.get("rank"),
                "candidate_id": c["candidate_id"],
                "name": c.get("_name"),
                "composite_score": round(c.get("composite_score", 0), 1),
                "strengths": (c.get("strengths") or [])[:3],
                "gaps": (c.get("gaps") or [])[:2],
                "source": c.get("source", "internal"),
                "recommendation": c.get("recommendation"),
            }
            for c in pool[:10]
        ],
    }

    email_html = _build_email_html(jd_title, jd_id, pool)
    subject = f"[JobOS] Candidate Pool Ready — {jd_title}"
    now = datetime.utcnow()

    for recipient in recipients:
        email = recipient.get("email")
        if not email:
            continue
        db.notifications.insert_one({
            "notification_id": str(uuid.uuid4()),
            "type": "pool_ready",
            "recipient_email": email,
            "recipient_roles": recipient.get("roles", []),
            "title": f"Candidate pool ready — {jd_title}",
            "body": f"{len(pool)} candidates evaluated and stack-ranked for {jd_id}.",
            "data": notification_data,
            "is_read": False,
            "created_at": now,
        })
        logger.info(f"In-app notification stored for {email}")
        send_email(email, subject, email_html)

    logger.info(f"notify_pool_ready complete for {jd_id}: {len(recipients)} recipients notified")
