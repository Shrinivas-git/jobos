from fastapi import APIRouter, Depends
from auth import check_role

router = APIRouter(prefix="/crm", tags=["crm"])

@router.get("/messages")
async def get_messages(user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    return {"message": "CRM messages"}
