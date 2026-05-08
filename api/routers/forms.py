from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from auth import check_role
from utils.client_utils import get_db
from utils.google_forms_utils import save_video_file, get_video_storage_path
from tasks.video_analysis_tasks import analyze_video_resume as analyze_video_task

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
