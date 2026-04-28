from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from datetime import datetime
import uuid
import logging
import os
from pydantic import BaseModel, Field
from utils.pydantic_utils import PyObjectId
from auth import check_role, get_current_user
from utils.client_utils import get_db

_bearer = HTTPBearer(auto_error=False)
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

async def _internal_or_auth(
    x_internal_key: Optional[str] = Header(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    if x_internal_key and INTERNAL_API_KEY and x_internal_key == INTERNAL_API_KEY:
        return {"sub": "email-watcher", "roles": ["system"]}
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await get_current_user(credentials.credentials)
from utils.storage_utils import save_resume_file
from utils.gemini_utils import extract_resume_metadata, generate_embedding
from utils.qdrant_utils import upsert_resume_vector, get_resume_vector
from utils.resume_utils import extract_text_from_file
from tasks.resume_tasks import process_resume_task
from tasks.matching_tasks import run_matching
from tasks.notification_tasks import notify_pool_ready

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])

class CandidateResponse(BaseModel):
    candidate_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = None
    location: Optional[str] = None
    notice_period: Optional[str] = None
    gender: Optional[str] = None
    college: Optional[str] = None
    projects: Optional[List[dict]] = None
    achievements: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    education: Optional[List[dict]] = None
    languages: Optional[List[str]] = None
    status: str
    source: str
    file_paths: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class CandidateUpdateRequest(BaseModel):
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = None
    notice_period: Optional[str] = None
    location: Optional[str] = None
    languages: Optional[List[str]] = None

class EmailIntakeRequest(BaseModel):
    file_path: str
    jd_id: Optional[str] = None
    source_email: str

@router.get("/", response_model=List[CandidateResponse])
async def get_candidates(user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    db = get_db()
    candidates = list(db.candidates.find({}, {"_id": 0}))
    return candidates

@router.get("/me", response_model=CandidateResponse)
async def get_my_profile(user: dict = Depends(check_role(["candidate"]))):
    email = user.get("email", "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email not found in token")

    db = get_db()
    candidate = db.candidates.find_one({"email": email}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    return candidate

@router.put("/me", response_model=CandidateResponse)
async def update_my_profile(
    update_data: CandidateUpdateRequest,
    user: dict = Depends(check_role(["candidate"]))
):
    email = user.get("email", "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email not found in token")

    db = get_db()
    update_payload = {
        "updated_at": datetime.now()
    }

    if update_data.skills is not None:
        update_payload["skills"] = update_data.skills
    if update_data.experience_years is not None:
        update_payload["experience_years"] = update_data.experience_years
    if update_data.notice_period is not None:
        update_payload["notice_period"] = update_data.notice_period
    if update_data.location is not None:
        update_payload["location"] = update_data.location
    if update_data.languages is not None:
        update_payload["languages"] = update_data.languages

    result = db.candidates.find_one_and_update(
        {"email": email},
        {"$set": update_payload},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    candidate_id = result.get("candidate_id")
    vector = get_resume_vector(candidate_id)
    if vector:
        qdrant_payload = {
            "candidate_id": candidate_id,
            "name": result.get("name"),
            "email": result.get("email"),
            "phone": result.get("phone"),
            "skills": result.get("skills"),
            "experience_years": result.get("experience_years"),
            "location": result.get("location"),
            "notice_period": result.get("notice_period"),
            "gender": result.get("gender"),
            "college": result.get("college"),
            "projects": result.get("projects", []),
            "achievements": result.get("achievements", []),
            "certifications": result.get("certifications", []),
            "education": result.get("education", []),
            "languages": result.get("languages", []),
            "previous_companies": result.get("previous_companies", []),
            "companies_switched": result.get("companies_switched", 0),
            "source": result.get("source"),
            "ingested_at": datetime.now().isoformat()
        }
        upsert_resume_vector(candidate_id, vector, qdrant_payload)

    del result["_id"]
    return result

@router.post("/email-intake")
async def email_intake(
    intake_data: EmailIntakeRequest,
    user: dict = Depends(_internal_or_auth),
):
    """
    Inbound resume intake from email watcher.
    If jd_id provided: match against that JD only.
    If no jd_id: match against all open JDs.
    """
    file_path = intake_data.file_path
    jd_id = intake_data.jd_id
    source_email = intake_data.source_email

    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail=f"File not found: {file_path}")

    try:
        db = get_db()
        date_str = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        candidate_id = f"CAN-{date_str}-{unique_id}"

        # Extract text
        text = extract_text_from_file(file_path)
        if not text:
            raise Exception("Failed to extract text from file")

        # Extract metadata
        metadata = extract_resume_metadata(text)

        # Email normalization
        email = metadata.get("email")
        if not email or str(email).lower() in ["none", "null", "", "unknown@example.com", "not specified"]:
            email = f"{candidate_id}@jobos.internal"
            metadata["email"] = email
        else:
            email = str(email).strip().lower()
            metadata["email"] = email

        # Generate embedding
        text_to_embed = f"""
        Name: {metadata.get('name')}
        Skills: {', '.join(metadata.get('skills', []))}
        Experience: {metadata.get('experience_years')} years
        Location: {metadata.get('location')}
        College: {metadata.get('college')}
        Resume Text: {text[:4000]}
        """
        vector = generate_embedding(text_to_embed)

        # Save to MongoDB
        candidate_data = {
            "candidate_id": candidate_id,
            "name": metadata.get("name"),
            "email": email,
            "phone": metadata.get("phone"),
            "skills": metadata.get("skills"),
            "experience_years": metadata.get("experience_years"),
            "location": metadata.get("location"),
            "notice_period": metadata.get("notice_period"),
            "gender": metadata.get("gender"),
            "college": metadata.get("college"),
            "projects": metadata.get("projects", []),
            "achievements": metadata.get("achievements", []),
            "certifications": metadata.get("certifications", []),
            "education": metadata.get("education", []),
            "languages": metadata.get("languages", []),
            "previous_companies": metadata.get("previous_companies", []),
            "companies_switched": metadata.get("companies_switched", 0),
            "resume_text": text,
            "status": "ready",
            "source": "email_intake",
            "source_email": source_email,
            "file_paths": [file_path],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        # Check for existing by email
        existing = db.candidates.find_one({"email": email}) if not email.endswith("@jobos.internal") else None

        if existing:
            candidate_id = existing["candidate_id"]
            update_payload = {
                "updated_at": datetime.now(),
                "resume_text": text,
                "status": "ready",
                "source_email": source_email
            }

            for key in ["name", "phone", "skills", "experience_years", "location", "notice_period", "gender", "college",
                        "projects", "achievements", "certifications", "education", "languages", "previous_companies"]:
                new_val = candidate_data.get(key)
                existing_val = existing.get(key)
                is_existing_weak = existing_val in [None, "Unknown", "Not specified", 0, []]
                is_new_strong = new_val not in [None, "Unknown", "Not specified", 0, []]

                if is_new_strong or is_existing_weak:
                    update_payload[key] = new_val

            new_switched = candidate_data.get("companies_switched")
            if new_switched is not None:
                update_payload["companies_switched"] = new_switched

            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {
                    "$set": update_payload,
                    "$addToSet": {"file_paths": file_path}
                }
            )
        else:
            db.candidates.insert_one(candidate_data)

        # Upsert to Qdrant
        payload = {
            "candidate_id": candidate_id,
            "name": metadata.get("name"),
            "email": email,
            "phone": metadata.get("phone"),
            "skills": metadata.get("skills"),
            "experience_years": metadata.get("experience_years"),
            "location": metadata.get("location"),
            "notice_period": metadata.get("notice_period"),
            "gender": metadata.get("gender"),
            "college": metadata.get("college"),
            "projects": metadata.get("projects", []),
            "achievements": metadata.get("achievements", []),
            "certifications": metadata.get("certifications", []),
            "education": metadata.get("education", []),
            "languages": metadata.get("languages", []),
            "previous_companies": metadata.get("previous_companies", []),
            "companies_switched": metadata.get("companies_switched", 0),
            "source": "email_intake",
            "ingested_at": datetime.now().isoformat(),
            "file_path": file_path
        }
        upsert_resume_vector(candidate_id, vector, payload)

        # Trigger matching
        if jd_id:
            # Match against specific JD
            logger.info(f"Running matching for candidate {candidate_id} against JD {jd_id}")
            run_matching.delay(jd_id)
        else:
            # Match against all open JDs
            logger.info(f"Running matching for candidate {candidate_id} against all open JDs")
            open_jds = db.job_descriptions.find({"status": "active"}, {"jd_id": 1})
            for jd_doc in open_jds:
                run_matching.delay(jd_doc["jd_id"])

        return {
            "message": "Resume intake processed successfully",
            "candidate_id": candidate_id,
            "source": "email_intake",
            "jd_id": jd_id or "auto-match"
        }

    except Exception as e:
        logger.error(f"Error processing email intake: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user: dict = Depends(check_role(["recruiter", "manager", "admin"]))
):
    """
    Accepts a PDF or DOCX resume, saves it, and processes it SYNCHRONOUSLY.
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
        
        # 1. Text Extraction
        text = extract_text_from_file(file_path)
        if not text:
            raise Exception("Failed to extract text from file")
            
        # 2. Metadata Extraction via Gemini
        metadata = extract_resume_metadata(text)
        
        # Handle unique email generation
        email = metadata.get("email")
        if not email or str(email).lower() in ["none", "null", "", "unknown@example.com", "not specified"]:
            email = f"{candidate_id}@jobos.internal"
            metadata["email"] = email
        else:
            email = str(email).strip().lower()
            metadata["email"] = email

        # 3. Generate Embedding
        text_to_embed = f"""
        Name: {metadata.get('name')}
        Skills: {', '.join(metadata.get('skills', []))}
        Experience: {metadata.get('experience_years')} years
        Location: {metadata.get('location')}
        College: {metadata.get('college')}
        Resume Text: {text[:4000]}
        """
        vector = generate_embedding(text_to_embed)
        
        # 4. Save to MongoDB
        db = get_db()
        candidate_data = {
            "candidate_id": candidate_id,
            "name": metadata.get("name"),
            "email": email,
            "phone": metadata.get("phone"),
            "skills": metadata.get("skills"),
            "experience_years": metadata.get("experience_years"),
            "location": metadata.get("location"),
            "notice_period": metadata.get("notice_period"),
            "gender": metadata.get("gender"),
            "college": metadata.get("college"),
            "projects": metadata.get("projects", []),
            "achievements": metadata.get("achievements", []),
            "certifications": metadata.get("certifications", []),
            "education": metadata.get("education", []),
            "languages": metadata.get("languages", []),
            "previous_companies": metadata.get("previous_companies", []),
            "companies_switched": metadata.get("companies_switched", 0),
            "resume_text": text,
            "status": "ready",
            "source": "web_upload",
            "file_paths": [file_path],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Check for existing by email
        existing = db.candidates.find_one({"email": email}) if not email.endswith("@jobos.internal") else None
        
        if existing:
            candidate_id = existing["candidate_id"]
            # Logic to preserve existing data if new extraction is "Unknown"
            update_payload = {
                "updated_at": datetime.now(),
                "resume_text": text,
                "status": "ready"
            }
            
            # Fields to update only if new value is significant
            for key in ["name", "phone", "skills", "experience_years", "location", "notice_period", "gender", "college",
                        "projects", "achievements", "certifications", "education", "languages", "previous_companies"]:
                new_val = candidate_data.get(key)
                # Only overwrite if new value is better or existing is Unknown/Default
                existing_val = existing.get(key)
                is_existing_weak = existing_val in [None, "Unknown", "Not specified", 0, []]
                is_new_strong = new_val not in [None, "Unknown", "Not specified", 0, []]
                
                if is_new_strong or is_existing_weak:
                    update_payload[key] = new_val

            # companies_switched: 0 is a valid value so needs its own guard
            new_switched = candidate_data.get("companies_switched")
            if new_switched is not None:
                update_payload["companies_switched"] = new_switched

            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {
                    "$set": update_payload,
                    "$addToSet": {"file_paths": file_path}
                }
            )
        else:
            db.candidates.insert_one(candidate_data)
            
        # 5. Upsert to Qdrant
        payload = {
            "candidate_id": candidate_id,
            "name": metadata.get("name"),
            "email": email,
            "phone": metadata.get("phone"),
            "skills": metadata.get("skills"),
            "experience_years": metadata.get("experience_years"),
            "location": metadata.get("location"),
            "notice_period": metadata.get("notice_period"),
            "gender": metadata.get("gender"),
            "college": metadata.get("college"),
            "projects": metadata.get("projects", []),
            "achievements": metadata.get("achievements", []),
            "certifications": metadata.get("certifications", []),
            "education": metadata.get("education", []),
            "languages": metadata.get("languages", []),
            "previous_companies": metadata.get("previous_companies", []),
            "companies_switched": metadata.get("companies_switched", 0),
            "source": "web_upload",
            "ingested_at": datetime.now().isoformat(),
            "file_path": file_path
        }
        upsert_resume_vector(candidate_id, vector, payload)
        
        return {
            "message": "Resume uploaded and processed successfully",
            "candidate_id": candidate_id,
            "metadata": metadata
        }
        
    except Exception as e:
        print(f"Error processing resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))
