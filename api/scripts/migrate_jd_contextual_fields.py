#!/usr/bin/env python3
"""
Migration script to add contextual fields to existing JD records.

For test JDs, sets default contextual preferences to enable contextual scoring.
In production, these would come from client requirements.
"""

import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_jd_contextual_fields():
    """Migrate JD records to add contextual preference fields."""
    db = get_db()

    # Find all JDs missing contextual fields
    query = {
        "$or": [
            {"preferred_company_type": {"$exists": False}},
            {"preferred_company_type": None},
            {"preferred_company_type": []},
            {"preferred_team_size": {"$exists": False}},
            {"preferred_team_size": None},
            {"role_type": {"$exists": False}},
            {"role_type": None},
        ]
    }

    jds = list(db.job_descriptions.find(query))
    total = len(jds)

    if total == 0:
        logger.info("No JDs need migration. All have contextual fields.")
        return

    logger.info(f"Found {total} JDs needing contextual field migration.")

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for idx, jd in enumerate(jds, 1):
        jd_id = jd.get("jd_id")
        title = jd.get("title", "Unknown")

        try:
            # Set reasonable defaults for contextual preferences
            # These enable contextual matching without restricting candidates
            preferred_company_type = jd.get("preferred_company_type") or [
                "Fintech", "Edtech", "Ecommerce", "Healthcare", "Product", "Services", "Startup", "Large Enterprise"
            ]
            preferred_team_size = jd.get("preferred_team_size") or "Any"
            role_type = jd.get("role_type") or "Any"

            # Update JD record
            db.job_descriptions.update_one(
                {"jd_id": jd_id},
                {
                    "$set": {
                        "preferred_company_type": preferred_company_type,
                        "preferred_team_size": preferred_team_size,
                        "role_type": role_type,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )

            logger.info(
                f"[{idx}/{total}] Updated {jd_id} ({title}): "
                f"preferred_company_type={len(preferred_company_type)} types, "
                f"preferred_team_size={preferred_team_size}, role_type={role_type}"
            )
            updated_count += 1

        except Exception as e:
            logger.error(f"[{idx}/{total}] Error processing {jd_id}: {str(e)}", exc_info=True)
            error_count += 1

    # Summary
    logger.info("=" * 80)
    logger.info("JD MIGRATION COMPLETE")
    logger.info(f"  Updated:   {updated_count}/{total}")
    logger.info(f"  Skipped:   {skipped_count}/{total}")
    logger.info(f"  Errors:    {error_count}/{total}")
    logger.info("=" * 80)


if __name__ == "__main__":
    migrate_jd_contextual_fields()
