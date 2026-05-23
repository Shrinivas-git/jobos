from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
from auth import check_role
from utils.client_utils import get_db
from utils.google_forms_utils import save_video_file, get_video_storage_path, get_sheet_responses, find_video_in_drive, download_video_from_drive
from utils.storage_utils import save_resume_file
from utils.resume_utils import extract_text_from_file
from utils.email_utils import send_email
from tasks.video_analysis_tasks import analyze_video_resume as analyze_video_task
from tasks.jd_tasks import process_jd_task
import uuid
import os
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forms", tags=["forms"])

def _extract_drive_file_id(url: str) -> str | None:
    """Extract Google Drive file ID from various URL formats."""
    if not url:
        return None
    # Match ?id=FILE_ID or /d/FILE_ID or /file/d/FILE_ID
    patterns = [
        r"[?&]id=([a-zA-Z0-9_-]{25,})",
        r"/d/([a-zA-Z0-9_-]{25,})",
        r"/file/d/([a-zA-Z0-9_-]{25,})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    # If it looks like a raw file ID (no slashes/dots)
    if re.match(r"^[a-zA-Z0-9_-]{25,}$", url.strip()):
        return url.strip()
    return None

class FormResponseData(BaseModel):
    jd_id: str
    candidate_id: str
    aadhar: Optional[str] = None
    linkedin_url: Optional[str] = None
    alternate_phone: Optional[str] = None
    telegram_handle: Optional[str] = None

class FormResponseModel(BaseModel):
    response_id: str
    candidate_id: str
    jd_id: str
    aadhar: Optional[str] = None
    linkedin_url: Optional[str] = None
    alternate_phone: Optional[str] = None
    telegram_handle: Optional[str] = None
    video_resume_path: Optional[str] = None
    video_analysis: Optional[dict] = None
    submitted_at: datetime
    created_at: datetime

@router.post("/open-submit")
async def open_submit_form(
    jd_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    source: str = Form(default="direct"),
    resume_file: UploadFile = File(...),
    linkedin_url: Optional[str] = Form(None),
    current_ctc: Optional[str] = Form(None),
    expected_ctc: Optional[str] = Form(None),
    notice_period: Optional[str] = Form(None),
):
    """
    Open application form — for external candidates from Indeed, Internshala etc.
    Creates candidate record + triggers matching pipeline.
    No auth required — public endpoint.
    """
    db = get_db()

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        raise HTTPException(status_code=404, detail="Job not found")

    email = email.strip().lower()

    # De-duplicate by email + jd_id
    existing = db.candidates.find_one({"email": email, "jd_id": jd_id})
    if existing:
        return {"status": "duplicate", "message": "Application already received for this role"}

    candidate_id = f"CAN-{jd_id.split('-')[1][:8] if '-' in jd_id else 'EXT'}-{uuid.uuid4().hex[:8]}"

    # Save resume
    resume_bytes = await resume_file.read()
    resume_path = save_resume_file(candidate_id, resume_file.filename or "resume.pdf", resume_bytes)
    resume_text = extract_text_from_file(resume_path) if resume_path else ""

    candidate_doc = {
        "candidate_id": candidate_id,
        "name": name.strip(),
        "email": email,
        "phone": phone.strip(),
        "jd_id": jd_id,
        "source": source,
        "status": "received",
        "resume_text": resume_text,
        "resume_path": resume_path,
        "linkedin_url": linkedin_url.strip() if linkedin_url else None,
        "current_ctc": current_ctc.strip() if current_ctc else None,
        "expected_ctc": expected_ctc.strip() if expected_ctc else None,
        "notice_period": notice_period or None,
        "skills": [],
        "experience_years": 0,
        "location": "",
        "headline": "",
        "file_paths": [resume_path] if resume_path else [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    db.candidates.insert_one(candidate_doc)
    logger.info(f"[OpenSubmit] Created candidate {candidate_id} — {name} from {source} for {jd_id}")

    # Trigger matching pipeline
    process_jd_task.delay(jd_id)

    return {"status": "received", "candidate_id": candidate_id}


@router.post("/submit")
async def submit_form(
    jd_id: str = Form(...),
    candidate_id: str = Form(...),
    aadhar: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    alternate_phone: Optional[str] = Form(None),
    telegram_handle: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
):
    """
    Submit form with video resume
    Called by candidate after shortlisting
    """
    try:
        db = get_db()

        # Validate candidate exists
        candidate = db.candidates.find_one({"candidate_id": candidate_id})
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Validate JD exists
        jd = db.job_descriptions.find_one({"jd_id": jd_id})
        if not jd:
            raise HTTPException(status_code=404, detail="JD not found")

        # Save resume file if provided
        resume_path = None
        resume_text = ""
        if resume_file:
            resume_bytes = await resume_file.read()
            resume_path = save_resume_file(candidate_id, resume_file.filename or "resume.pdf", resume_bytes)
            resume_text = extract_text_from_file(resume_path) if resume_path else ""

        # Save video file if provided
        video_path = None
        if video_file:
            video_data = await video_file.read()
            video_path = save_video_file(video_data, candidate_id, jd_id)
            if not video_path:
                raise HTTPException(status_code=500, detail="Failed to save video")

        # Create form response record
        response_id = f"FORM-{datetime.utcnow().timestamp()}"
        form_response = {
            "response_id": response_id,
            "jd_id": jd_id,
            "candidate_id": candidate_id,
            "aadhar": aadhar.strip() if aadhar else None,
            "email": email.strip().lower() if email else None,
            "linkedin_url": linkedin_url.strip() if linkedin_url else None,
            "alternate_phone": alternate_phone.strip() if alternate_phone else None,
            "telegram_handle": telegram_handle.strip() if telegram_handle else None,
            "resume_path": resume_path,
            "video_resume_path": video_path,
            "video_analysis": None,
            "status": "submitted",
            "submitted_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        db.form_responses.insert_one(form_response)
        form_response.pop("_id", None)  # remove ObjectId added by MongoDB

        # Update candidate profile with form response ID
        candidate_update = {
            "form_response_id": response_id,
            "resume_path": resume_path,
            "resume_text": resume_text if resume_text else None,
            "file_paths": [resume_path] if resume_path else [],
            "telegram_handle": telegram_handle.strip() if telegram_handle else None,
            "alternate_phone": alternate_phone.strip() if alternate_phone else None,
            "updated_at": datetime.utcnow()
        }
        # Only set email if candidate doesn't already have one
        if email and not candidate.get("email"):
            candidate_update["email"] = email.strip().lower()

        db.candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": candidate_update}
        )

        # Update pipeline response tracking
        db.pipeline_stages.update_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"$set": {
                "response_tracking.form_submitted.status": "submitted",
                "response_tracking.form_submitted.submitted_at": datetime.utcnow(),
                "response_tracking.form_submitted.reminder_count": 0,
                "response_tracking.form_submitted.last_reminder_at": None,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )

        # Trigger resume extraction/metadata pipeline if resume provided
        if resume_path:
            from tasks.resume_tasks import process_resume_task
            process_resume_task.delay(candidate_id, resume_path, source="linkedin_form")

        # Trigger async video analysis if video provided
        if video_path:
            analyze_video_task.delay(candidate_id, jd_id, video_path)

        # Trigger notification to recruiter
        from tasks.notification_tasks import notify_form_submitted
        notify_form_submitted.delay(jd_id, candidate_id, form_response)

        return {
            "status": "success",
            "response_id": response_id,
            "message": "Form submitted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error submitting form: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/responses/{jd_id}", response_model=List[FormResponseModel])
async def get_form_responses(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """Get all form responses for a JD"""
    try:
        db = get_db()
        responses = list(db.form_responses.find({"jd_id": jd_id}, {"_id": 0}))
        return responses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/response/{jd_id}/{candidate_id}/public")
async def check_form_response_public(jd_id: str, candidate_id: str):
    """Public endpoint — returns 200 if already submitted, 404 if not."""
    db = get_db()
    exists = db.form_responses.find_one({"jd_id": jd_id, "candidate_id": candidate_id}, {"_id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="Not submitted")
    return {"submitted": True}


@router.get("/response/{jd_id}/{candidate_id}", response_model=FormResponseModel)
async def get_form_response(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """Get specific form response"""
    try:
        db = get_db()
        response = db.form_responses.find_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"_id": 0}
        )
        if not response:
            raise HTTPException(status_code=404, detail="Form response not found")
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{jd_id}")
async def get_form_submission_stats(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """Get form submission stats for a JD"""
    try:
        db = get_db()
        total = db.form_responses.count_documents({"jd_id": jd_id})
        submitted = db.form_responses.count_documents({"jd_id": jd_id, "status": "submitted"})
        analyzed = db.form_responses.count_documents({"jd_id": jd_id, "video_analysis": {"$ne": None}})

        return {
            "jd_id": jd_id,
            "total_forms": total,
            "submitted": submitted,
            "video_analyzed": analyzed,
            "pending_video_analysis": submitted - analyzed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-form-link/{jd_id}/{candidate_id}")
async def send_form_link(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """
    Send the form submission link to a candidate via email
    This is the initial email that invites them to fill out the form
    """
    try:
        db = get_db()

        # Get candidate and JD details
        candidate = db.candidates.find_one({"candidate_id": candidate_id})
        jd = db.job_descriptions.find_one({"jd_id": jd_id})

        if not candidate or not jd:
            raise HTTPException(status_code=404, detail="Candidate or JD not found")

        candidate_name = candidate.get("name", candidate_id)
        candidate_email = candidate.get("email")
        jd_title = jd.get("title", jd_id)

        if not candidate_email:
            raise HTTPException(status_code=400, detail="Candidate email not found")

        # Use the real Google Form URL
        form_link = os.getenv("GOOGLE_FORM_URL", f"http://localhost:3000/form/{jd_id}/{candidate_id}")

        # Send email to candidate
        subject = f"Video Resume Form - {jd_title}"
        html = f"""<!DOCTYPE html>
<html>
<body style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#f1f5f9;margin:0;padding:24px">
  <div style="max-width:600px;margin:0 auto">
    <div style="background:#1e293b;padding:24px;border-radius:12px;margin-bottom:16px">
      <h1 style="color:#60a5fa;margin:0 0 4px 0;font-size:22px">JobOS</h1>
      <p style="color:#94a3b8;margin:0;font-size:12px;text-transform:uppercase;letter-spacing:2px">Video Resume Form</p>
    </div>
    <div style="background:#1e293b;padding:24px;border-radius:12px">
      <p style="color:#f1f5f9;margin:0 0 16px 0;font-size:15px">Hi {candidate_name},</p>
      <p style="color:#94a3b8;margin:0 0 20px 0;line-height:1.6">
        Thank you for your interest in the position of <strong style="color:#f1f5f9">{jd_title}</strong>.
      </p>
      <p style="color:#94a3b8;margin:0 0 20px 0;line-height:1.6">
        We would love to learn more about you! Please fill out the brief form below and submit a short video resume (1-2 minutes).
      </p>
      <p style="color:#94a3b8;margin:0 0 24px 0;line-height:1.6">
        <strong style="color:#f1f5f9">Form Details:</strong><br>
        • Aadhar Number<br>
        • LinkedIn Profile<br>
        • Alternate Phone Number<br>
        • Telegram Handle (optional)<br>
        • Video Resume (MP4, Max 5 min)
      </p>
      <div style="text-align:center;margin:28px 0">
        <a href="{form_link}"
           style="display:inline-block;padding:14px 32px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:10px;font-weight:700;font-size:14px;letter-spacing:0.5px">
          Submit Your Video Resume
        </a>
      </div>
      <p style="color:#64748b;font-size:12px;margin:0;text-align:center">
        Or copy this link: <span style="color:#60a5fa">{form_link}</span>
      </p>
      <p style="color:#94a3b8;margin:20px 0 0 0;line-height:1.6;font-size:13px">
        If you have any questions, please don't hesitate to reach out.
      </p>
    </div>
    <p style="color:#334155;font-size:11px;text-align:center;margin-top:24px">
      JobOS · Recruitment Operating System
    </p>
  </div>
</body>
</html>"""

        send_email(candidate_email, subject, html)
        logger.info(f"Form submission link sent to {candidate_email} for {candidate_id}")

        return {
            "status": "success",
            "message": f"Form link sent to {candidate_name} ({candidate_email})",
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error sending form link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resend-notification/{jd_id}/{candidate_id}")
async def resend_form_notification(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """
    Manually resend the form submission notification email
    Useful if the original email wasn't received
    """
    try:
        db = get_db()

        # Get form response
        form_response = db.form_responses.find_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"_id": 0}
        )
        if not form_response:
            raise HTTPException(status_code=404, detail="Form response not found")

        # Trigger notification task
        from tasks.notification_tasks import notify_form_submitted
        notify_form_submitted.delay(jd_id, candidate_id, form_response)

        return {
            "status": "success",
            "message": f"Form submission notification queued for {candidate_id}",
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error resending form notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-google/{jd_id}")
async def sync_google_form_responses(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """
    Pull latest responses from Google Sheet into MongoDB.
    Matches rows by email to candidates in the JD pipeline.
    Also triggers video download + analysis for new submissions.
    """
    try:
        db = get_db()

        rows = get_sheet_responses()
        if not rows:
            return {"status": "ok", "synced": 0, "message": "No rows in sheet or sheet not accessible"}

        # Build email -> candidate_id map for this JD's pipeline
        pipeline_entries = list(db.pipeline_stages.find({"jd_id": jd_id}, {"candidate_id": 1}))
        candidate_ids = [p["candidate_id"] for p in pipeline_entries]
        candidates = list(db.candidates.find({"candidate_id": {"$in": candidate_ids}}, {"candidate_id": 1, "email": 1}))
        email_to_candidate = {c["email"].lower(): c["candidate_id"] for c in candidates if c.get("email")}

        sheet_emails = [(row.get("Email Address") or row.get("Email") or "").strip().lower() for row in rows]
        logger.info(f"Sheet emails: {sheet_emails}")
        logger.info(f"Pipeline emails: {list(email_to_candidate.keys())}")
        for row in rows:
            logger.info(f"Sheet columns: {list(row.keys())}")
            break

        synced = 0
        skipped = 0

        for row in rows:
            email = (row.get("Email Address") or row.get("Email") or "").strip().lower()
            if not email or email not in email_to_candidate:
                skipped += 1
                continue

            candidate_id = email_to_candidate[email]

            # Skip if already synced — but re-check video if missing
            existing = db.form_responses.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
            if existing:
                if not existing.get("video_resume_path"):
                    video_cell = row.get("Video Resume (MP4 format, max 100MB, 3-minute duration recommended)") or row.get("Video Resume") or ""
                    video_file_id = _extract_drive_file_id(video_cell)
                    if video_file_id:
                        video_path = download_video_from_drive(video_file_id, candidate_id, jd_id)
                        if video_path:
                            db.form_responses.update_one(
                                {"jd_id": jd_id, "candidate_id": candidate_id},
                                {"$set": {"video_resume_path": video_path}}
                            )
                            analyze_video_task.delay(candidate_id, jd_id, video_path)
                skipped += 1
                continue

            # Parse timestamp
            submitted_at = datetime.utcnow()
            try:
                from dateutil import parser as dateparser
                submitted_at = dateparser.parse(row.get("Timestamp", "")) or datetime.utcnow()
            except Exception:
                pass

            response_id = f"GFORM-{jd_id}-{candidate_id}"
            form_response = {
                "response_id": response_id,
                "jd_id": jd_id,
                "candidate_id": candidate_id,
                "aadhar": row.get("Aadhar Number", "").strip() or None,
                "linkedin_url": row.get("LinkedIn Profile URL", "").strip() or None,
                "alternate_phone": row.get("Alternate Phone Number", "").strip() or None,
                "telegram_handle": row.get("Telegram Handle", "").strip() or None,
                "video_resume_path": None,
                "video_analysis": None,
                "status": "submitted",
                "source": "google_form",
                "submitted_at": submitted_at,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            db.form_responses.insert_one(form_response)
            form_response.pop("_id", None)  # remove ObjectId added by MongoDB

            # Update candidate profile
            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {"$set": {
                    "form_response_id": response_id,
                    "telegram_handle": form_response["telegram_handle"],
                    "alternate_phone": form_response["alternate_phone"],
                    "updated_at": datetime.utcnow()
                }}
            )

            # Update pipeline tracking
            db.pipeline_stages.update_one(
                {"jd_id": jd_id, "candidate_id": candidate_id},
                {"$set": {
                    "response_tracking.form_submitted.status": "submitted",
                    "response_tracking.form_submitted.submitted_at": submitted_at,
                    "updated_at": datetime.utcnow()
                }}
            )

            # Get video file ID from sheet (Google Forms stores Drive URL in the cell)
            video_cell = row.get("Video Resume (MP4 format, max 100MB, 3-minute duration recommended)") or row.get("Video Resume") or ""
            video_file_id = _extract_drive_file_id(video_cell)
            if video_file_id:
                video_path = download_video_from_drive(video_file_id, candidate_id, jd_id)
                if video_path:
                    db.form_responses.update_one(
                        {"response_id": response_id},
                        {"$set": {"video_resume_path": video_path}}
                    )
                    analyze_video_task.delay(candidate_id, jd_id, video_path)

            # Notify recruiter (pass only serializable fields)
            from tasks.notification_tasks import notify_form_submitted
            notify_form_submitted.delay(jd_id, candidate_id, {
                "response_id": response_id,
                "jd_id": jd_id,
                "candidate_id": candidate_id,
                "status": "submitted",
                "video_resume_path": video_path if video_file_id else None,
            })

            synced += 1

        return {
            "status": "ok",
            "synced": synced,
            "skipped": skipped,
            "message": f"Synced {synced} new responses from Google Form",
            "debug": {
                "sheet_emails": sheet_emails,
                "pipeline_emails": list(email_to_candidate.keys())
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing Google Form responses: {e}")
        raise HTTPException(status_code=500, detail=str(e))
