import os
import logging
from fastapi import APIRouter, Depends, Body, HTTPException
from auth import check_role
from utils.client_utils import get_db
from utils.unipile_utils import send_linkedin_message
from utils.linkedin_utils import generate_linkedin_post_draft

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["linkedin"])

FRONTEND_URL = os.getenv("FRONTEND_URL", os.getenv("APP_BASE_URL", "http://localhost:5173"))


@router.post("/test-dm")
async def test_dm(
    provider_id: str = Body(..., description="Unipile provider_id of the LinkedIn account to DM"),
    jd_id: str = Body(default="TEST-JD-001"),
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    """
    Test endpoint — sends a DM to a LinkedIn account via Unipile.
    Use this to verify the DM arrives and the form link opens correctly.
    """
    candidate_id = "CAN-TEST-001"
    form_url = f"{FRONTEND_URL}/apply/{jd_id}/{candidate_id}"

    message = (
        f"Hi! This is a test message from JobOS.\n\n"
        f"If you received this, Unipile DMs are working correctly.\n\n"
        f"Test form link (click to verify it opens):\n{form_url}"
    )

    result = send_linkedin_message(provider_id, message)

    if result.get("ok"):
        return {"status": "sent", "form_url": form_url, "chat_id": result.get("chat_id")}
    else:
        return {"status": "failed", "error": result.get("error")}


@router.get("/{jd_id}/post-draft")
async def get_linkedin_post_draft(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    """Return the LinkedIn post draft for a JD so the recruiter can copy-paste it."""
    db = get_db()
    jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"_id": 0})
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    draft = generate_linkedin_post_draft(jd)
    return {"jd_id": jd_id, "draft": draft}
