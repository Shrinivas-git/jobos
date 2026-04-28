#!/usr/bin/env python3
"""
Sync all candidate fields from MongoDB to Qdrant resume_vectors payloads.
Does NOT regenerate embeddings — only updates payload fields.
"""

import sys
import os
import uuid
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db
from utils.qdrant_utils import client, RESUME_COLLECTION

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PAYLOAD_FIELDS = [
    "candidate_id", "name", "email", "phone",
    "skills", "experience_years", "location", "notice_period",
    "gender", "college", "company_types", "avg_team_size", "role_type",
    "projects", "education", "certifications", "achievements",
    "languages", "previous_companies", "companies_switched", "source",
]

def sync():
    db = get_db()
    candidates = list(db.candidates.find({}, {"_id": 0, "resume_text": 0}))
    total = len(candidates)

    if total == 0:
        logger.info("No candidates found.")
        return

    logger.info(f"Syncing {total} candidates to Qdrant...")
    updated = 0
    errors = 0

    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            continue
        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, candidate_id))
            payload = {k: candidate[k] for k in PAYLOAD_FIELDS if k in candidate and candidate[k] is not None}

            client.set_payload(
                collection_name=RESUME_COLLECTION,
                payload=payload,
                points=[point_id],
            )
            logger.info(
                f"  {candidate_id}: skills={len(payload.get('skills', []))}, "
                f"company_types={payload.get('company_types', [])}, "
                f"avg_team_size={payload.get('avg_team_size', 'N/A')}"
            )
            updated += 1
        except Exception as e:
            logger.error(f"  Error syncing {candidate_id}: {e}")
            errors += 1

    logger.info("=" * 60)
    logger.info(f"DONE — Updated: {updated}/{total}  Errors: {errors}/{total}")
    logger.info("=" * 60)

if __name__ == "__main__":
    sync()
