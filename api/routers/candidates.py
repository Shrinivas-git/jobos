from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import os
from pydantic import BaseModel, Field, model_validator
from utils.pydantic_utils import PyObjectId
from auth import check_role, get_current_user
from utils.client_utils import get_db
from utils.storage_utils import save_resume_file
from utils.gemini_utils import extract_resume_metadata, generate_embedding
from utils.qdrant_utils import upsert_resume_vector, delete_resume_vector
from utils.resume_utils import extract_text_from_file
from tasks.resume_tasks import process_resume_task
from tasks.matching_tasks import run_matching
from tasks.notification_tasks import notify_pool_ready

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
    file_paths: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def coerce_mongo_types(cls, v):
        # dict → [dict] for List[dict] fields
        for field in ('education', 'projects'):
            val = v.get(field)
            if isinstance(val, dict):
                v[field] = [val]

        # str → [str] for List[str] fields
        for field in ('skills', 'achievements', 'certifications', 'languages'):
            val = v.get(field)
            if isinstance(val, str):
                v[field] = [val] if val else []

        # non-str → str for Optional[str] scalar fields
        for field in ('name', 'email', 'phone', 'location', 'notice_period',
                      'gender', 'college'):
            val = v.get(field)
            if val is not None and not isinstance(val, str):
                v[field] = str(val)

        # non-float → float for Optional[float] fields
        val = v.get('experience_years')
        if val is not None and not isinstance(val, float):
            try:
                v['experience_years'] = float(val)
            except (ValueError, TypeError):
                v['experience_years'] = None

        return v

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

@router.get("/sourced")
async def get_sourced_candidates(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    """Return LinkedIn-sourced candidates for a given JD."""
    db = get_db()
    candidates = list(db.candidates.find(
        {"source": "unipile_linkedin", "jd_id": jd_id},
        {"_id": 0, "candidate_id": 1, "name": 1, "headline": 1, "location": 1,
         "linkedin_url": 1, "linkedin_provider_id": 1, "form_sent": 1, "created_at": 1}
    ).sort("created_at", -1))
    return candidates


@router.post("/{candidate_id}/send-linkedin-message")
async def send_linkedin_message_to_candidate(
    candidate_id: str,
    jd_id: str = Body(...),
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))
):
    """Send a LinkedIn DM to a sourced candidate with the application form link."""
    from utils.unipile_utils import send_linkedin_message
    db = get_db()
    candidate = db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    provider_id = candidate.get("linkedin_provider_id", "")
    if not provider_id:
        raise HTTPException(status_code=400, detail="No LinkedIn provider ID stored for this candidate — cannot send message via Unipile")

    jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"title": 1})
    job_title = jd.get("title", "a role") if jd else "a role"

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    form_url = f"{frontend_url}/apply/{jd_id}/{candidate_id}"

    message = (
        f"Hi {candidate.get('name', 'there')},\n\n"
        f"I came across your LinkedIn profile and believe you could be a great fit for our {job_title} opening.\n\n"
        f"If you're interested, please take 2 minutes to fill out this short application form:\n{form_url}\n\n"
        f"Looking forward to hearing from you!"
    )

    result = send_linkedin_message(provider_id, message)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Unipile error: {result.get('error')}")

    db.candidates.update_one(
        {"candidate_id": candidate_id},
        {"$set": {"form_sent": True, "form_sent_at": datetime.now(timezone.utc)}}
    )
    return {"ok": True, "message": "LinkedIn message sent successfully"}

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

    # Generate new embedding from updated metadata
    text_to_embed = f"""
    Name: {result.get('name')}
    Skills: {', '.join(s for s in result.get('skills', []) if s)}
    Experience: {result.get('experience_years')} years
    Location: {result.get('location')}
    College: {result.get('college')}
    Resume Text: {result.get('resume_text', '')[:4000]}
    """
    vector = generate_embedding(text_to_embed)

    # Upsert to Qdrant with new embedding
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

    # Trigger matching for all open JDs
    open_jds = db.job_descriptions.find({"status": "active"}, {"jd_id": 1})
    for jd_doc in open_jds:
        run_matching.delay(jd_doc["jd_id"])
        logger.info(f"Triggered matching for candidate {candidate_id} against JD {jd_doc['jd_id']}")

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
        Skills: {', '.join(s for s in metadata.get('skills', []) if s)}
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
            "skills": [s for s in (metadata.get("skills") or []) if s],
            "experience_years": metadata.get("experience_years"),
            "location": metadata.get("location"),
            "notice_period": metadata.get("notice_period"),
            "gender": metadata.get("gender"),
            "college": metadata.get("college"),
            "projects": [p for p in (metadata.get("projects") or []) if p],
            "achievements": [a for a in (metadata.get("achievements") or []) if a],
            "certifications": [c for c in (metadata.get("certifications") or []) if c],
            "education": [e for e in (metadata.get("education") or []) if e],
            "languages": [l for l in (metadata.get("languages") or []) if l],
            "previous_companies": [c for c in (metadata.get("previous_companies") or []) if c],
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
        Skills: {', '.join(s for s in metadata.get('skills', []) if s)}
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
            "skills": [s for s in (metadata.get("skills") or []) if s],
            "experience_years": metadata.get("experience_years"),
            "location": metadata.get("location"),
            "notice_period": metadata.get("notice_period"),
            "gender": metadata.get("gender"),
            "college": metadata.get("college"),
            "projects": [p for p in (metadata.get("projects") or []) if p],
            "achievements": [a for a in (metadata.get("achievements") or []) if a],
            "certifications": [c for c in (metadata.get("certifications") or []) if c],
            "education": [e for e in (metadata.get("education") or []) if e],
            "languages": [l for l in (metadata.get("languages") or []) if l],
            "previous_companies": [c for c in (metadata.get("previous_companies") or []) if c],
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

        # Trigger re-matching for all active JDs with the updated profile
        open_jds = db.job_descriptions.find({"status": "active"}, {"jd_id": 1})
        for jd in open_jds:
            run_matching.delay(jd["jd_id"])
            logger.info(f"Triggered matching for candidate {candidate_id} against JD {jd['jd_id']}")

        return {
            "message": "Resume uploaded and processed successfully",
            "candidate_id": candidate_id,
            "metadata": metadata
        }
        
    except Exception as e:
        print(f"Error processing resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── DPDP: Consent & Right-to-Erasure ─────────────────────────────────────────

@router.get("/{candidate_id}/public")
async def get_candidate_public(candidate_id: str):
    """Public endpoint — returns only name for use on candidate-facing form page."""
    db = get_db()
    c = db.candidates.find_one({"candidate_id": candidate_id}, {"_id": 0, "candidate_id": 1, "name": 1})
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c


@router.post("/{candidate_id}/consent")
async def record_consent(
    candidate_id: str,
    user: dict = Depends(check_role(["candidate", "recruiter", "admin"])),
):
    """Record DPDP consent for a candidate."""
    db = get_db()
    result = db.candidates.update_one(
        {"candidate_id": candidate_id},
        {"$set": {
            "consent_given": True,
            "consent_at": datetime.now(timezone.utc),
            "consent_actor": user.get("sub"),
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": "consent recorded", "candidate_id": candidate_id}


@router.delete("/{candidate_id}/erase")
async def erase_candidate(
    candidate_id: str,
    user: dict = Depends(check_role(["admin"])),
):
    """Right-to-erasure: anonymise all PII fields for a candidate (admin only)."""
    db = get_db()
    erased = "[ERASED]"
    result = db.candidates.update_one(
        {"candidate_id": candidate_id},
        {"$set": {
            "name": erased,
            "email": f"{candidate_id}@erased.invalid",
            "phone": erased,
            "resume_url": erased,
            "resume_text": erased,
            "file_paths": [],
            "skills": [],
            "education": [],
            "projects": [],
            "achievements": [],
            "certifications": [],
            "languages": [],
            "location": erased,
            "college": erased,
            "erased_at": datetime.now(timezone.utc),
            "erased_by": user.get("sub"),
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": "candidate erased", "candidate_id": candidate_id}


@router.delete("/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    """Hard delete a candidate — removes from MongoDB, Qdrant, and filesystem."""
    db = get_db()
    candidate = db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # 1. Remove from MongoDB
    db.candidates.delete_one({"candidate_id": candidate_id})
    db.candidate_pools.delete_many({"candidate_id": candidate_id})
    db.pipeline_stages.delete_many({"candidate_id": candidate_id})
    db.form_responses.delete_many({"candidate_id": candidate_id})
    db.reminder_log.delete_many({"candidate_id": candidate_id})

    # 2. Remove from Qdrant
    try:
        delete_resume_vector(candidate_id)
    except Exception as e:
        logger.warning(f"Qdrant delete failed for {candidate_id}: {e}")

    # 3. Remove filesystem folders (resume + video)
    try:
        import shutil
        resume_folder = os.path.join("data", "resumes", candidate_id)
        if os.path.isdir(resume_folder):
            shutil.rmtree(resume_folder)
            logger.info(f"Deleted resume folder: {resume_folder}")
        for jd_folder in ["/data/video_resumes"]:
            video_folder = os.path.join(jd_folder, "*", candidate_id)
            import glob
            for vf in glob.glob(video_folder):
                shutil.rmtree(vf, ignore_errors=True)
    except Exception as e:
        logger.warning(f"Filesystem delete failed for {candidate_id}: {e}")

    logger.info(f"Candidate {candidate_id} hard-deleted by {user.get('preferred_username', user.get('sub'))}")
    return {"ok": True, "deleted": candidate_id}
