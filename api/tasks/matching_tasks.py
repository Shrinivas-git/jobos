import os
import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.qdrant_utils import get_jd_vector, search_resumes_by_vector
from utils.config_utils import get_matching_thresholds
from utils.gemini_utils import evaluate_candidate_fitment
from utils.storage_utils import save_candidate_match_results

logger = logging.getLogger(__name__)

def calculate_completeness_score(candidate: dict) -> float:
    """
    Simple logic to calculate profile completeness (0-100).
    """
    fields = ["name", "email", "phone", "skills", "experience_years", "location"]
    filled = 0
    for field in fields:
        val = candidate.get(field)
        if val and val not in ["Unknown", "Not specified", "null", []]:
            filled += 1
    return (filled / len(fields)) * 100

@celery.task(name="tasks.matching_tasks.run_matching")
def run_matching(jd_id: str, candidate_ids: list = None):
    """
    Pass 1: Speed Layer
    Uses Qdrant cosine similarity to filter the top-N candidates from the internal pool.
    If candidate_ids provided, only matches those specific candidates.
    """
    logger.info(f"Starting Pass 1 matching for JD: {jd_id}, filter: {len(candidate_ids) if candidate_ids else 'all'} candidates")
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

    # 3. Filter by candidate_ids if specified
    if candidate_ids:
        candidate_id_set = set(candidate_ids)
        results = [r for r in results if r.payload.get("candidate_id") in candidate_id_set]
        logger.info(f"Filtered to {len(results)} candidates from provided list")

    # 4. Filter and Format Results based on P-threshold
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
        
        # Save/Upsert to candidate_pools — never downgrade a pass_2_complete record
        db.candidate_pools.update_one(
            {"jd_id": jd_id, "candidate_id": candidate_id, "status": {"$ne": "pass_2_complete"}},
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
    Pass 2: Intelligence Layer
    Deep reasoning on candidates using Groq (llama-3.3-70b-versatile).
    """
    logger.info(f"Starting Pass 2 reasoning for JD: {jd_id}")
    db = get_db()
    
    # 1. Fetch JD data
    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        logger.error(f"JD {jd_id} not found")
        return {"error": "JD not found"}
    
    structured_jd = jd.get("structured_data")
    if not structured_jd:
        logger.error(f"Structured JD data missing for {jd_id}")
        return {"error": "Structured JD data missing"}

    # Fetch client slug for folder structure
    client = db.clients.find_one({"_id": jd.get("client_id")})
    if not client:
        # Fallback to finding by name if ObjectId mismatch
        client = db.clients.find_one({"slug": jd.get("client_slug", "unknown")})
    
    client_slug = client.get("slug", "unknown") if client else "unknown"

    # 2. Fetch candidates from Pass 1 — skip any already pass_2_complete
    pass_1_matches = list(db.candidate_pools.find(
        {"jd_id": jd_id, "status": {"$ne": "pass_2_complete"}}
    ).sort("rank", 1).limit(20))
    
    if not pass_1_matches:
        logger.warning(f"No Pass 1 matches found for {jd_id}")
        return {"status": "no_candidates"}

    # 3. Iterate and evaluate
    evaluated_count = 0
    for match in pass_1_matches:
        candidate_id = match["candidate_id"]
        logger.info(f"Evaluating candidate {candidate_id} for JD {jd_id}...")

        try:
            # Fetch full candidate record
            candidate = db.candidates.find_one({"candidate_id": candidate_id})
            if not candidate or not candidate.get("resume_text"):
                logger.warning(f"Resume text missing for candidate {candidate_id} — marking pass_2_skipped")
                db.candidate_pools.update_one(
                    {"jd_id": jd_id, "candidate_id": candidate_id},
                    {"$set": {
                        "status": "pass_2_skipped",
                        "skip_reason": "resume_text_missing",
                        "updated_at": datetime.now()
                    }}
                )
                continue

            # Call Claude reasoning
            recruiter_notes = jd.get("recruiter_notes") or None
            evaluation = evaluate_candidate_fitment(structured_jd, candidate["resume_text"], recruiter_notes)

            # Calculate completeness (display-only, no longer in composite)
            completeness = calculate_completeness_score(candidate)

            # Component scores
            fitment_score = float(evaluation.get("fitment_score", 0))
            cosine_score = float(match.get("match_score", 0)) * 100  # Normalize to 0-100 (Pass-1 gate only; not in composite)
            context_bonus = float(evaluation.get("context_bonus", 0))
            must_have_coverage_ratio = float(evaluation.get("must_have_coverage_ratio", 0.0))
            must_have_pct = must_have_coverage_ratio * 100  # 0-100
            rare_assets = evaluation.get("rare_assets", []) or []
            rare_asset_bonus = min(len(rare_assets) * 3, 9)  # 0-9

            # Certification tier bonus: Expert=+2, Mentor=+4 (Mentor is peer-recognised, very rare), capped at +8
            certs_assessed = evaluation.get("certifications_assessed", []) or []
            cert_tier_bonus = min(
                sum(4 if (c.get("tier") or "").lower() == "mentor" else 2
                    for c in certs_assessed
                    if (c.get("tier") or "").lower() in ("expert", "mentor")),
                8
            )

            # Quantified outcomes bonus: 0/1/3 based on count
            outcomes_count = int(evaluation.get("quantified_outcomes_count", 0) or 0)
            if outcomes_count >= 5:
                outcome_bonus = 3
            elif outcomes_count >= 1:
                outcome_bonus = 1
            else:
                outcome_bonus = 0  # 0-3

            # Emerging tech bonus: +3 if candidate has Agentforce or Data Cloud exposure
            # These are explicitly called out in the JD and rare among candidates
            emerging_keywords = {"agentforce", "data cloud"}
            candidate_skills_lower = {s.lower() for s in (candidate.get("structured_data") or {}).get("skills", [])}
            rare_assets_lower = {r.lower() for r in rare_assets}
            emerging_tech_bonus = 3 if emerging_keywords & (candidate_skills_lower | rare_assets_lower) else 0

            # Composite (cosine dropped from formula; now Pass-1 gate only):
            # 75% fitment + 10% must-have + 5% rare-asset + 5% cert tier + 5% outcomes + emerging tech bonus
            composite_score = (
                (fitment_score * 0.75)
                + (must_have_pct * 0.10)
                + ((rare_asset_bonus / 9.0 * 100) * 0.05 if rare_asset_bonus else 0)
                + ((cert_tier_bonus / 8.0 * 100) * 0.05 if cert_tier_bonus else 0)
                + ((outcome_bonus / 3.0 * 100) * 0.05 if outcome_bonus else 0)
                + emerging_tech_bonus
            )

            # Adjustments
            role_level_match = evaluation.get("role_level_match", "Unknown")
            tool_currency = evaluation.get("tool_currency", "None")
            key_tool_recency = evaluation.get("key_tool_recency", "Never")
            hard_filters_passed = evaluation.get("hard_filters_passed", True)

            if role_level_match == "Mismatch":
                composite_score -= 10
            if tool_currency == "Previous":
                composite_score -= 5
            if key_tool_recency == "Stale":
                composite_score -= 5
            if hard_filters_passed is False:
                composite_score = min(composite_score, 35)

            # Clamp to [0, 100]
            composite_score = max(0.0, min(100.0, composite_score))

            match_update = {
                "fitment_score": fitment_score,
                "completeness_score": completeness,
                "context_bonus": context_bonus,
                "must_have_coverage_ratio": must_have_coverage_ratio,
                "must_have_breakdown": evaluation.get("must_have_breakdown", []),
                "rare_asset_bonus": rare_asset_bonus,
                "cert_tier_bonus": cert_tier_bonus,
                "outcome_bonus": outcome_bonus,
                "emerging_tech_bonus": emerging_tech_bonus,
                "quantified_outcomes_count": outcomes_count,
                "certifications_assessed": certs_assessed,
                "composite_score": composite_score,
                "reasoning": evaluation.get("reasoning"),
                "strengths": evaluation.get("strengths"),
                "gaps": evaluation.get("gaps"),
                "recommendation": evaluation.get("recommendation"),
                "scoring_factors": evaluation.get("scoring_factors", []),
                "hard_filters_passed": hard_filters_passed,
                "hard_filter_failures": evaluation.get("hard_filter_failures", []),
                "role_level_detected": evaluation.get("role_level_detected", "Unknown"),
                "role_level_match": role_level_match,
                "tool_currency": tool_currency,
                "key_tool_recency": key_tool_recency,
                "cv_narrative_style": evaluation.get("cv_narrative_style", "Unknown"),
                "availability_signal": evaluation.get("availability_signal", "Unknown"),
                "availability_reason": evaluation.get("availability_reason", ""),
                "alternative_role_fit": evaluation.get("alternative_role_fit", ""),
                "rare_assets": rare_assets,
                "self_reported_unverified": evaluation.get("self_reported_unverified", []),
                "interview_flags": evaluation.get("interview_flags", []),
                "status": "pass_2_complete",
                "updated_at": datetime.now()
            }

            # Update MongoDB
            db.candidate_pools.update_one(
                {"jd_id": jd_id, "candidate_id": candidate_id},
                {"$set": match_update}
            )

            # Write to filesystem (match_score.json and pointer.json)
            pointer_data = {
                "candidate_id": candidate_id,
                "vector_id": str(candidate.get("vector_id", "")),
                "file_path": candidate.get("file_paths", [""])[0] if candidate.get("file_paths") else ""
            }

            save_candidate_match_results(
                client_slug,
                jd_id,
                candidate_id,
                match_update,
                pointer_data
            )

            evaluated_count += 1
        except Exception as eval_err:
            logger.exception(f"Pass 2 failed for candidate {candidate_id}: {eval_err}")
            db.candidate_pools.update_one(
                {"jd_id": jd_id, "candidate_id": candidate_id},
                {"$set": {
                    "status": "pass_2_failed",
                    "skip_reason": str(eval_err)[:300],
                    "updated_at": datetime.now()
                }}
            )
            continue
        
    # 4. Final Re-ranking based on composite_score
    all_matches = list(db.candidate_pools.find({"jd_id": jd_id}))
    # Sort by composite_score descending
    all_matches.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    
    for idx, match in enumerate(all_matches):
        db.candidate_pools.update_one(
            {"jd_id": jd_id, "candidate_id": match["candidate_id"]},
            {"$set": {"rank": idx + 1}}
        )

    logger.info(f"Pass 2 reasoning complete for {jd_id}. Evaluated {evaluated_count} candidates.")

    from tasks.notification_tasks import notify_pool_ready
    notify_pool_ready.delay(jd_id)

    return {"jd_id": jd_id, "evaluated_count": evaluated_count, "status": "complete"}
