import logging
import os
from datetime import datetime, timezone

from celery_app import celery
from utils.client_utils import get_db
from utils.unipile_utils import send_linkedin_message, send_linkedin_connection_request, get_linkedin_relation_type
from utils.email_utils import send_email

logger = logging.getLogger(__name__)

UNIPILE_DSN = os.getenv("UNIPILE_DSN", "api43.unipile.com:17352")
UNIPILE_BASE = f"https://{UNIPILE_DSN}/api/v1"
RECRUITER_EMAIL = os.getenv("RECRUITER_EMAIL", "radhika@refiningskills.org")


def _fetch_job_applicants(linkedin_job_id: str) -> tuple[list, str | None]:
    """Returns (applicants_list, error_message). error_message is None on success."""
    import requests
    api_key = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")
    if not api_key or not account_id:
        return [], "Unipile credentials not configured (UNIPILE_API_KEY / UNIPILE_ACCOUNT_ID missing)"
    try:
        resp = requests.get(
            f"{UNIPILE_BASE}/linkedin/jobs/{linkedin_job_id}/applicants",
            params={"account_id": account_id},
            headers={"X-API-KEY": api_key},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("items", []), None
    except Exception as e:
        return [], str(e)


def _send_failure_email(jd_id: str, job_title: str, portal: str, error: str):
    subject = f"[JobOS] Action needed — {portal} automation failed for: {job_title}"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px">
      <h2 style="color:#dc2626">Automation Failed — Manual Action Required</h2>
      <p>The automated {portal} check failed for the following job. Please review applicants manually.</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0">
        <tr><td style="padding:8px;color:#6b7280;width:140px">Job Title</td><td style="padding:8px;font-weight:600">{job_title}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Job ID</td><td style="padding:8px">{jd_id}</td></tr>
        <tr><td style="padding:8px;color:#6b7280">Portal</td><td style="padding:8px">{portal}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px;color:#6b7280">Error</td><td style="padding:8px;color:#dc2626;font-size:13px">{error}</td></tr>
        <tr><td style="padding:8px;color:#6b7280">Time</td><td style="padding:8px">{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</td></tr>
      </table>
      <p style="color:#6b7280;font-size:13px">Please check the {portal} page for {COMPANY_NAME} manually and process any new applicants.</p>
    </div>
    """
    send_email(RECRUITER_EMAIL, subject, html)


@celery.task(name="tasks.linkedin_tasks.source_linkedin_outbound")
def source_linkedin_outbound(jd_id: str, max_results: int = 10):
    """
    Triggered on JD upload/create.
    Searches LinkedIn via Unipile, sends a connection request to each matching profile.
    DMs are sent later by poll_linkedin_connections once a request is accepted.
    Rate-limited to 5 connection requests per call (~100-200/week LinkedIn limit).
    """
    from utils.unipile_utils import fetch_linkedin_profiles
    from datetime import datetime, timezone
    import uuid

    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        logger.error(f"[LinkedIn Outbound] JD not found: {jd_id}")
        return

    job_title = jd.get("title", "a role")
    company = jd.get("company") or jd.get("structured_data", {}).get("company", "")

    # TEST MODE guard — only send to Shrinivas until fully validated
    TEST_MODE = os.getenv("LINKEDIN_OUTBOUND_TEST_MODE", "true").lower() == "true"
    TEST_PROVIDER_ID = "ACoAAEnrbxIB0fMAikP7yjMwtBzsrB7sKfKi3v0"
    TEST_NAME = "Shrinivas"

    if TEST_MODE:
        profiles = [{"provider_id": TEST_PROVIDER_ID, "name": TEST_NAME}]
        logger.info(f"[LinkedIn Outbound] TEST MODE — using test profile only")
    else:
        profiles = fetch_linkedin_profiles(jd, max_results=max_results)
        logger.info(f"[LinkedIn Outbound] {jd_id}: found {len(profiles)} profiles")

    sent = 0
    BATCH_LIMIT = 3  # max connection requests per trigger to stay within LinkedIn limits

    for profile in profiles:
        if sent >= BATCH_LIMIT:
            break

        provider_id = profile.get("provider_id") or profile.get("id", "")
        name = profile.get("name") or profile.get("full_name") or "there"
        if not provider_id:
            continue

        # Skip if already sent a connection request for this jd+profile
        already = db.linkedin_outbound.find_one({"jd_id": jd_id, "provider_id": provider_id})
        if already:
            continue

        candidate_id = f"CAN-LI-{uuid.uuid4().hex[:8]}"

        # Save candidate record so form link is valid when DM is eventually sent
        db.candidates.insert_one({
            "candidate_id": candidate_id,
            "name": name,
            "email": f"{candidate_id}@jobos.internal",
            "jd_id": jd_id,
            "source": "linkedin_outbound",
            "linkedin_provider_id": provider_id,
            "linkedin_outbound_status": "connection_sent",
            "status": "sourced",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

        # Track outbound state separately for polling
        db.linkedin_outbound.insert_one({
            "jd_id": jd_id,
            "candidate_id": candidate_id,
            "provider_id": provider_id,
            "name": name,
            "job_title": job_title,
            "company": company,
            "linkedin_outbound_status": "connection_sent",
            "connection_sent_at": datetime.now(timezone.utc),
            "dm_sent_at": None,
        })

        result = send_linkedin_connection_request(provider_id)
        if result.get("ok"):
            logger.info(f"[LinkedIn Outbound] Connection request sent to {name} ({provider_id})")
            sent += 1
        else:
            logger.warning(f"[LinkedIn Outbound] Connection request failed for {name}: {result.get('error')}")
            db.linkedin_outbound.update_one(
                {"jd_id": jd_id, "provider_id": provider_id},
                {"$set": {"linkedin_outbound_status": "connection_failed"}}
            )
            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {"$set": {"linkedin_outbound_status": "connection_failed"}}
            )

    logger.info(f"[LinkedIn Outbound] {jd_id}: sent {sent} connection request(s)")
    return {"jd_id": jd_id, "connection_requests_sent": sent, "test_mode": TEST_MODE}


@celery.task(name="tasks.linkedin_tasks.poll_linkedin_connections")
def poll_linkedin_connections():
    """
    Runs every 4 hours. Checks whether pending LinkedIn connection requests have been accepted.
    On acceptance → sends DM with form link and updates state to dm_sent.
    Expires requests older than 7 days that are still pending.
    """
    from datetime import datetime, timezone, timedelta

    db = get_db()
    frontend_url = os.getenv("FRONTEND_URL", os.getenv("APP_BASE_URL", "http://localhost:5173"))

    pending = list(db.linkedin_outbound.find({"linkedin_outbound_status": "connection_sent"}))
    logger.info(f"[LinkedIn Connections Poll] Checking {len(pending)} pending connection requests")

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    for record in pending:
        provider_id = record["provider_id"]
        jd_id = record["jd_id"]
        candidate_id = record["candidate_id"]
        name = record.get("name", "there")
        job_title = record.get("job_title", "a role")
        company = record.get("company", "")
        sent_at = record.get("connection_sent_at")

        # Expire requests older than 7 days
        if sent_at and sent_at.replace(tzinfo=timezone.utc) < cutoff:
            db.linkedin_outbound.update_one(
                {"_id": record["_id"]},
                {"$set": {"linkedin_outbound_status": "connection_expired"}}
            )
            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {"$set": {"linkedin_outbound_status": "connection_expired", "updated_at": datetime.now(timezone.utc)}}
            )
            logger.info(f"[LinkedIn Connections Poll] Expired request for {name} ({provider_id})")
            continue

        relation_type = get_linkedin_relation_type(provider_id)
        if relation_type != "CONNECTED":
            logger.debug(f"[LinkedIn Connections Poll] {name}: still {relation_type}")
            continue

        # Skip if a DM was already sent to this person for any JD
        already_dmed = db.linkedin_outbound.find_one({
            "provider_id": provider_id,
            "linkedin_outbound_status": "dm_sent",
        })
        if already_dmed:
            db.linkedin_outbound.update_one(
                {"_id": record["_id"]},
                {"$set": {"linkedin_outbound_status": "dm_skipped_already_sent"}}
            )
            logger.info(f"[LinkedIn Connections Poll] Skipping DM to {name} — already sent for JD {already_dmed['jd_id']}")
            continue

        # Connection accepted — send DM with form link
        form_url = f"{frontend_url}/apply/{jd_id}/{candidate_id}"
        first_name = name.split()[0] if name and name != "there" else "there"
        at_company = f" at {company}" if company else ""
        message = (
            f"Hi {first_name}, thanks for connecting! We have an opening for a {job_title} role{at_company} "
            f"that looks like a strong match for your background. "
            f"If you're interested, here's a short 2-minute form:\n{form_url}"
        )

        result = send_linkedin_message(provider_id, message)
        now = datetime.now(timezone.utc)

        if result.get("ok"):
            db.linkedin_outbound.update_one(
                {"_id": record["_id"]},
                {"$set": {"linkedin_outbound_status": "dm_sent", "dm_sent_at": now}}
            )
            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {"$set": {
                    "linkedin_outbound_status": "dm_sent",
                    "status": "outbound_dm_sent",
                    "updated_at": now,
                }}
            )
            logger.info(f"[LinkedIn Connections Poll] DM sent to {name} ({provider_id}) for {jd_id}")
        else:
            logger.warning(f"[LinkedIn Connections Poll] DM failed for {name}: {result.get('error')}")


@celery.task(name="tasks.linkedin_tasks.poll_linkedin_applicants")
def poll_linkedin_applicants():
    """
    Runs every 4 hours. For each active JD with a linkedin_job_id:
    - Fetches applicants from Unipile
    - Saves new ones as candidates
    - Sends form link DM to those without a resume
    """
    db = get_db()
    frontend_url = os.getenv("FRONTEND_URL", os.getenv("APP_BASE_URL", "http://localhost:5173"))

    jds = list(db.job_descriptions.find(
        {"linkedin_job_id": {"$exists": True, "$ne": None}, "status": {"$nin": ["closed", "cancelled"]}},
        {"jd_id": 1, "title": 1, "linkedin_job_id": 1}
    ))

    logger.info(f"[LinkedIn Poll] Checking {len(jds)} JDs with LinkedIn job IDs")

    for jd in jds:
        jd_id = jd["jd_id"]
        linkedin_job_id = jd["linkedin_job_id"]
        job_title = jd.get("title", "a role")
        company = jd.get("company") or jd.get("structured_data", {}).get("company", "")

        applicants, error = _fetch_job_applicants(linkedin_job_id)
        if error:
            logger.error(f"[LinkedIn Poll] {jd_id}: fetch failed — {error}")
            _send_failure_email(jd_id, job_title, "LinkedIn", error)
            continue
        logger.info(f"[LinkedIn Poll] {jd_id}: {len(applicants)} applicants found")

        for applicant in applicants:
            provider_id = applicant.get("provider_id") or applicant.get("id", "")
            name = applicant.get("name") or applicant.get("full_name", "there")
            email = (applicant.get("email") or "").strip().lower()
            has_resume = bool(applicant.get("resume") or applicant.get("resume_url") or applicant.get("cv"))

            if not provider_id:
                continue

            # Skip already processed applicants
            already_seen = db.linkedin_applicants.find_one({
                "linkedin_job_id": linkedin_job_id,
                "provider_id": provider_id,
            })
            if already_seen:
                continue

            # Mark as seen immediately to avoid duplicate processing
            db.linkedin_applicants.insert_one({
                "linkedin_job_id": linkedin_job_id,
                "jd_id": jd_id,
                "provider_id": provider_id,
                "name": name,
                "email": email,
                "has_resume": has_resume,
                "processed_at": datetime.now(timezone.utc),
            })

            if has_resume:
                # Save as candidate and trigger matching
                candidate_id = f"CAN-LI-{provider_id[:8]}"
                existing = db.candidates.find_one({"candidate_id": candidate_id})
                if not existing:
                    db.candidates.insert_one({
                        "candidate_id": candidate_id,
                        "name": name,
                        "email": email,
                        "jd_id": jd_id,
                        "source": "linkedin",
                        "linkedin_provider_id": provider_id,
                        "status": "received",
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    })
                    logger.info(f"[LinkedIn Poll] Saved candidate {candidate_id} — {name}")
            else:
                # No resume — send form link via LinkedIn DM
                candidate_id = f"CAN-LI-{provider_id[:8]}"
                if not db.candidates.find_one({"candidate_id": candidate_id}):
                    db.candidates.insert_one({
                        "candidate_id": candidate_id,
                        "name": name,
                        "email": email,
                        "jd_id": jd_id,
                        "source": "linkedin",
                        "linkedin_provider_id": provider_id,
                        "status": "form_pending",
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    })

                form_url = f"{frontend_url}/apply/{jd_id}/{candidate_id}"
                first_name = name.split()[0] if name and name != "there" else "there"
                at_company = f" at {company}" if company else ""
                message = (
                    f"Hi {first_name}, thanks for applying for the {job_title} role{at_company}! "
                    f"To process your application, please fill out this short form (takes 2 mins):\n{form_url}"
                )
                result = send_linkedin_message(provider_id, message)
                if result.get("ok"):
                    logger.info(f"[LinkedIn Poll] Sent form link to {name} ({provider_id})")
                    db.linkedin_applicants.update_one(
                        {"provider_id": provider_id, "linkedin_job_id": linkedin_job_id},
                        {"$set": {"form_link_sent": True, "form_link_sent_at": datetime.now(timezone.utc)}}
                    )
                else:
                    logger.warning(f"[LinkedIn Poll] Failed to send DM to {name}: {result.get('error')}")
