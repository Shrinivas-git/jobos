#!/usr/bin/env python3
"""
Migration script to extract and populate contextual fields for existing candidates.

Fetches all candidates missing contextual fields (company_types, avg_team_size, role_type),
re-extracts metadata from their resume files, and updates MongoDB + Qdrant.
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path so we can import from api modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db
from utils.gemini_utils import extract_resume_metadata, generate_embedding
from utils.qdrant_utils import upsert_resume_vector
from utils.resume_utils import extract_text_from_file

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_contextual_fields():
    """Main migration function."""
    db = get_db()

    # Find all candidates missing contextual fields
    query = {
        "$or": [
            {"company_types": {"$exists": False}},
            {"company_types": None},
            {"company_types": []},
            {"avg_team_size": {"$exists": False}},
            {"avg_team_size": None},
            {"role_type": {"$exists": False}},
            {"role_type": None}
        ]
    }

    candidates = list(db.candidates.find(query))
    total = len(candidates)

    if total == 0:
        logger.info("No candidates need migration. All have contextual fields.")
        return

    logger.info(f"Found {total} candidates needing contextual field extraction.")

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for idx, candidate in enumerate(candidates, 1):
        candidate_id = candidate.get("candidate_id")
        file_paths = candidate.get("file_paths", [])

        try:
            # Get the first (primary) resume file
            if not file_paths:
                logger.warning(f"[{idx}/{total}] Skipping {candidate_id}: no file_paths")
                skipped_count += 1
                continue

            file_path = file_paths[0]

            # Check file exists
            if not os.path.exists(file_path):
                logger.warning(f"[{idx}/{total}] Skipping {candidate_id}: file not found at {file_path}")
                skipped_count += 1
                continue

            logger.info(f"[{idx}/{total}] Extracting metadata for {candidate_id}...")

            # Extract text from resume
            resume_text = extract_text_from_file(file_path)
            if not resume_text:
                logger.warning(f"[{idx}/{total}] Skipping {candidate_id}: failed to extract text")
                skipped_count += 1
                continue

            # Extract metadata
            metadata = extract_resume_metadata(resume_text)

            company_types = metadata.get("company_types", [])
            avg_team_size = metadata.get("avg_team_size", "Unknown")
            role_type = metadata.get("role_type", "Unknown")

            # Update MongoDB candidate record
            db.candidates.update_one(
                {"candidate_id": candidate_id},
                {
                    "$set": {
                        "company_types": company_types,
                        "avg_team_size": avg_team_size,
                        "role_type": role_type,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )

            # Update Qdrant resume_vectors payload
            vector_id = candidate.get("vector_id")
            if vector_id:
                # Generate embedding from resume text
                embedding = generate_embedding(resume_text)

                # Upsert with updated payload
                upsert_resume_vector(
                    vector_id=vector_id,
                    embedding=embedding,
                    payload={
                        "candidate_id": candidate_id,
                        "name": candidate.get("name"),
                        "email": candidate.get("email"),
                        "phone": candidate.get("phone"),
                        "skills": metadata.get("skills", []),
                        "experience_years": metadata.get("experience_years", 0),
                        "location": metadata.get("location", "Not specified"),
                        "source": candidate.get("source", "internal"),
                        "file_path": file_path,
                        "company_types": company_types,
                        "avg_team_size": avg_team_size,
                        "role_type": role_type,
                    }
                )

            logger.info(
                f"[{idx}/{total}] Updated {candidate_id}: "
                f"company_types={company_types}, avg_team_size={avg_team_size}, role_type={role_type}"
            )
            updated_count += 1

        except Exception as e:
            logger.error(f"[{idx}/{total}] Error processing {candidate_id}: {str(e)}", exc_info=True)
            error_count += 1

    # Summary
    logger.info("=" * 80)
    logger.info("MIGRATION COMPLETE")
    logger.info(f"  Updated:   {updated_count}/{total}")
    logger.info(f"  Skipped:   {skipped_count}/{total}")
    logger.info(f"  Errors:    {error_count}/{total}")
    logger.info("=" * 80)


if __name__ == "__main__":
    migrate_contextual_fields()
