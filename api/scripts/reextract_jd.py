"""
Re-extract structured_data for one or more JDs using the latest extract_jd_data prompt.

Run inside the api container:
    docker exec api python /app/scripts/reextract_jd.py JD-20260505-df10f1a7
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.client_utils import get_db
from utils.gemini_utils import extract_jd_data
from utils.resume_utils import extract_text_from_file


def reextract(jd_id: str) -> None:
    db = get_db()
    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        print(f"[ERR] JD not found: {jd_id}")
        return

    raw_text = jd.get("raw_text") or jd.get("raw") or ""
    if not raw_text:
        # Fallback: read the source file from disk
        folder = jd.get("folder_path")
        filename = jd.get("filename")
        if folder and filename:
            candidates = [
                os.path.join(folder, "raw", filename),
                os.path.join(folder, filename),
            ]
            for file_path in candidates:
                if os.path.exists(file_path):
                    print(f"raw_text not saved on JD record; reading from file: {file_path}")
                    raw_text = extract_text_from_file(file_path)
                    if raw_text:
                        break
        if not raw_text:
            print(f"[ERR] {jd_id}: could not load raw text from DB or disk.")
            return

    old = jd.get("structured_data", {}) or {}
    print(f"\n=== {jd_id} ===")
    print(f"Title (old): {old.get('title')}")
    print(f"Old skills count: {len(old.get('skills', []) or [])}")
    print(f"Old must_have_skills present: {'must_have_skills' in old}")
    print(f"Old nice_to_have_skills present: {'nice_to_have_skills' in old}")
    print(f"Old industries present: {'industries' in old}")

    print(f"\nRe-extracting with new prompt (this calls Claude)...")
    new_data = extract_jd_data(raw_text)

    print(f"\nTitle (new): {new_data.get('title')}")
    must = new_data.get("must_have_skills", []) or []
    nice = new_data.get("nice_to_have_skills", []) or []
    inds = new_data.get("industries", []) or []
    print(f"\nNew must_have_skills ({len(must)}):")
    for s in must:
        print(f"  - {s}")
    print(f"\nNew nice_to_have_skills ({len(nice)}):")
    for s in nice:
        print(f"  - {s}")
    print(f"\nNew industries: {inds}")

    db.job_descriptions.update_one(
        {"jd_id": jd_id},
        {"$set": {
            "structured_data": new_data,
            "reextracted_at": datetime.now(),
        }}
    )
    print(f"\n[OK] Updated structured_data for {jd_id}.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python /app/scripts/reextract_jd.py <jd_id> [<jd_id> ...]")
        sys.exit(1)
    for jd_id in sys.argv[1:]:
        reextract(jd_id)


if __name__ == "__main__":
    main()
