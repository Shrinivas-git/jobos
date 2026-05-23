import logging
import re
from datetime import datetime, timezone

from celery_app import celery
from utils.client_utils import get_db
from utils.internshala_utils import _load_session, fetch_posted_jobs, fetch_applicants

logger = logging.getLogger(__name__)


def _match_jd(db, job: dict):
    """Find the JobOS JD for an Internshala job, backfilling internshala_job_id by title."""
    job_id = job["job_id"]
    jd = db.job_descriptions.find_one({"internshala_job_id": job_id})
    if jd:
        return jd

    title = job.get("title", "").strip()
    if not title:
        return None
    jd = db.job_descriptions.find_one({
        "title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}
    })
    if jd:
        db.job_descriptions.update_one(
            {"jd_id": jd["jd_id"]},
            {"$set": {"internshala_job_id": job_id}},
        )
        logger.info("[Internshala Poll] Linked job %s -> %s (by title)", job_id, jd["jd_id"])
    return jd


@celery.task(name="tasks.internshala_tasks.poll_internshala_applicants")
def poll_internshala_applicants():
    """
    Runs every 4 hours. Reads applicants from each posted Internshala job and
    imports new ones as candidates in their matching JD pipeline.
    Internshala does not expose applicant email, so phone is stored for outreach.
    """
    db = get_db()
    s = _load_session()
    if not s:
        logger.warning("[Internshala Poll] No session — skipping")
        return {"error": "no_session"}

    jobs = fetch_posted_jobs(s)
    logger.info("[Internshala Poll] Found %d posted jobs", len(jobs))

    imported = 0
    for job in jobs:
        if job.get("applicant_count", 0) <= 0:
            continue

        jd = _match_jd(db, job)
        if not jd:
            logger.info("[Internshala Poll] No matching JD for '%s' (job %s) — skipping",
                        job.get("title"), job["job_id"])
            continue

        jd_id = jd["jd_id"]
        records = fetch_applicants(s, job["job_id"])
        logger.info("[Internshala Poll] %s: %d applicants", jd_id, len(records))

        for rec in records:
            application_id = rec.get("id")
            if not application_id:
                continue
            candidate_id = f"CAN-IN-{application_id}"
            if db.candidates.find_one({"candidate_id": candidate_id}):
                continue

            name = rec.get("full_name") or f"{rec.get('first_name','')} {rec.get('last_name','')}".strip() or "Unknown"
            phone = rec.get("phone_primary", "")
            country_code = rec.get("country_code", "")
            skills = list((rec.get("student_skills") or {}).keys())

            db.candidates.insert_one({
                "candidate_id": candidate_id,
                "name": name,
                "email": f"{candidate_id}@jobos.internal",  # Internshala hides email
                "phone": f"{country_code}{phone}".strip(),
                "jd_id": jd_id,
                "source": "internshala",
                "status": "received",
                "current_city": rec.get("current_city", ""),
                "skills": skills,
                "total_experience": rec.get("student_total_experience", ""),
                "cover_letter": rec.get("cover_letter", ""),
                "internshala_application_id": application_id,
                "internshala_student_id": rec.get("student_id"),
                "applied_at": rec.get("applied_at"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            imported += 1
            logger.info("[Internshala Poll] Imported %s — %s (%s)", candidate_id, name, jd_id)

    logger.info("[Internshala Poll] Done — imported %d new candidate(s)", imported)
    return {"jobs": len(jobs), "imported": imported}
