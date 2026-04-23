from fastapi import APIRouter, Depends
from auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {
        "username": user.get("preferred_username"),
        "email": user.get("email"),
        "roles": user.get("realm_access", {}).get("roles", []),
        "full_payload": user
    }
