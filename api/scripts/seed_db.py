import os
import sys
from pymongo import MongoClient, ASCENDING
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:example@mongodb:27017/jobos?authSource=admin")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

def init_mongodb():
    print("Initializing MongoDB collections and indexes...")
    client = MongoClient(MONGO_URI)
    db = client.get_database("jobos")

    collections = {
        "users": [("email", ASCENDING), ("keycloak_id", ASCENDING)],
        "clients": [("slug", ASCENDING)],
        "job_descriptions": [("jd_id", ASCENDING), ("client_id", ASCENDING)],
        "candidates": [("email", ASCENDING), ("phone", ASCENDING)],
        "candidate_pools": [("jd_id", ASCENDING), ("candidate_id", ASCENDING)],
        "pipeline_stages": [("jd_id", ASCENDING), ("candidate_id", ASCENDING)],
        "batches": [("jd_id", ASCENDING)],
        "rejections": [("candidate_id", ASCENDING)],
        "invoices": [("client_id", ASCENDING), ("jd_id", ASCENDING)],
        "tasks": [("owner_id", ASCENDING), ("due_at", ASCENDING)],
        "documents": [("candidate_id", ASCENDING)],
        "notifications": [("recipient_id", ASCENDING)],
        "calls": [("candidate_id", ASCENDING)],
        "audit_log": [("actor_id", ASCENDING), ("timestamp", ASCENDING)],
        "assessments": [("title", ASCENDING)],
        "assessment_results": [("candidate_id", ASCENDING), ("assessment_id", ASCENDING)],
        "offers": [("candidate_id", ASCENDING), ("jd_id", ASCENDING)],
        "messages": [("recipient_id", ASCENDING)],
        "referrals": [("candidate_id", ASCENDING)],
        "why_not_selected": [("candidate_id", ASCENDING)],
        "feedback_digests": [("candidate_id", ASCENDING)],
        "accounts": [("client_id", ASCENDING)],
        "placements": [("candidate_id", ASCENDING), ("jd_id", ASCENDING)]
    }

    for coll_name, indexes in collections.items():
        if coll_name not in db.list_collection_names():
            db.create_collection(coll_name)
            print(f" - Created collection: {coll_name}")
        
        for index in indexes:
            db[coll_name].create_index([index], unique=True if index[0] in ["email", "slug", "jd_id", "keycloak_id"] else False)
        
    print("MongoDB initialization complete.\n")

def init_qdrant():
    print(f"Initializing Qdrant collections at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    collections = ["resume_vectors", "jd_vectors"]
    
    for coll_name in collections:
        exists = False
        try:
            client.get_collection(collection_name=coll_name)
            exists = True
            print(f" - Collection {coll_name} already exists.")
        except Exception:
            pass

        if not exists:
            client.recreate_collection(
                collection_name=coll_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print(f" - Created collection: {coll_name} (768 dim, Cosine)")

    print("Qdrant initialization complete.\n")

if __name__ == "__main__":
    try:
        init_mongodb()
        init_qdrant()
        print("Database bootstrap successful!")
    except Exception as e:
        print(f"Error during bootstrap: {e}")
        sys.exit(1)
