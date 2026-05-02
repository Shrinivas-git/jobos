from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
import uuid
import logging

from auth import check_role
from utils.client_utils import get_db
from utils.email_utils import send_email
from utils.gemini_utils import _call_groq, _parse_json_response, REASON_MODEL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])


class DraftRequest(BaseModel):
    jd_id: str
    candidate_id: str


class ApproveRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id", ""))
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in doc.items()}


@router.post("/draft")
async def draft_message(
    req: DraftRequest,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": req.jd_id})
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    candidate = db.candidates.find_one({"candidate_id": req.candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if not candidate.get("email"):
        raise HTTPException(status_code=400, detail="Candidate has no email address on file")

    pool = db.candidate_pools.find_one({"jd_id": req.jd_id, "candidate_id": req.candidate_id})

    structured = jd.get("structured_data", {})
    jd_title = structured.get("title") or jd.get("title", "the role")
    jd_skills = structured.get("skills", [])
    jd_level = structured.get("level", "")
    jd_responsibilities = str(structured.get("responsibilities", ""))[:500]

    candidate_name = candidate.get("name", "there")
    candidate_skills = candidate.get("skills", [])
    candidate_exp = candidate.get("experience_years", 0)

    strengths = (pool.get("strengths") or []) if pool else []
    composite_score = (pool.get("composite_score") or 0) if pool else 0

    prompt = f"""You are a professional technical recruiter drafting an outreach email to a shortlisted candidate.

JOB DETAILS:
- Title: {jd_title}
- Level: {jd_level}
- Key Skills: {', '.join(jd_skills[:10]) if jd_skills else 'Not specified'}
- Responsibilities: {jd_responsibilities}

CANDIDATE PROFILE:
- Name: {candidate_name}
- Experience: {candidate_exp} years
- Skills: {', '.join(candidate_skills[:10]) if candidate_skills else 'Not specified'}
- Strengths for this role: {'; '.join(strengths[:3]) if strengths else 'Strong technical profile'}
- Fitment score: {composite_score:.0f}/100

Write a concise, professional outreach email. Be warm but direct. Mention 1-2 specific strengths.
Do NOT mention gaps. Use "our team" or "we" — no placeholder company names.

Return ONLY a valid JSON object with exactly these two keys:
- "subject": email subject line (under 80 characters)
- "body": complete HTML email body (use <p>, <br>, <strong> tags; no <html>/<head>/<body> wrapper)

JSON OUTPUT:"""

    try:
        text = _call_groq(REASON_MODEL, prompt, max_tokens=1024)
        parsed = _parse_json_response(text)
        subject = parsed.get("subject") or f"Exciting opportunity: {jd_title}"
        body = parsed.get("body") or (
            f"<p>Dear {candidate_name},</p>"
            f"<p>We'd love to discuss the <strong>{jd_title}</strong> role with you.</p>"
            f"<p>Please let us know your availability for a quick call.</p>"
            f"<p>Best regards,<br>The Recruitment Team</p>"
        )
    except Exception as e:
        logger.error(f"Groq draft failed: {e}")
        subject = f"Exciting opportunity: {jd_title}"
        body = (
            f"<p>Dear {candidate_name},</p>"
            f"<p>We're impressed by your profile and would love to discuss the "
            f"<strong>{jd_title}</strong> role with you.</p>"
            f"<p>Please let us know your availability for a quick call.</p>"
            f"<p>Best regards,<br>The Recruitment Team</p>"
        )

    message_id = f"MSG-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    doc = {
        "message_id": message_id,
        "jd_id": req.jd_id,
        "candidate_id": req.candidate_id,
        "candidate_email": candidate["email"],
        "candidate_name": candidate_name,
        "jd_title": jd_title,
        "subject": subject,
        "body": body,
        "status": "draft",
        "created_by": user.get("sub", "unknown"),
        "created_at": now,
        "approved_at": None,
        "approved_by": None,
        "sent_at": None,
        "edited": False,
    }

    db.crm_messages.insert_one(doc)
    return _serialize(doc)


@router.get("/messages")
async def list_messages(
    jd_id: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    query: dict = {}
    if jd_id:
        query["jd_id"] = jd_id
    if status:
        query["status"] = status
    docs = list(db.crm_messages.find(query).sort("created_at", -1).limit(200))
    return [_serialize(d) for d in docs]


@router.get("/messages/{message_id}")
async def get_message(
    message_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    doc = db.crm_messages.find_one({"message_id": message_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Message not found")
    return _serialize(doc)


@router.post("/messages/{message_id}/approve")
async def approve_and_send(
    message_id: str,
    req: ApproveRequest,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    doc = db.crm_messages.find_one({"message_id": message_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Message not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail=f"Message already {doc.get('status')}")

    subject = req.subject if req.subject else doc["subject"]
    body = req.body if req.body else doc["body"]
    now = datetime.utcnow()

    ok = send_email(doc["candidate_email"], subject, body)

    db.crm_messages.update_one(
        {"message_id": message_id},
        {"$set": {
            "subject": subject,
            "body": body,
            "edited": bool(req.subject or req.body),
            "status": "sent" if ok else "failed",
            "approved_at": now,
            "approved_by": user.get("sub", "unknown"),
            "sent_at": now if ok else None,
        }},
    )

    updated = db.crm_messages.find_one({"message_id": message_id})
    return _serialize(updated)
