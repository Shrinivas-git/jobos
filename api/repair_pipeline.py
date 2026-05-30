"""One-off: rebuild pipeline_stages docs for already-shortlisted candidates
that have no stages (e.g. record deleted during the partial-doc cleanup).
Run inside the api container:  python repair_pipeline.py
"""
from utils.client_utils import get_db
from routers.pipeline import upsert_initial_stage

db = get_db()
fixed = 0
for c in db.candidate_pools.find({"status": "shortlisted"}):
    existing = db.pipeline_stages.find_one(
        {"jd_id": c["jd_id"], "candidate_id": c["candidate_id"]}
    )
    if existing and existing.get("stages"):
        continue
    doc = upsert_initial_stage(db, c["jd_id"], c["candidate_id"], "shortlist")
    fixed += 1
    print(f"repaired: {c['jd_id']} / {c['candidate_id']} -> {[s['name'] for s in doc['stages']]}")

print(f"done. {fixed} pipeline record(s) rebuilt.")
