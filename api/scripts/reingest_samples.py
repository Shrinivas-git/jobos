import os
import uuid
from datetime import datetime
from pymongo import MongoClient
from celery_app import celery
from utils.storage_utils import save_resume_file
from tasks.resume_tasks import process_resume_task

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/jobos?authSource=admin")

def reingest_samples():
    print("Starting re-ingestion of sample resumes...")
    db = MongoClient(MONGO_URI).get_database("jobos")
    
    # Path to sample resumes (relative to project root in container)
    # Based on docker-compose, ./api is /app. We need to reach ../sampleresumes
    # But sampleresumes is NOT mounted in the API container in docker-compose.yml.
    # I should check where sampleresumes is. 
    # Ah, it's at C:\staging\jobos\sampleresumes.
    # I'll use a absolute path for the script inside container if I mount it, 
    # or just assume I run it from somewhere that has access.
    
    # Actually, I can use the existing /data mount if I copy samples there first.
    # Or I can just upload them via the API if I had a client.
    
    # Let's check api container mounts in docker-compose.yml
    # volumes:
    #  - ./api:/app
    #  - ./data:/data
    #  - ./config:/app/config
    
    # I will create the script to look into /data/samples if I copy them there.
    samples_dir = "/data/samples"
    if not os.path.exists(samples_dir):
        print(f"Error: {samples_dir} not found. Please copy sampleresumes to data/samples first.")
        return

    files = [f for f in os.listdir(samples_dir) if f.lower().endswith(('.pdf', '.docx'))]
    print(f"Found {len(files)} resumes to ingest.")

    for filename in files:
        try:
            # Generate Candidate ID
            date_str = datetime.now().strftime("%Y%m%d")
            unique_id = str(uuid.uuid4())[:8]
            candidate_id = f"CAN-{date_str}-{unique_id}"
            
            file_path = os.path.join(samples_dir, filename)
            with open(file_path, "rb") as f:
                content = f.read()
            
            # Save file with versioning
            new_path = save_resume_file(candidate_id, filename, content)
            
            # Create placeholder in MongoDB
            db.candidates.insert_one({
                "candidate_id": candidate_id,
                "status": "processing",
                "source": "reingest_script",
                "file_paths": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })
            
            # Trigger async processing
            process_resume_task.delay(candidate_id, new_path, "reingest_script")
            print(f" - Triggered processing for {filename} -> {candidate_id}")
            
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    reingest_samples()
