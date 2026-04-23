from fastapi import APIRouter, Depends
from auth import check_role

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/vault")
async def get_document_vault(user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"]))):
    return {"message": "Document vault access"}
