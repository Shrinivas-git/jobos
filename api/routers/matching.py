from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from auth import check_role
from tasks.matching_tasks import run_matching

router = APIRouter(prefix="/matching", tags=["matching"])

class MatchingResultResponse(BaseModel):
    jd_id: str
    candidate_id: str
    match_score: float # Cosine similarity
    fitment_score: Optional[float] = None # Pass 2 reasoning score
    composite_score: Optional[float] = None
    completeness_score: Optional[float] = None
    reasoning: Optional[str] = None
    strengths: Optional[List[str]] = None
    gaps: Optional[List[str]] = None
    recommendation: Optional[str] = None
    rank: int
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

@router.post("/run/{jd_id}")
async def trigger_matching(jd_id: str, user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    """Triggers the full matching process (Pass 1 & Pass 2) for a specific JD."""
    run_matching.delay(jd_id)
    return {"message": f"Matching process triggered for {jd_id}", "jd_id": jd_id}

@router.post("/pass2/{jd_id}")
async def trigger_pass2(jd_id: str, user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    """Triggers only the Pass 2 (Intelligence Layer) for existing Pass 1 results."""
    from tasks.matching_tasks import run_pass_2
    run_pass_2.delay(jd_id)
    return {"message": f"Pass 2 reasoning triggered for {jd_id}", "jd_id": jd_id}

@router.get("/results/{jd_id}", response_model=List[MatchingResultResponse])
async def get_matching_results(jd_id: str, user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    """Retrieves current matching results for a JD."""
    from utils.client_utils import get_db
    db = get_db()
    results = list(db.candidate_pools.find({"jd_id": jd_id}, {"_id": 0}).sort("rank", 1))
    return results


class CandidateAction(BaseModel):
    action: str  # "shortlist" | "reject"
    reason: Optional[str] = None


@router.post("/action/{jd_id}/{candidate_id}")
async def record_candidate_action(
    jd_id: str,
    candidate_id: str,
    body: CandidateAction,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    if body.action not in ("shortlist", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'shortlist' or 'reject'")
    if body.action == "reject" and not body.reason:
        raise HTTPException(status_code=400, detail="Rejection requires a reason")
    from utils.client_utils import get_db
    db = get_db()
    db.candidate_pools.update_one(
        {"jd_id": jd_id, "candidate_id": candidate_id},
        {"$set": {
            "status": body.action + "ed",
            "action_reason": body.reason,
            "actioned_at": datetime.utcnow().isoformat(),
            "actioned_by": user.get("sub", "unknown"),
            "updated_at": datetime.utcnow(),
        }},
    )
    return {"ok": True}


@router.get("/pipeline-stats/{jd_id}")
async def get_pipeline_stats(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    from utils.client_utils import get_db
    db = get_db()
    docs = list(db.candidate_pools.find({"jd_id": jd_id}, {"status": 1}))
    total = len(docs)
    shortlisted = sum(1 for d in docs if d.get("status") == "shortlisted")
    rejected = sum(1 for d in docs if d.get("status") == "rejected")
    pending = total - shortlisted - rejected
    return {"total": total, "shortlisted": shortlisted, "rejected": rejected, "pending": pending}
