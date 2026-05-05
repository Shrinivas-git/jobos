from fastapi import APIRouter, Depends, HTTPException
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel
from auth import check_role
from tasks.matching_tasks import run_matching
from utils.client_utils import get_db
from routers.pipeline import upsert_initial_stage

router = APIRouter(prefix="/matching", tags=["matching"])

class MatchingResultResponse(BaseModel):
    jd_id: str
    candidate_id: str
    match_score: float # Cosine similarity
    fitment_score: Optional[float] = None # Pass 2 reasoning score
    composite_score: Optional[float] = None
    completeness_score: Optional[float] = None
    context_bonus: float = 0.0 # Contextual match bonus
    reasoning: Optional[str] = None
    strengths: Optional[List[str]] = None
    gaps: Optional[List[str]] = None
    recommendation: Optional[str] = None
    rank: int
    status: str
    source: str
    company_types: List[str] = [] # From candidate profile
    avg_team_size: str = "Unknown" # From candidate profile
    role_type: str = "Unknown" # From candidate profile
    preferred_company_type: List[str] = [] # From JD preferences
    preferred_team_size: str = "Any" # From JD preferences
    jd_role_type: str = "Any" # From JD preferences
    scoring_factors: Optional[List[dict]] = None
    hard_filters_passed: Optional[bool] = None
    hard_filter_failures: Optional[List[str]] = None
    role_level_detected: Optional[str] = None
    role_level_match: Optional[str] = None
    tool_currency: Optional[str] = None
    cv_narrative_style: Optional[str] = None
    availability_signal: Optional[str] = None
    rare_assets: Optional[List[str]] = None
    self_reported_unverified: Optional[List[str]] = None
    interview_flags: Optional[List[str]] = None
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
    """Retrieves current matching results for a JD, enriched with candidate and JD contextual data."""
    db = get_db()
    results = list(db.candidate_pools.find({"jd_id": jd_id}, {"_id": 0}).sort("rank", 1))

    # Fetch JD contextual preferences (nested in structured_data)
    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    structured = jd.get("structured_data", {}) if jd else {}
    jd_company_types = structured.get("preferred_company_type", [])
    jd_team_size = structured.get("preferred_team_size", "Any")
    jd_role_type = structured.get("role_type", "Any")

    # Enrich with candidate contextual data and JD preferences
    enriched_results = []
    for result in results:
        candidate = db.candidates.find_one({"candidate_id": result.get("candidate_id")})
        if candidate:
            result["company_types"] = candidate.get("company_types", [])
            result["avg_team_size"] = candidate.get("avg_team_size", "Unknown")
            result["role_type"] = candidate.get("role_type", "Unknown")
        # Add JD contextual preferences
        result["preferred_company_type"] = jd_company_types
        result["preferred_team_size"] = jd_team_size
        result["jd_role_type"] = jd_role_type
        enriched_results.append(result)

    return enriched_results


class CandidateAction(BaseModel):
    action: Literal["shortlist", "reject"]
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
    if body.action == "shortlist":
        upsert_initial_stage(db, jd_id, candidate_id, "shortlist")
    if body.action == "reject":
        rejected = list(db.candidate_pools.find(
            {"jd_id": jd_id, "status": "rejected"},
            {"action_reason": 1}
        ))
        reason_counts: dict = {}
        for r in rejected:
            rsn = r.get("action_reason") or "Unknown"
            reason_counts[rsn] = reason_counts.get(rsn, 0) + 1
        flagged = next((rsn for rsn, cnt in reason_counts.items() if cnt >= 3), None)
        if flagged:
            db.job_descriptions.update_one(
                {"jd_id": jd_id},
                {"$set": {"quality_flag": flagged, "quality_flag_at": datetime.utcnow()}}
            )
    return {"ok": True}


@router.get("/pipeline-stats/{jd_id}")
async def get_pipeline_stats(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    docs = list(db.candidate_pools.find({"jd_id": jd_id}, {"status": 1}))
    total = len(docs)
    shortlisted = sum(1 for d in docs if d.get("status") == "shortlisted")
    rejected = sum(1 for d in docs if d.get("status") == "rejected")
    pending = total - shortlisted - rejected
    return {"total": total, "shortlisted": shortlisted, "rejected": rejected, "pending": pending}
