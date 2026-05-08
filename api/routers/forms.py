from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from auth import check_role
from utils.client_utils import get_db
from utils.google_forms_utils import save_video_file, get_video_storage_path
from utils.email_utils import send_email
from tasks.video_analysis_tasks import analyze_video_resume as analyze_video_task
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forms", tags=["forms"])

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

@router.post("/submit")
async def submit_form(
    jd_id: str = Form(...),
    candidate_id: str = Form(...),
    aadhar: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    alternate_phone: Optional[str] = Form(None),
    telegram_handle: Optional[str] = Form(None),
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
            "linkedin_url": linkedin_url.strip() if linkedin_url else None,
            "alternate_phone": alternate_phone.strip() if alternate_phone else None,
            "telegram_handle": telegram_handle.strip() if telegram_handle else None,
            "video_resume_path": video_path,
            "video_analysis": None,
            "status": "submitted",
            "submitted_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        db.form_responses.insert_one(form_response)

        # Update candidate profile with form response ID
        db.candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": {
                "form_response_id": response_id,
                "telegram_handle": telegram_handle.strip() if telegram_handle else None,
                "alternate_phone": alternate_phone.strip() if alternate_phone else None,
                "updated_at": datetime.utcnow()
            }}
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

        # Build form link (frontend URL)
        form_link = f"http://localhost:3000/form/{jd_id}/{candidate_id}"

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
