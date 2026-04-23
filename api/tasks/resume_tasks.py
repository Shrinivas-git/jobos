import os
import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.gemini_utils import extract_resume_metadata, generate_embedding
from utils.qdrant_utils import upsert_resume_vector
from utils.resume_utils import extract_text_from_file

logger = logging.getLogger(__name__)

@celery.task(name="tasks.resume_tasks.process_resume_task")
def process_resume_task(candidate_id: str, file_path: str, source: str = "web_upload"):
    logger.info(f"Starting processing for candidate: {candidate_id}")
    db = get_db()
    
    # 1. Text Extraction
    text = extract_text_from_file(file_path)
    if not text:
        logger.error(f"Failed to extract text from {file_path}")
        db.candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": {"status": "error", "error": "Text extraction failed"}}
        )
        return
    
    # 2. Metadata Extraction via Gemini
    logger.info("Extracting metadata via Gemini...")
    metadata = extract_resume_metadata(text)
    
    # FIX: Handle unique email generation and duplicate emails
    # Ensure email is NEVER None, null, empty string, or placeholder
    email = metadata.get("email")
    if not email or str(email).lower() in ["none", "null", "", "unknown@example.com", "not specified"]:
        email = f"{candidate_id}@jobos.internal"
        metadata["email"] = email
        logger.info(f"Generated internal email for {candidate_id}: {email}")
    else:
        # Normalize email
        email = str(email).strip().lower()
        metadata["email"] = email

    # 3. Generate Embedding
    logger.info("Generating embedding...")
    # Use text + metadata for a rich embedding
    text_to_embed = f"""
    Name: {metadata.get('name')}
    Skills: {', '.join(metadata.get('skills', []))}
    Experience: {metadata.get('experience_years')} years
    Location: {metadata.get('location')}
    Resume Text: {text[:4000]}
    """
    vector = generate_embedding(text_to_embed)
    
    # 4. Handle Upsert Logic
    is_internal_email = email.endswith("@jobos.internal")
    
    # Query for matching: by email if real, by candidate_id if internal
    # If it's a real email, we want to find if ANY candidate has this email already
    query = {"email": email} if not is_internal_email else {"candidate_id": candidate_id}
    
    logger.info(f"Performing upsert search with query: {query}")
    
    existing_candidate = db.candidates.find_one(query)
    
    if existing_candidate:
        final_candidate_id = existing_candidate["candidate_id"]
        logger.info(f"Matching candidate found: {final_candidate_id}. Updating existing record.")
        
        # update existing record
        db.candidates.update_one(
            {"candidate_id": final_candidate_id},
            {
                "$set": {
                    "name": metadata.get("name"),
                    "phone": metadata.get("phone"),
                    "skills": metadata.get("skills"),
                    "experience_years": metadata.get("experience_years"),
                    "location": metadata.get("location"),
                    "status": "ready",
                    "updated_at": datetime.now()
                },
                "$addToSet": {"file_paths": file_path} # Avoid duplicates if same path
            }
        )
        
        # If the existing candidate is NOT the one we just created in the router, 
        # delete the temporary placeholder record.
        if final_candidate_id != candidate_id:
            db.candidates.delete_one({"candidate_id": candidate_id})
            logger.info(f"Cleaned up placeholder record: {candidate_id}")
    else:
        # This shouldn't happen often as router creates a placeholder, 
        # but handle it for robustness.
        final_candidate_id = candidate_id
        logger.info(f"No match found. Updating placeholder record: {candidate_id}")
        db.candidates.update_one(
            {"candidate_id": candidate_id},
            {
                "$set": {
                    "name": metadata.get("name"),
                    "email": email,
                    "phone": metadata.get("phone"),
                    "skills": metadata.get("skills"),
                    "experience_years": metadata.get("experience_years"),
                    "location": metadata.get("location"),
                    "status": "ready",
                    "updated_at": datetime.now()
                },
                "$addToSet": {"file_paths": file_path}
            },
            upsert=True
        )

    # 5. Upsert to Qdrant
    logger.info(f"Upserting to Qdrant for candidate: {final_candidate_id}...")
    payload = {
        "candidate_id": final_candidate_id,
        "name": metadata.get("name"),
        "email": email,
        "phone": metadata.get("phone"),
        "skills": metadata.get("skills"),
        "experience_years": metadata.get("experience_years"),
        "location": metadata.get("location"),
        "source": source,
        "ingested_at": datetime.now().isoformat(),
        "file_path": file_path
    }
    upsert_resume_vector(final_candidate_id, vector, payload)
    
    logger.info(f"Resume processing complete for {final_candidate_id}")
    return f"Processed {final_candidate_id}"
