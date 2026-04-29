import logging
from fastapi import APIRouter, HTTPException
from utils.client_utils import get_db
from tasks.feedback_tasks import generate_and_store_feedback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/generate/{candidate_id}/{jd_id}", status_code=202)
async def trigger_feedback_generation(candidate_id: str, jd_id: str):
    """Queue Groq feedback generation for a rejected candidate. Call when recruiter clicks Reject."""
    db = get_db()
    if not db.candidates.find_one({"candidate_id": candidate_id}):
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not db.job_descriptions.find_one({"jd_id": jd_id}):
        raise HTTPException(status_code=404, detail="JD not found")

    generate_and_store_feedback.delay(candidate_id, jd_id)
    return {"status": "queued", "candidate_id": candidate_id, "jd_id": jd_id}


@router.get("/{candidate_id}")
async def get_candidate_feedback(candidate_id: str):
    """Return all feedback records for a candidate, newest first."""
    db = get_db()
    records = list(
        db.candidate_feedback
        .find({"candidate_id": candidate_id}, {"_id": 0})
        .sort("generated_at", -1)
    )
    return {"candidate_id": candidate_id, "feedback": records, "count": len(records)}
