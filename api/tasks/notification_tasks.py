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


def _build_client_package_html(jd_title: str, jd_id: str, candidates: list) -> str:
    verdict_color = {"shortlist": "#4ade80", "hold": "#f59e0b", "reject": "#f87171"}
    verdict_label = {"shortlist": "STRONG HIRE", "hold": "BORDERLINE", "reject": "NOT RECOMMENDED"}

    candidate_blocks = ""
    for i, c in enumerate(candidates):
        name = c.get("_name", c.get("candidate_id", "Unknown"))
        score = c.get("fitment_score") or c.get("composite_score") or 0
        rec = (c.get("recommendation") or "hold").lower()
        color = verdict_color.get(rec, "#f59e0b")
        label = verdict_label.get(rec, "BORDERLINE")
        reasoning = c.get("reasoning") or ""
        strengths = c.get("strengths") or []
        gaps = c.get("gaps") or []
        availability = c.get("availability_reason") or c.get("availability_signal") or ""

        strengths_html = "".join(
            f'<li style="margin:6px 0;color:#cbd5e1;font-size:13px;line-height:1.6">{s}</li>'
            for s in strengths[:3]
        )
        gaps_html = "".join(
            f'<li style="margin:6px 0;color:#cbd5e1;font-size:13px;line-height:1.6">{g}</li>'
            for g in gaps[:2]
        )

        candidate_blocks += f"""
    <div style="background:#1e293b;border-radius:12px;padding:28px;margin-bottom:20px;border-left:4px solid {color}">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
        <div>
          <p style="margin:0;font-size:20px;font-weight:700;color:#f1f5f9">#{i+1} &nbsp;{name}</p>
          <p style="margin:4px 0 0 0;font-size:13px;color:#64748b">{c.get('candidate_id','')}</p>
        </div>
        <div style="text-align:right">
          <p style="margin:0;font-size:28px;font-weight:900;color:{color}">{score:.0f}%</p>
          <p style="margin:2px 0 0 0;font-size:10px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:1px">{label}</p>
        </div>
      </div>

      {"<p style='margin:0 0 16px 0;font-size:13px;color:#94a3b8;line-height:1.7;font-style:italic'>" + reasoning + "</p>" if reasoning else ""}

      {"<p style='margin:0 0 6px 0;font-size:11px;font-weight:700;color:#4ade80;text-transform:uppercase;letter-spacing:1px'>Strengths</p><ul style='margin:0 0 16px 0;padding-left:18px'>" + strengths_html + "</ul>" if strengths_html else ""}

      {"<p style='margin:0 0 6px 0;font-size:11px;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:1px'>Key Gaps</p><ul style='margin:0 0 16px 0;padding-left:18px'>" + gaps_html + "</ul>" if gaps_html else ""}

      {"<p style='margin:0;font-size:12px;color:#64748b;font-style:italic'>⏱ " + availability + "</p>" if availability else ""}
    </div>"""

    return f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:700px;margin:0 auto">

    <div style="background:#1e293b;padding:28px;border-radius:12px;margin-bottom:20px">
      <p style="margin:0 0 4px 0;font-size:22px;font-weight:700;color:#60a5fa">Candidate Assessment Report</p>
      <p style="margin:0;font-size:12px;color:#475569;text-transform:uppercase;letter-spacing:2px">Prepared by your recruitment partner</p>
    </div>

    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:20px">
      <p style="margin:0 0 4px 0;font-size:17px;font-weight:700;color:#f1f5f9">{jd_title}</p>
      <p style="margin:0 0 16px 0;font-size:12px;color:#475569">Ref: {jd_id}</p>
      <p style="margin:0;font-size:13px;color:#94a3b8;line-height:1.7">
        Please find below our assessed candidates for this position, ranked by fitment.
        Each profile has been evaluated against your job requirements.
        Kindly review and reply with the candidates you'd like to proceed with.
      </p>
    </div>

    {candidate_blocks}

    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      This report is confidential and intended solely for the named recipient.
    </p>
  </div>
</body>
</html>"""


@celery.task(name="tasks.notification_tasks.send_client_package")
def send_client_package(jd_id: str, client_email: str):
    logger.info(f"send_client_package: JD {jd_id} → {client_email}")
    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        logger.error(f"JD {jd_id} not found")
        return
    structured = jd.get("structured_data", {})
    jd_title = structured.get("title") or jd.get("title", "Job Role")

    candidates = list(db.candidate_pools.find({"jd_id": jd_id, "status": "pass_2_complete"}).sort("rank", 1))
    for entry in candidates:
        cand = db.candidates.find_one({"candidate_id": entry["candidate_id"]}, {"name": 1})
        entry["_name"] = cand.get("name", entry["candidate_id"]) if cand else entry["candidate_id"]

    html = _build_client_package_html(jd_title, jd_id, candidates)
    subject = f"Candidate Assessment — {jd_title}"
    send_email(client_email, subject, html)
    logger.info(f"Client package sent to {client_email} for JD {jd_id} ({len(candidates)} candidates)")


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


@celery.task(name="tasks.notification_tasks.notify_candidate_document_access")
def notify_candidate_document_access(
    doc_id: str,
    candidate_id: str,
    doc_type: str,
    accessor_email: str,
    access_type: str,
):
    """Notify the candidate in real time when a recruiter views or downloads their document."""
    logger.info(f"notify_candidate_document_access: {doc_id} {access_type} by {accessor_email}")
    db = get_db()

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"email": 1, "name": 1})
    if not candidate or not candidate.get("email"):
        logger.warning(f"Candidate {candidate_id} has no email — skipping document access notification")
        return

    now = datetime.utcnow()
    action_label = "downloaded" if access_type == "download" else "viewed"
    doc_label = doc_type.replace("_", " ").title()

    db.notifications.insert_one({
        "notification_id": str(uuid.uuid4()),
        "type": "document_access",
        "recipient_email": candidate["email"],
        "recipient_roles": ["candidate"],
        "title": f"Your {doc_label} document was {action_label}",
        "body": (
            f"A recruiter ({accessor_email}) {action_label} your {doc_label} document "
            f"on {now.strftime('%d %b %Y at %H:%M UTC')}."
        ),
        "data": {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "accessor_email": accessor_email,
            "access_type": access_type,
            "timestamp": now.isoformat(),
        },
        "is_read": False,
        "created_at": now,
    })

    subject = f"[JobOS] Your document was {action_label}"
    html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Document Access Alert</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#f1f5f9;margin:0 0 16px 0">Hi {candidate.get('name', 'Candidate')},</p>
      <p style="color:#94a3b8;margin:0 0 16px 0">
        A recruiter <strong style="color:#60a5fa">{action_label}</strong> your
        <strong style="color:#f1f5f9">{doc_label}</strong> document.
      </p>
      <div style="background:#0f172a;padding:16px;border-radius:8px;margin-bottom:16px">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0">Access Details</p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Recruiter: <span style="color:#f1f5f9">{accessor_email}</span></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Document: <span style="color:#f1f5f9">{doc_label}</span></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Action: <span style="color:#f1f5f9">{action_label.title()}</span></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Time: <span style="color:#f1f5f9">{now.strftime('%d %b %Y at %H:%M UTC')}</span></p>
      </div>
      <p style="color:#64748b;font-size:12px;margin:0">
        You can revoke document access at any time from your JobOS profile.
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""

    send_email(candidate["email"], subject, html)
    logger.info(f"Document access notification sent to {candidate['email']} for {doc_id}")


@celery.task(name="tasks.notification_tasks.send_interview_email")
def send_interview_email(jd_id: str, candidate_id: str, interview_details: dict):
    """Send interview schedule confirmation email to candidate."""
    logger.info(f"send_interview_email: {candidate_id} for JD {jd_id}")
    db = get_db()

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"email": 1, "name": 1})
    if not candidate or not candidate.get("email"):
        logger.warning(f"No email for candidate {candidate_id} — skipping interview email")
        return

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    jd_title = (jd.get("structured_data", {}).get("title") or jd.get("title", "Job Role")) if jd else "Job Role"

    name = candidate.get("name", "Candidate")
    email = candidate["email"]

    date = interview_details.get("date", "")
    time = interview_details.get("time", "")
    mode = interview_details.get("mode", "online")
    meeting_link = interview_details.get("meeting_link") or ""
    location = interview_details.get("location") or ""
    notes = interview_details.get("notes") or ""
    duration_map = {"30min": "30 minutes", "45min": "45 minutes", "1hour": "1 hour"}
    duration_label = duration_map.get(interview_details.get("duration", "1hour"), "1 hour")

    mode_row = ""
    if mode == "online" and meeting_link:
        mode_row = f'<p style="color:#94a3b8;margin:4px 0;font-size:13px">Meeting Link: <a href="{meeting_link}" style="color:#60a5fa">{meeting_link}</a></p>'
    elif mode == "in-person" and location:
        mode_row = f'<p style="color:#94a3b8;margin:4px 0;font-size:13px">Location: <span style="color:#f1f5f9">{location}</span></p>'

    notes_block = ""
    if notes:
        notes_block = f"""
        <div style="background:#0f172a;padding:16px;border-radius:8px;margin-top:16px">
          <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0">Notes from Recruiter</p>
          <p style="color:#94a3b8;margin:0;font-size:13px">{notes}</p>
        </div>"""

    subject = f"[JobOS] Interview Scheduled — {jd_title}"
    html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Interview Scheduled</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#f1f5f9;margin:0 0 16px 0">Hi {name},</p>
      <p style="color:#94a3b8;margin:0 0 20px 0">
        Your interview for <strong style="color:#f1f5f9">{jd_title}</strong> has been scheduled. Please find the details below.
      </p>
      <div style="background:#0f172a;padding:16px;border-radius:8px;margin-bottom:16px">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px 0">Interview Details</p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Date: <span style="color:#f1f5f9">{date}</span></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Time: <span style="color:#f1f5f9">{time}</span></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Duration: <span style="color:#f1f5f9">{duration_label}</span></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Mode: <span style="color:#f1f5f9">{"Online" if mode == "online" else "In-person"}</span></p>
        {mode_row}
      </div>
      {notes_block}
      <p style="color:#64748b;font-size:12px;margin-top:20px 0 0 0">
        Please ensure you are available at the scheduled time. Reply to this email if you need to reschedule.
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""

    send_email(email, subject, html)
    logger.info(f"Interview email sent to {email} for candidate {candidate_id}")

    # Also notify client
    client_email = jd.get("client_email") if jd else None
    if client_email:
        structured = (jd.get("structured_data") or {}) if jd else {}
        level = structured.get("level", "")
        location = structured.get("location", "Not specified")
        skills = (structured.get("must_have_skills") or structured.get("skills") or [])[:5]
        skills_str = ", ".join(skills) if skills else "—"

        mode_client = ""
        if mode == "online" and meeting_link:
            mode_client = f'<p style="color:#94a3b8;margin:4px 0;font-size:13px">Meeting Link: <a href="{meeting_link}" style="color:#60a5fa">{meeting_link}</a></p>'
        elif mode == "in-person" and location:
            mode_client = f'<p style="color:#94a3b8;margin:4px 0;font-size:13px">Location: <span style="color:#f1f5f9">{location}</span></p>'

        client_subject = f"Interview Scheduled — {name} · {jd_title}"
        client_html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <p style="color:#60a5fa;margin:0 0 4px 0;font-size:20px;font-weight:700">Interview Confirmation</p>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">From your recruitment partner</p>
    </div>

    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0">Role</p>
      <p style="color:#f1f5f9;font-size:17px;font-weight:700;margin:0 0 4px 0">{jd_title}</p>
      {"<p style='color:#94a3b8;font-size:13px;margin:2px 0'>Level: " + level + "</p>" if level else ""}
      <p style="color:#94a3b8;font-size:13px;margin:2px 0">Location: {location}</p>
      <p style="color:#94a3b8;font-size:13px;margin:8px 0 0 0">Key Skills: <span style="color:#cbd5e1">{skills_str}</span></p>
    </div>

    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px 0">Candidate</p>
      <p style="color:#f1f5f9;font-size:16px;font-weight:700;margin:0">{name}</p>
    </div>

    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px 0">Interview Details</p>
      <p style="color:#94a3b8;margin:4px 0;font-size:13px">Date: <span style="color:#f1f5f9">{date}</span></p>
      <p style="color:#94a3b8;margin:4px 0;font-size:13px">Time: <span style="color:#f1f5f9">{time}</span></p>
      <p style="color:#94a3b8;margin:4px 0;font-size:13px">Duration: <span style="color:#f1f5f9">{duration_label}</span></p>
      <p style="color:#94a3b8;margin:4px 0;font-size:13px">Mode: <span style="color:#f1f5f9">{"Online" if mode == "online" else "In-person"}</span></p>
      {mode_client}
    </div>

    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      This is an automated notification from your recruitment partner.
    </p>
  </div>
</body>
</html>"""
        send_email(client_email, client_subject, client_html)
        logger.info(f"Interview client notification sent to {client_email} for {candidate_id}")
    else:
        logger.warning(f"No client_email on JD {jd_id} — skipping client interview notification")


_FRONTEND_BASE = "http://localhost:5173"


@celery.task(name="tasks.notification_tasks.send_offer_response_email")
def send_offer_response_email(jd_id: str, candidate_id: str, offer_token: str, joining_date: str = None, work_location: str = None):
    logger.info(f"send_offer_response_email: {candidate_id} for JD {jd_id}")
    db = get_db()

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"email": 1, "name": 1})
    if not candidate or not candidate.get("email"):
        logger.warning(f"No email for candidate {candidate_id} — skipping offer email")
        return

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    jd_title = (jd.get("structured_data", {}).get("title") or jd.get("title", "the role")) if jd else "the role"

    name = candidate.get("name", "Candidate")
    email = candidate["email"]
    response_url = f"{_FRONTEND_BASE}/offer-response/{offer_token}"

    offer_details_block = ""
    if joining_date or work_location:
        rows = ""
        if joining_date:
            rows += f'<p style="color:#94a3b8;margin:4px 0;font-size:13px">Proposed Joining Date: <strong style="color:#f1f5f9">{joining_date}</strong></p>'
        if work_location:
            rows += f'<p style="color:#94a3b8;margin:4px 0;font-size:13px">Work Location: <strong style="color:#f1f5f9">{work_location}</strong></p>'
        offer_details_block = f"""
      <div style="background:#0f172a;padding:16px;border-radius:8px;margin-bottom:20px">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 10px 0">Offer Details</p>
        {rows}
      </div>"""

    subject = f"[JobOS] Offer Letter — {jd_title}"
    html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Offer Extended</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#f1f5f9;margin:0 0 16px 0">Hi {name},</p>
      <p style="color:#94a3b8;margin:0 0 20px 0;line-height:1.6">
        Congratulations! We are pleased to extend an offer for the position of
        <strong style="color:#f1f5f9">{jd_title}</strong>.
      </p>
      {offer_details_block}
      <p style="color:#94a3b8;margin:0 0 24px 0;line-height:1.6">
        Please click the button below to confirm or respond to this offer.
      </p>
      <div style="text-align:center;margin:28px 0">
        <a href="{response_url}"
           style="display:inline-block;padding:14px 32px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:10px;font-weight:700;font-size:14px;letter-spacing:0.5px">
          View & Respond to Offer
        </a>
      </div>
      <p style="color:#64748b;font-size:12px;margin:0;text-align:center">
        Or copy this link: <span style="color:#60a5fa">{response_url}</span>
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""

    send_email(email, subject, html)
    logger.info(f"Offer response email sent to {email}")


@celery.task(name="tasks.notification_tasks.notify_offer_response")
def notify_offer_response(jd_id: str, candidate_id: str, response: str, reason: str | None):
    logger.info(f"notify_offer_response: {candidate_id} responded '{response}' for JD {jd_id}")
    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    jd_title = (jd.get("structured_data", {}).get("title") or jd.get("title", "the role")) if jd else "the role"
    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"name": 1})
    candidate_name = candidate.get("name", candidate_id) if candidate else candidate_id

    color_map = {"accept": "#4ade80", "hold": "#f59e0b", "reject": "#f87171"}
    color = color_map.get(response, "#94a3b8")
    label_map = {"accept": "ACCEPTED", "hold": "ON HOLD", "reject": "DECLINED"}
    label = label_map.get(response, response.upper())

    reason_block = ""
    if reason:
        reason_block = f"""
      <div style="background:#0f172a;padding:14px;border-radius:8px;margin-top:16px">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px 0">Reason</p>
        <p style="color:#94a3b8;margin:0;font-size:13px">{reason}</p>
      </div>"""

    recruiters = list(db.users.find({"roles": {"$in": ["recruiter", "manager", "admin"]}}, {"email": 1}))
    now = datetime.utcnow()

    notification_body = f"{candidate_name} has {response}d the offer for {jd_title}."
    for rec in recruiters:
        email = rec.get("email")
        if not email:
            continue
        db.notifications.insert_one({
            "notification_id": str(uuid.uuid4()),
            "type": "offer_response",
            "recipient_email": email,
            "recipient_roles": ["recruiter"],
            "title": f"Offer {label} — {candidate_name}",
            "body": notification_body,
            "data": {"jd_id": jd_id, "candidate_id": candidate_id, "response": response},
            "is_read": False,
            "created_at": now,
        })

        subject = f"[JobOS] Offer {label} — {candidate_name} · {jd_title}"
        html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Offer Response Received</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
        <span style="font-size:28px;font-weight:900;color:{color}">{label}</span>
      </div>
      <div style="background:#0f172a;padding:16px;border-radius:8px">
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Candidate: <strong style="color:#f1f5f9">{candidate_name}</strong></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Role: <strong style="color:#f1f5f9">{jd_title}</strong></p>
        <p style="color:#94a3b8;margin:4px 0;font-size:13px">Response: <strong style="color:{color}">{label}</strong></p>
      </div>
      {reason_block}
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""
        send_email(email, subject, html)

    logger.info(f"Offer response notifications sent to {len(recruiters)} recruiter(s)")


_STAGE_NOTIFICATIONS = {
    "shortlist": {
        "subject": "Good news! You've been shortlisted — {jd_title}",
        "body": "You have been shortlisted for <strong style=\"color:#f1f5f9\">{jd_title}</strong>. Our recruiter will be in touch soon.",
        "header": "You've Been Shortlisted",
        "color": "#4ade80",
    },
    "offer": {
        "subject": "Offer incoming — {jd_title}",
        "body": "Congratulations! You have received an offer for <strong style=\"color:#f1f5f9\">{jd_title}</strong>. Please expect a call from our team shortly.",
        "header": "Offer Extended",
        "color": "#60a5fa",
    },
    "joined": {
        "subject": "Welcome aboard! — {jd_title}",
        "body": "Congratulations on joining! Wishing you all the best in your new role at <strong style=\"color:#f1f5f9\">{jd_title}</strong>.",
        "header": "Welcome Aboard",
        "color": "#a78bfa",
    },
}

# interview_1 and interview_final are handled by send_interview_email
_SKIP_STAGES = {"interview_1", "interview_final"}


@celery.task(name="tasks.notification_tasks.send_stage_notification")
def send_stage_notification(candidate_id: str, jd_id: str, stage: str):
    """Send candidate email when pipeline stage changes (except interview stages)."""
    if stage in _SKIP_STAGES:
        return

    cfg = _STAGE_NOTIFICATIONS.get(stage)
    if not cfg:
        return

    db = get_db()
    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"email": 1, "name": 1})
    if not candidate or not candidate.get("email"):
        logger.warning(f"No email for candidate {candidate_id} — skipping stage notification")
        return

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    jd_title = (jd.get("structured_data", {}).get("title") or jd.get("title", "the role")) if jd else "the role"

    name = candidate.get("name", "Candidate")
    email = candidate["email"]
    subject = cfg["subject"].format(jd_title=jd_title)
    body_html = cfg["body"].format(jd_title=jd_title)
    header = cfg["header"]
    color = cfg["color"]

    html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">{header}</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#f1f5f9;margin:0 0 16px 0">Hi {name},</p>
      <p style="color:#94a3b8;margin:0 0 20px 0;line-height:1.6">{body_html}</p>
      <div style="background:#0f172a;padding:16px;border-radius:8px;border-left:3px solid {color}">
        <p style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px 0">Role</p>
        <p style="color:#f1f5f9;margin:0;font-size:14px;font-weight:600">{jd_title}</p>
      </div>
      <p style="color:#64748b;font-size:12px;margin-top:20px">
        If you have any questions, please reply to this email or contact your recruiter.
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""

    send_email(email, subject, html)
    logger.info(f"Stage notification '{stage}' sent to {email} for candidate {candidate_id}")
