import logging
from fastapi import APIRouter, Depends, HTTPException
from auth import check_role
from utils.client_utils import get_db
from tasks.browser_tasks import post_job_to_portals

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publish", tags=["publish"])


@router.post("/browser/{jd_id}")
async def trigger_browser_post(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    """Manually re-trigger Playwright posting for a JD to all portals."""
    db = get_db()
    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    post_job_to_portals.delay(jd_id)
    return {"message": f"Portal posting triggered for {jd_id}", "jd_id": jd_id}
