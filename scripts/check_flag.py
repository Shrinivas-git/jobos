from utils.client_utils import get_db
db = get_db()
jd = db.job_descriptions.find_one({"jd_id": "JD-20260511-38431c3d"}, {"needs_external_sourcing": 1, "sourcing_status": 1})
print(jd)
