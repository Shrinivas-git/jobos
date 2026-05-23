from utils.client_utils import get_db
db = get_db()
update = {"needs_external_sourcing": True, "sourcing_status": "awaiting_approval"}
result = db.job_descriptions.update_one({"jd_id": "JD-20260511-38431c3d"}, {"$set": update})
print("Modified:", result.modified_count)
