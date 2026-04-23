import os
import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.qdrant_utils import get_jd_vector, search_resumes_by_vector
from utils.config_utils import get_matching_thresholds

logger = logging.getLogger(__name__)

@celery.task(name="tasks.matching_tasks.run_matching")
def run_matching(jd_id: str):
    """
    Pass 1: Speed Layer
    Uses Qdrant cosine similarity to filter the top-N candidates from the internal pool.
    """
    logger.info(f"Starting Pass 1 matching for JD: {jd_id}")
    db = get_db()
    
    # 1. Get JD Vector
    jd_vector = get_jd_vector(jd_id)
    if not jd_vector:
        logger.error(f"JD vector not found for {jd_id}")
        return {"error": "JD vector not found"}
        
    # 2. Search Qdrant for top candidates
    p_threshold, k_threshold = get_matching_thresholds()
    # Search for more than k_threshold to account for filtering, up to a reasonable cap
    results = search_resumes_by_vector(jd_vector, limit=50) 
    
    # 3. Filter and Format Results based on P-threshold
    matches = []
    rank = 1
    for res in results:
        score = res.score
        if score < p_threshold:
            logger.info(f"Candidate {res.payload.get('candidate_id')} below p_threshold ({score} < {p_threshold})")
            continue
            
        payload = res.payload
        candidate_id = payload.get("candidate_id")
        
        match_record = {
            "jd_id": jd_id,
            "candidate_id": candidate_id,
            "match_score": score,
            "rank": rank,
            "status": "pass_1",
            "source": payload.get("source", "internal"),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        matches.append(match_record)
        
        # Save/Upsert to candidate_pools
        db.candidate_pools.update_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"$set": match_record},
            upsert=True
        )
        
        rank += 1
        if rank > 20: # Cap Pass 1 results at top 20 for Pass 2 processing
            break
            
    logger.info(f"Pass 1 matching complete for {jd_id}. Found {len(matches)} matches above threshold {p_threshold}.")
    
    # 4. Check K-threshold for external sourcing fallback
    if len(matches) < k_threshold:
        logger.warning(f"K-threshold not met for {jd_id} ({len(matches)}/{k_threshold}). Flagging for external sourcing.")
        db.job_descriptions.update_one(
            {"jd_id": jd_id},
            {"$set": {"needs_external_sourcing": True, "sourcing_status": "pending"}}
        )
    else:
        db.job_descriptions.update_one(
            {"jd_id": jd_id},
            {"$set": {"needs_external_sourcing": False}}
        )
        
    # 5. Trigger Pass 2 (Intelligence Layer) if matches found
    if matches:
        logger.info(f"Triggering Pass 2 reasoning for {len(matches)} candidates...")
        run_pass_2.delay(jd_id)
    else:
        logger.warning(f"No candidates met P-threshold for {jd_id}. Pass 2 not triggered.")
        
    return {"jd_id": jd_id, "matches_count": len(matches), "pass_2_triggered": len(matches) > 0}

@celery.task(name="tasks.matching_tasks.run_pass_2")
def run_pass_2(jd_id: str):
    """
    Pass 2: Intelligence Layer (Stub)
    Deep reasoning on candidates using Gemini 2.5 Pro.
    To be implemented in TASK-008.
    """
    logger.info(f"Pass 2 reasoning (STUB) triggered for JD: {jd_id}")
    return {"jd_id": jd_id, "status": "stub_executed"}
