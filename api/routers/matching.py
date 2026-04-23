from fastapi import APIRouter, Depends, HTTPException
from auth import check_role
from tasks.matching_tasks import run_matching

router = APIRouter(prefix="/matching", tags=["matching"])

@router.post("/run/{jd_id}")
async def trigger_matching(jd_id: str, user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    """Triggers the semantic matching process for a specific JD."""
    run_matching.delay(jd_id)
    return {"message": f"Matching process triggered for {jd_id}", "jd_id": jd_id}

@router.get("/results/{jd_id}")
async def get_matching_results(jd_id: str, user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    """Retrieves current matching results for a JD."""
    from utils.client_utils import get_db
    db = get_db()
    results = list(db.candidate_pools.find({"jd_id": jd_id}, {"_id": 0}).sort("rank", 1))
    return results
