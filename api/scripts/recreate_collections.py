
import os
import sys
import logging
import uuid
import json
from qdrant_client import QdrantClient, models

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.client_utils import get_db
from utils.gemini_utils import generate_embedding
from utils.resume_utils import extract_text_from_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
db = get_db()

def delete_and_recreate_collections():
    """Deletes and recreates the Qdrant collections."""
    collection_names = ["jd_vectors", "resume_vectors"]
    for name in collection_names:
        try:
            qdrant_client.delete_collection(collection_name=name)
            logger.info(f"Deleted collection: {name}")
        except Exception as e:
            logger.warning(f"Could not delete collection {name} (it may not exist): {e}")

        qdrant_client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )
        logger.info(f"Recreated collection: {name} (384 dimensions)")

def get_jd_text(jd):
    """Helper to construct text for JD embedding."""
    sd = jd.get("structured_data", {})
    if not sd:
        return ""
    
    text = f"""
    Title: {sd.get('title')}
    Level: {sd.get('level')}
    Responsibilities: {sd.get('responsibilities')}
    Skills: {', '.join(sd.get('skills', [])) if isinstance(sd.get('skills'), list) else sd.get('skills')}
    Location: {sd.get('location')}
    Experience: {sd.get('experience_range')}
    """
    return text.strip()

def re_embed_jds():
    """Fetches all JDs from MongoDB, re-embeds them, and upserts to Qdrant."""
    logger.info("Starting JD re-embedding process...")
    # Using the correct collection name: job_descriptions
    jds = list(db.job_descriptions.find({}))
    count = 0
    for jd in jds:
        jd_id = jd.get('jd_id')
        if not jd_id:
            continue
            
        full_text = get_jd_text(jd)
        if not full_text:
            logger.warning(f"Skipping JD {jd_id} due to missing structured data.")
            continue
        
        vector = generate_embedding(full_text)
        payload = {
            "jd_id": jd_id,
            "title": jd.get("structured_data", {}).get("title"),
            "client_id": str(jd.get("client_id")),
            "location": jd.get("structured_data", {}).get("location")
        }
        
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, jd_id))

        qdrant_client.upsert(
            collection_name="jd_vectors",
            points=[models.PointStruct(id=point_id, vector=vector, payload=payload)]
        )
        count += 1
    logger.info(f"Successfully re-embedded {count}/{len(jds)} JDs.")

def re_embed_resumes():
    """Iterates through /data/resumes folder, extracts text, embeds, and upserts to Qdrant."""
    logger.info("Starting resume re-embedding process from /data/resumes...")
    resumes_root = "/data/resumes"
    if not os.path.exists(resumes_root):
        logger.error(f"Resumes root {resumes_root} does not exist.")
        return

    count = 0
    # Each subfolder is a candidate_id
    candidate_folders = [f for f in os.listdir(resumes_root) if os.path.isdir(os.path.join(resumes_root, f))]
    
    for candidate_id in candidate_folders:
        folder_path = os.path.join(resumes_root, candidate_id)
        # Look for the original resume file
        files = os.listdir(folder_path)
        resume_file = None
        for f in files:
            if f.lower().endswith(('.pdf', '.docx')):
                resume_file = f
                break
        
        if not resume_file:
            logger.warning(f"No resume file found in {folder_path}")
            continue
            
        file_path = os.path.join(folder_path, resume_file)
        text = extract_text_from_file(file_path)
        
        if not text:
            logger.warning(f"Failed to extract text from {file_path}")
            continue
            
        # Try to get metadata from DB if it exists, else use minimal
        candidate = db.candidates.find_one({"candidate_id": candidate_id})
        
        # Enrich embedding with metadata if available
        if candidate:
            text_to_embed = f"""
            Name: {candidate.get('name')}
            Skills: {', '.join(candidate.get('skills', [])) if isinstance(candidate.get('skills'), list) else ''}
            Experience: {candidate.get('experience_years')} years
            Location: {candidate.get('location')}
            Resume Text: {text[:4000]}
            """
            payload = {
                "candidate_id": candidate_id,
                "name": candidate.get("name"),
                "email": candidate.get("email"),
                "experience_years": candidate.get("experience_years"),
                "skills": candidate.get("skills"),
                "location": candidate.get("location")
            }
        else:
            text_to_embed = text[:5000]
            payload = {
                "candidate_id": candidate_id,
                "status": "re-indexed-without-db-record"
            }
            
        vector = generate_embedding(text_to_embed)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, candidate_id))

        qdrant_client.upsert(
            collection_name="resume_vectors",
            points=[models.PointStruct(id=point_id, vector=vector, payload=payload)]
        )
        count += 1
        
    logger.info(f"Successfully re-embedded {count} resumes.")

if __name__ == "__main__":
    logger.info("--- Starting Qdrant Collection and Data Migration ---")
    
    # 1. Delete and recreate collections
    delete_and_recreate_collections()
    
    # 2. Re-embed JDs from MongoDB
    re_embed_jds()
    
    # 3. Re-embed Resumes from Folder
    re_embed_resumes()
    
    logger.info("--- Migration Complete ---")
