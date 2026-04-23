import os
import json
import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.gemini_utils import extract_jd_data, generate_jd_formats, generate_embedding
from utils.qdrant_utils import upsert_jd_vector

logger = logging.getLogger(__name__)

@celery.task(name="tasks.jd_tasks.process_jd_task")
def process_jd_task(jd_id: str):
    logger.info(f"Starting processing for JD: {jd_id}")
    db = get_db()
    jd_record = db.job_descriptions.find_one({"jd_id": jd_id})
    
    if not jd_record:
        logger.error(f"JD {jd_id} not found in database")
        return f"JD {jd_id} not found"

    jd_path = jd_record["folder_path"]
    raw_path = os.path.join(jd_path, "raw")
    
    structured_data = jd_record.get("structured_data")
    
    # 1. Extraction (if not already structured via web form)
    if not structured_data:
        try:
            if not os.path.exists(raw_path):
                logger.error(f"Raw path {raw_path} does not exist")
                return f"Raw path missing for {jd_id}"
                
            raw_files = os.listdir(raw_path)
            if not raw_files:
                logger.error(f"No raw files found in {raw_path}")
                return f"No raw files found for {jd_id}"
            
            # Prefer email_body.txt or use the first available file
            raw_file = "email_body.txt" if "email_body.txt" in raw_files else raw_files[0]
            file_path = os.path.join(raw_path, raw_file)
            
            # Basic text reading. (Note: pdf/docx extraction could be added here in utils)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
            
            logger.info(f"Extracting structured data from {raw_file}...")
            structured_data = extract_jd_data(raw_text)
            
            # Save jd.json
            with open(os.path.join(jd_path, "jd.json"), "w") as f:
                json.dump(structured_data, f, indent=2)
                
            # Update MongoDB record with extracted data
            db.job_descriptions.update_one(
                {"jd_id": jd_id},
                {"$set": {"structured_data": structured_data}}
            )
        except Exception as e:
            logger.error(f"Error during JD extraction: {e}")
            return f"Extraction failed for {jd_id}: {e}"

    # 2. Format Generation (Internal, Short, Candidate)
    try:
        logger.info("Generating JD formats...")
        formats = generate_jd_formats(structured_data)
        for fmt_name, content in formats.items():
            with open(os.path.join(jd_path, f"{fmt_name}.md"), "w") as f:
                f.write(content)
    except Exception as e:
        logger.error(f"Error generating formats: {e}")

    # 3. Embedding & Qdrant Upsert
    try:
        logger.info("Generating embedding and upserting to Qdrant...")
        # Construct a comprehensive text for semantic search
        text_to_embed = f"""
        Title: {structured_data.get('title')}
        Level: {structured_data.get('level')}
        Responsibilities: {structured_data.get('responsibilities')}
        Skills: {', '.join(structured_data.get('skills', []))}
        Location: {structured_data.get('location')}
        """
        vector = generate_embedding(text_to_embed)
        
        payload = {
            "jd_id": jd_id,
            "title": structured_data.get("title"),
            "client_id": str(jd_record.get("client_id")),
            "location": structured_data.get("location"),
            "status": "structured"
        }
        upsert_jd_vector(jd_id, vector, payload)
    except Exception as e:
        logger.error(f"Error with Qdrant/Embedding: {e}")

    # 4. Final Status Update
    db.job_descriptions.update_one(
        {"jd_id": jd_id},
        {"$set": {
            "status": "structured", 
            "updated_at": datetime.now()
        }}
    )

    logger.info(f"Processing complete for JD: {jd_id}")
    
    # 5. Trigger Matching Engine
    from tasks.matching_tasks import run_matching
    run_matching.delay(jd_id)
    
    return f"Successfully structured {jd_id}"
