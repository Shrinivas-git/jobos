from utils.client_utils import get_db

db = get_db()

# Reset all JDs that are wrongly showing "pending" back to awaiting_approval
# so they show the button but don't auto-fetch
result = db.job_descriptions.update_many(
    {"sourcing_status": "pending"},
    {"$set": {"sourcing_status": "awaiting_approval"}}
)
print(f"Reset {result.modified_count} JDs from pending -> awaiting_approval")

# Also clear the flag on JDs that should NOT have it
# (only JD-20260511-38431c3d was intentionally flagged for testing)
result2 = db.job_descriptions.update_many(
    {
        "needs_external_sourcing": True,
        "jd_id": {"$ne": "JD-20260511-38431c3d"}
    },
    {"$set": {"needs_external_sourcing": False, "sourcing_status": None}}
)
print(f"Cleared flag from {result2.modified_count} other JDs")
