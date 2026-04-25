from fastapi import APIRouter, Depends
from datetime import datetime
from auth import get_current_user
from utils.client_utils import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):
    email = user.get("email")
    username = user.get("preferred_username")
    roles = user.get("realm_access", {}).get("roles", [])

    if email:
        db = get_db()
        db.users.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "username": username,
                "roles": roles,
                "last_seen": datetime.utcnow(),
            }},
            upsert=True,
        )

    return {
        "username": username,
        "email": email,
        "roles": roles,
        "full_payload": user,
    }
