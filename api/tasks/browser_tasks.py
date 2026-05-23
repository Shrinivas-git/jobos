import logging
from celery_app import celery
from utils.client_utils import get_db
from utils.playwright_poster import post_to_all_portals
from utils.email_publisher import send_portal_failure_email

logger = logging.getLogger(__name__)


@celery.task(name="tasks.browser_tasks.post_job_to_portals")
def post_job_to_portals(jd_id: str):
    """
    Triggered automatically when a JD is created.
    Tries to post to all 5 portals via Playwright.
    Sends failure email to recruiter for any portal that fails.
    """
    db = get_db()
    jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"_id": 0})
    if not jd:
        logger.error(f"[BrowserTask] JD not found: {jd_id}")
        return

    title = jd.get("title", "Untitled")
    structured = jd.get("structured_data", {})

    logger.info(f"[BrowserTask] Starting portal posting for {jd_id} — {title}")

    results = post_to_all_portals(jd)

    portal_statuses = {}
    for portal, result in results.items():
        success = result["success"]
        error = result["error"]
        portal_statuses[portal] = "posted" if success else "failed"

        if not success:
            logger.warning(f"[BrowserTask] {portal} failed for {jd_id} — sending fallback email")
            send_portal_failure_email(jd_id, title, portal, error or "Unknown error", structured)

    # Save portal posting status to DB
    db.job_descriptions.update_one(
        {"jd_id": jd_id},
        {"$set": {"portal_status": portal_statuses}}
    )

    logger.info(f"[BrowserTask] Done for {jd_id}: {portal_statuses}")
    return portal_statuses
