from fastapi import APIRouter, Depends
from auth import check_role

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/dashboard")
async def get_analytics(user: dict = Depends(check_role(["manager", "admin", "hod"]))):
    return {"message": "Analytics data"}
