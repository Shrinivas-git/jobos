#!/usr/bin/env python3
"""
Sync all JD fields from MongoDB to Qdrant jd_vectors payloads.
Does NOT regenerate embeddings — only updates payload fields in-place.
"""

import sys
import os
import uuid
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db
from utils.qdrant_utils import client, COLLECTION_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def sync():
    db = get_db()
    jds = list(db.job_descriptions.find({}, {"_id": 0}))
    total = len(jds)

    if total == 0:
        logger.info("No JDs found.")
        return

    logger.info(f"Syncing {total} JDs to Qdrant...")
    updated = 0
    errors = 0

    for jd in jds:
        jd_id = jd.get("jd_id")
        if not jd_id:
            continue

        sd = jd.get("structured_data") or {}

        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, jd_id))

            payload = {
                "jd_id":                  jd_id,
                "client_id":              str(jd.get("client_id", "")),
                "title":                  sd.get("title") or jd.get("title", ""),
                "level":                  sd.get("level", ""),
                "responsibilities":       sd.get("responsibilities", ""),
                "skills":                 sd.get("skills", []),
                "location":               sd.get("location", ""),
                "work_structure":         sd.get("work_structure", ""),
                "relevant_experience":    sd.get("relevant_experience", 0),
                "total_experience":       sd.get("total_experience", 0),
                "compensation_range":     sd.get("compensation_range", ""),
                "gender_preference":      sd.get("gender_preference", "Any"),
                "college_preference":     sd.get("college_preference", ""),
                "college_exclusion":      sd.get("college_exclusion", ""),
                "urgency":                sd.get("urgency", "Medium"),
                "num_positions":          sd.get("num_positions", 1),
                "hiring_timeline":        sd.get("hiring_timeline", ""),
                "kpis":                   sd.get("kpis", ""),
                "preferred_company_type": sd.get("preferred_company_type", []),
                "preferred_team_size":    sd.get("preferred_team_size", "Any"),
                "role_type":              sd.get("role_type", "Any"),
                "status":                 jd.get("status", "structured"),
                "created_at":             jd.get("created_at", "").isoformat() if hasattr(jd.get("created_at", ""), "isoformat") else str(jd.get("created_at", "")),
            }

            client.set_payload(
                collection_name=COLLECTION_NAME,
                payload=payload,
                points=[point_id],
            )
            logger.info(
                f"  {jd_id} ({payload['title']}): "
                f"preferred_company_type={payload['preferred_company_type']}, "
                f"role_type={payload['role_type']}"
            )
            updated += 1

        except Exception as e:
            logger.error(f"  Error syncing {jd_id}: {e}")
            errors += 1

    logger.info("=" * 60)
    logger.info(f"DONE — Updated: {updated}/{total}  Errors: {errors}/{total}")
    logger.info("=" * 60)


if __name__ == "__main__":
    sync()
