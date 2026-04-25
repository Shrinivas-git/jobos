from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from auth import get_current_user
from utils.client_utils import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(notifications: list) -> list:
    for n in notifications:
        n.pop("_id", None)
        if isinstance(n.get("created_at"), datetime):
            n["created_at"] = n["created_at"].isoformat()
    return notifications


@router.get("/")
async def list_notifications(user: dict = Depends(get_current_user)):
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="User email not in token")
    db = get_db()
    notifications = list(
        db.notifications.find({"recipient_email": email}).sort("created_at", -1).limit(50)
    )
    return _serialize(notifications)


@router.get("/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    email = user.get("email")
    if not email:
        return {"count": 0}
    db = get_db()
    count = db.notifications.count_documents({"recipient_email": email, "is_read": False})
    return {"count": count}


@router.put("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="User email not in token")
    db = get_db()
    db.notifications.update_many(
        {"recipient_email": email, "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"ok": True}


@router.put("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    email = user.get("email")
    db = get_db()
    result = db.notifications.update_one(
        {"notification_id": notification_id, "recipient_email": email},
        {"$set": {"is_read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}
