import json
import logging
import os
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from auth import check_role
from utils.client_utils import get_db
from utils.gemini_utils import _call_groq, FAST_MODEL, REASON_MODEL
from utils.email_utils import send_email

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _parse_questions(raw: str) -> list:
    """Extract JSON array of question strings from Groq response."""
    text = raw.strip()
    # Strip markdown fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text.split("```")[1].split("```")[0].strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(q) for q in parsed[:5]]
        if isinstance(parsed, dict) and "questions" in parsed:
            return [str(q) for q in parsed["questions"][:5]]
    except Exception:
        pass
    # Fallback: extract numbered lines
    lines = [re.sub(r"^\d+[\.\)]\s*", "", l).strip() for l in raw.splitlines() if re.match(r"^\d+[\.\)]", l.strip())]
    return lines[:5]


def _build_assessment_email(candidate_name: str, jd_title: str, assessment_id: str) -> str:
    link = f"{FRONTEND_URL}/assessment/{assessment_id}"
    return f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Skill Assessment</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#f1f5f9;margin:0 0 16px 0">Hi {candidate_name},</p>
      <p style="color:#94a3b8;margin:0 0 20px 0;line-height:1.6">
        As part of the recruitment process for <strong style="color:#f1f5f9">{jd_title}</strong>,
        we'd like you to complete a short skill assessment. It consists of <strong style="color:#f1f5f9">5 questions</strong>
        and should take about 15–20 minutes.
      </p>
      <div style="text-align:center;margin:28px 0">
        <a href="{link}"
           style="background:#3b82f6;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;display:inline-block">
          Start Assessment
        </a>
      </div>
      <p style="color:#64748b;font-size:12px;margin:0">
        Or copy this link: <span style="color:#60a5fa">{link}</span>
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System · Do not reply to this email
    </p>
  </div>
</body>
</html>"""


# ── Generate ──────────────────────────────────────────────────────────────────

@router.post("/generate/{jd_id}/{candidate_id}")
async def generate_assessment(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"email": 1, "name": 1})
    if not candidate or not candidate.get("email"):
        raise HTTPException(status_code=404, detail="Candidate not found or has no email")

    structured = jd.get("structured_data", {})
    jd_title = structured.get("title") or jd.get("title", "the role")
    skills = structured.get("skills", [])
    responsibilities = structured.get("responsibilities", "")

    skills_str = ", ".join(skills[:10]) if skills else "general professional skills"
    prompt = f"""You are an expert technical recruiter. Generate exactly 5 skill-based assessment questions for a candidate applying for the role: {jd_title}.

Key skills required: {skills_str}
Role responsibilities: {str(responsibilities)[:500]}

Requirements:
- Questions must test practical knowledge, not just definitions
- Mix difficulty: 2 intermediate, 2 advanced, 1 situational/scenario-based
- Each question should be answerable in 3-5 sentences by a qualified candidate
- Questions must be specific to the skills listed, not generic

Respond with ONLY a JSON array of 5 question strings. No explanation, no numbering outside JSON.
Example format: ["Question 1 text?", "Question 2 text?", "Question 3 text?", "Question 4 text?", "Question 5 text?"]"""

    try:
        raw = _call_groq(FAST_MODEL, prompt, max_tokens=1024)
        questions = _parse_questions(raw)
    except Exception as e:
        logger.error(f"Groq question generation failed: {e}")
        raise HTTPException(status_code=502, detail="AI question generation failed")

    if len(questions) < 5:
        raise HTTPException(status_code=502, detail=f"AI returned only {len(questions)} questions — try again")

    assessment_id = f"ASMT-{str(uuid.uuid4())[:12].upper()}"
    now = datetime.utcnow()

    doc = {
        "assessment_id": assessment_id,
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "jd_title": jd_title,
        "questions": [{"id": i + 1, "question": q} for i, q in enumerate(questions)],
        "answers": [],
        "score": None,
        "scoring_rationale": None,
        "status": "pending",
        "sent_by": user.get("sub", "unknown"),
        "created_at": now,
        "completed_at": None,
        "attempts": [],
    }
    db.assessments.insert_one(doc)

    # Email candidate
    html = _build_assessment_email(
        candidate.get("name", "Candidate"),
        jd_title,
        assessment_id,
    )
    send_email(candidate["email"], f"[JobOS] Skill Assessment — {jd_title}", html)

    logger.info(f"Assessment {assessment_id} created for {candidate_id} / {jd_id}")
    return {"assessment_id": assessment_id, "status": "pending", "questions_count": len(questions)}


# ── Public: view questions ────────────────────────────────────────────────────

@router.get("/{assessment_id}")
async def get_assessment(assessment_id: str):
    """Public endpoint — candidate opens this via email link."""
    db = get_db()
    doc = db.assessments.find_one({"assessment_id": assessment_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {
        "assessment_id": doc["assessment_id"],
        "jd_title": doc.get("jd_title", ""),
        "status": doc["status"],
        "questions": doc["questions"],
    }


# ── Public: submit answers ────────────────────────────────────────────────────

class SubmitBody(BaseModel):
    answers: List[str]  # ordered list matching question IDs 1-5


@router.post("/{assessment_id}/submit")
async def submit_assessment(assessment_id: str, body: SubmitBody):
    """Public endpoint — candidate submits answers."""
    db = get_db()
    doc = db.assessments.find_one({"assessment_id": assessment_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")

    questions = doc.get("questions", [])
    if len(body.answers) != len(questions):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(questions)} answers, got {len(body.answers)}",
        )
    if any(not a.strip() for a in body.answers):
        raise HTTPException(status_code=400, detail="All answers must be non-empty")

    # Build Q&A pairs for scoring
    qa_pairs = "\n\n".join(
        f"Q{i+1}: {questions[i]['question']}\nA{i+1}: {body.answers[i].strip()}"
        for i in range(len(questions))
    )
    jd_title = doc.get("jd_title", "the role")

    scoring_prompt = f"""You are an expert technical interviewer scoring candidate answers for the role: {jd_title}.

{qa_pairs}

Score the candidate's answers holistically on a scale of 0 to 100, where:
- 0-40: Weak — vague, incorrect, or incomplete answers
- 41-60: Average — shows some understanding but lacks depth
- 61-80: Good — demonstrates solid knowledge with practical examples
- 81-100: Excellent — detailed, accurate, insightful answers

Respond ONLY with valid JSON in this exact format:
{{"score": <integer 0-100>, "rationale": "<2-3 sentence explanation of the score>"}}"""

    try:
        raw = _call_groq(REASON_MODEL, scoring_prompt, max_tokens=512)
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        scoring = json.loads(text)
        new_score = max(0, min(100, int(scoring.get("score", 0))))
        rationale = scoring.get("rationale", "")
    except Exception as e:
        logger.error(f"Groq scoring failed for {assessment_id}: {e}")
        raise HTTPException(status_code=502, detail="AI scoring failed — please try again")

    now = datetime.utcnow()
    answers_payload = [
        {"id": i + 1, "answer": body.answers[i].strip()}
        for i in range(len(questions))
    ]

    # PRD: keep highest score across retakes
    prev_score = doc.get("score") or 0
    best_score = max(new_score, prev_score) if doc.get("status") == "completed" else new_score

    attempt = {
        "score": new_score,
        "completed_at": now,
        "answers": answers_payload,
    }

    db.assessments.update_one(
        {"assessment_id": assessment_id},
        {
            "$set": {
                "answers": answers_payload,
                "score": best_score,
                "scoring_rationale": rationale,
                "status": "completed",
                "completed_at": now,
            },
            "$push": {"attempts": attempt},
        },
    )

    return {
        "ok": True,
        "score": best_score,
        "message": "Assessment submitted successfully",
    }


# ── Recruiter: results for one candidate ─────────────────────────────────────

@router.get("/results/{jd_id}/{candidate_id}")
async def get_results(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    doc = db.assessments.find_one(
        {"jd_id": jd_id, "candidate_id": candidate_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No assessment found for this candidate/JD")
    return doc


# ── Recruiter: all results for a JD ─────────────────────────────────────────

@router.get("/by-jd/{jd_id}")
async def get_assessments_by_jd(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    """Returns latest assessment per candidate for a given JD."""
    db = get_db()
    docs = list(db.assessments.find({"jd_id": jd_id}, {"_id": 0}).sort("created_at", -1))
    # Keep only the latest per candidate
    seen: dict = {}
    for d in docs:
        cid = d["candidate_id"]
        if cid not in seen:
            seen[cid] = {"status": d["status"], "score": d.get("score"), "assessment_id": d["assessment_id"]}
    return seen
