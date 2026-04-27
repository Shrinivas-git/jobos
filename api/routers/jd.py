from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional, List
from datetime import datetime
import json
import os
from pydantic import BaseModel, EmailStr, Field
from utils.pydantic_utils import PyObjectId
from auth import check_role
from utils.client_utils import find_or_create_client, get_db
from utils.jd_utils import generate_jd_id
from utils.storage_utils import create_jd_folder_structure, save_raw_jd_content
from tasks.jd_tasks import process_jd_task

router = APIRouter(prefix="/jd", tags=["jd"])

class StructuredJD(BaseModel):
    title: str
    level: str
    client_email: EmailStr
    responsibilities: str
    kpis: str
    skills: List[str]
    relevant_experience: int
    total_experience: int
    compensation_range: str
    work_structure: str
    location: str
    hiring_timeline: str
    urgency: str
    num_positions: int
    gender_preference: str = "Any"
    college_preference: Optional[str] = ""
    college_exclusion: Optional[str] = ""
    preferred_company_type: Optional[List[str]] = []
    preferred_team_size: Optional[str] = "Any"
    role_type: Optional[str] = "Any"
    obfuscate: bool = False

class JDResponse(BaseModel):
    jd_id: str
    title: str
    client_id: PyObjectId
    filename: Optional[str] = None
    folder_path: str
    status: str
    created_at: datetime
    source: str
    uploaded_by: Optional[str] = None
    structured_data: Optional[dict] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

@router.get("/", response_model=List[JDResponse])
async def get_jds(user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))):
    db = get_db()
    # Sort by created_at descending
    jds = list(db.job_descriptions.find({}, {"_id": 0}).sort("created_at", -1))
    return jds

@router.post("/upload")
async def upload_jd(
    title: str = Form(...),
    client_email: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    try:
        # 1. Find or create client
        client = find_or_create_client(client_email)
        
        # 2. Generate JD-ID
        jd_id = generate_jd_id()
        
        # 3. Create folder structure
        paths = create_jd_folder_structure(client['slug'], jd_id)
        
        # 4. Save raw file
        content = await file.read()
        file_path = save_raw_jd_content(paths['raw_path'], file.filename, content)
        
        # 5. Store metadata in MongoDB
        db = get_db()
        jd_data = {
            "client_id": client['_id'],
            "jd_id": jd_id,
            "title": title,
            "filename": file.filename,
            "folder_path": paths['jd_path'],
            "source": "web_form_upload",
            "uploaded_by": user.get("preferred_username"),
            "status": "received",
            "created_at": datetime.now()
        }
        db.job_descriptions.insert_one(jd_data)
        
        # Trigger async processing
        process_jd_task.delay(jd_id)
        
        return {
            "message": "JD uploaded successfully",
            "jd_id": jd_id,
            "client": client['slug'],
            "folder": paths['jd_path']
        }
        
    except Exception as e:
        print(f"Error uploading JD: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create")
async def create_structured_jd(
    data: StructuredJD,
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    try:
        # 1. Find or create client
        client = find_or_create_client(data.client_email)
        
        # 2. Generate JD-ID
        jd_id = generate_jd_id()
        
        # 3. Create folder structure
        paths = create_jd_folder_structure(client['slug'], jd_id)
        
        # 4. Save structured JSON
        jd_json_path = os.path.join(paths['jd_path'], "jd.json")
        with open(jd_json_path, "w") as f:
            json.dump(data.dict(), f, indent=2)
            
        # 5. Store metadata in MongoDB
        db = get_db()
        jd_data = {
            "client_id": client['_id'],
            "jd_id": jd_id,
            "title": data.title,
            "folder_path": paths['jd_path'],
            "source": "web_form_structured",
            "uploaded_by": user.get("preferred_username"),
            "status": "received", # In Phase 2 this might jump to 'structured'
            "created_at": datetime.now(),
            "structured_data": data.dict()
        }
        db.job_descriptions.insert_one(jd_data)
        
        # Trigger async processing
        process_jd_task.delay(jd_id)
        
        return {
            "message": "Structured JD created successfully",
            "jd_id": jd_id,
            "client": client['slug'],
            "folder": paths['jd_path']
        }
        
    except Exception as e:
        print(f"Error creating structured JD: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{jd_id}/process")
async def trigger_process_jd(jd_id: str):
    """Internal endpoint to trigger JD structuring."""
    process_jd_task.delay(jd_id)
    return {"message": f"Processing triggered for {jd_id}"}
