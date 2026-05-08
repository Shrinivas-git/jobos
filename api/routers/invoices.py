from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from auth import check_role
from utils.client_utils import get_db

router = APIRouter(prefix="/invoices", tags=["invoices"])


class MarkPaidBody(BaseModel):
    paid_at: Optional[str] = None  # ISO string, defaults to now


@router.get("/")
async def list_invoices(
    status: Optional[str] = None,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    query = {}
    if status:
        query["payment_status"] = status
    invoices = list(db.invoices.find(query, {"_id": 0}).sort("generated_at", -1))
    return invoices


@router.patch("/{invoice_id}/mark-paid")
async def mark_paid(
    invoice_id: str,
    body: MarkPaidBody,
    user: dict = Depends(check_role(["manager", "admin"])),
):
    db = get_db()
    paid_at = datetime.fromisoformat(body.paid_at) if body.paid_at else datetime.utcnow()
    result = db.invoices.update_one(
        {"invoice_id": invoice_id},
        {"$set": {"payment_status": "paid", "paid_at": paid_at}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"ok": True, "invoice_id": invoice_id, "payment_status": "paid"}


@router.patch("/{invoice_id}/mark-unpaid")
async def mark_unpaid(
    invoice_id: str,
    user: dict = Depends(check_role(["manager", "admin"])),
):
    db = get_db()
    result = db.invoices.update_one(
        {"invoice_id": invoice_id},
        {"$set": {"payment_status": "unpaid", "paid_at": None}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"ok": True, "invoice_id": invoice_id, "payment_status": "unpaid"}
