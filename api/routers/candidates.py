from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from typing import List
from datetime import datetime
import uuid
from auth import check_role
from utils.client_utils import get_db
from utils.storage_utils import save_resume_file
from tasks.resume_tasks import process_resume_task

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.get("/")
async def get_candidates(user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    db = get_db()
    candidates = list(db.candidates.find({}, {"_id": 0}))
    return candidates

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """
    Accepts a PDF or DOCX resume, saves it, and triggers processing.
    """
    filename = file.filename
    if not filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")
    
    try:
        # Generate Candidate ID
        date_str = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        candidate_id = f"CAN-{date_str}-{unique_id}"
        
        # Read content
        content = await file.read()
        
        # Save file with versioning
        file_path = save_resume_file(candidate_id, filename, content)
        
        # Create placeholder in MongoDB
        db = get_db()
        db.candidates.insert_one({
            "candidate_id": candidate_id,
            "status": "processing",
            "source": "web_upload",
            "file_paths": [], # Will be updated by task
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        
        # Trigger async processing
        process_resume_task.delay(candidate_id, file_path, "web_upload")
        
        return {
            "message": "Resume uploaded and processing started",
            "candidate_id": candidate_id,
            "file_path": file_path
        }
        
    except Exception as e:
        print(f"Error uploading resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))
