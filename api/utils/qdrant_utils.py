import os
import logging
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

COLLECTION_NAME = "jd_vectors"
RESUME_COLLECTION = "resume_vectors"

def init_qdrant():
    """Ensures the jd_vectors and resume_vectors collections exist."""
    try:
        collections = [c.name for c in client.get_collections().collections]
        
        # JD Vectors
        if COLLECTION_NAME not in collections:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
            
        # Resume Vectors
        if RESUME_COLLECTION not in collections:
            client.create_collection(
                collection_name=RESUME_COLLECTION,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {RESUME_COLLECTION}")
            
    except Exception as e:
        logger.error(f"Error initializing Qdrant: {e}")

def upsert_jd_vector(jd_id: str, vector: list, payload: dict):
    """Upserts a JD vector and its payload into Qdrant."""
    try:
        # Convert jd_id to UUID (required for Qdrant string IDs)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, jd_id))
        
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        logger.info(f"Upserted JD vector for {jd_id} (UUID: {point_id})")
    except Exception as e:
        logger.error(f"Error upserting JD to Qdrant: {e}")

def upsert_resume_vector(candidate_id: str, vector: list, payload: dict):
    """Upserts a resume vector and its payload into Qdrant."""
    try:
        # Convert candidate_id to UUID
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, candidate_id))
        
        client.upsert(
            collection_name=RESUME_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        logger.info(f"Upserted Resume vector for {candidate_id} (UUID: {point_id})")
    except Exception as e:
        logger.error(f"Error upserting Resume to Qdrant: {e}")

def get_jd_vector(jd_id: str):
    """Retrieves the vector for a specific JD."""
    try:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, jd_id))
        result = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_vectors=True
        )
        if result:
            return result[0].vector
        return None
    except Exception as e:
        logger.error(f"Error retrieving JD vector: {e}")
        return None

def search_resumes_by_vector(vector: list, limit: int = 100):
    """Searches for top resumes matching a vector."""
    try:
        results = client.search(
            collection_name=RESUME_COLLECTION,
            query_vector=vector,
            limit=limit,
            with_payload=True
        )
        return results
    except Exception as e:
        logger.error(f"Error searching resumes in Qdrant: {e}")
        return []

# Initialize on import
init_qdrant()
