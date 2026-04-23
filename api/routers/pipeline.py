from fastapi import APIRouter, Depends
from auth import check_role

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

@router.get("/status")
async def get_pipeline_status(user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    return {"message": "Pipeline status"}
