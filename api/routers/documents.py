import os
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import StreamingResponse
from auth import check_role
from utils.client_utils import get_db
from utils.storage_utils import save_document_file
from tasks.notification_tasks import notify_candidate_document_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# Document type → minimum tier required to access
DOC_TIER_MAP = {
    "experience": 2,
    "education":  3,
    "licence":    3,
    "identity":   4,
    "salary":     4,
}

# Pipeline stage → tier unlocked
STAGE_TIER_MAP = {
    "shortlist":        2,
    "interview_1":      3,
    "interview_final":  3,
    "offer":            4,
    "joined":           4,
}

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_candidate_tier(db, candidate_id: str, jd_id: str) -> int:
    """Return the highest tier unlocked for this candidate on this JD."""
    doc = db.pipeline_stages.find_one(
        {"jd_id": jd_id, "candidate_id": candidate_id},
        {"current_stage": 1}
    )
    if not doc:
        return 1
    return STAGE_TIER_MAP.get(doc.get("current_stage", ""), 1)


def _assert_doc_accessible(doc: dict, tier: int):
    if doc.get("access_revoked"):
        raise HTTPException(status_code=403, detail="Candidate has revoked access to this document")
    if not doc.get("consent_given"):
        raise HTTPException(status_code=403, detail="No consent recorded for this document")
    if tier < doc.get("tier_required", 99):
        raise HTTPException(
            status_code=403,
            detail=f"Document requires Tier {doc['tier_required']}; candidate is at Tier {tier} for this JD"
        )


def _log_access(db, doc: dict, accessor: dict, jd_id: str, access_type: str, tier: int, request: Request):
    db.document_access_log.insert_one({
        "log_id": str(uuid.uuid4()),
        "doc_id": doc["doc_id"],
        "candidate_id": doc["candidate_id"],
        "accessed_by": accessor.get("sub") or accessor.get("preferred_username", "unknown"),
        "accessor_role": (accessor.get("realm_access", {}).get("roles") or ["unknown"])[0],
        "accessor_email": accessor.get("email", ""),
        "jd_id": jd_id,
        "access_type": access_type,
        "doc_type": doc["doc_type"],
        "tier_at_access": tier,
        "timestamp": datetime.utcnow(),
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", ""),
    })


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------
@router.post("/upload")
async def upload_document(
    doc_type: str = Form(...),
    consent: bool = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(check_role(["candidate"])),
):
    """Candidate uploads a document. Explicit consent=true is mandatory."""
    if not consent:
        raise HTTPException(status_code=400, detail="Explicit consent is required to upload documents")

    if doc_type not in DOC_TIER_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type. Allowed: {list(DOC_TIER_MAP.keys())}"
        )

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    candidate_id = user.get("preferred_username") or user.get("sub")
    doc_id = f"DOC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

    stored_path = save_document_file(candidate_id, doc_id, ext, content)

    db = get_db()
    now = datetime.utcnow()
    db.documents.insert_one({
        "doc_id": doc_id,
        "candidate_id": candidate_id,
        "doc_type": doc_type,
        "tier_required": DOC_TIER_MAP[doc_type],
        "original_filename": file.filename,
        "stored_path": stored_path,
        "consent_given": True,
        "consent_timestamp": now,
        "access_revoked": False,
        "revoked_at": None,
        "uploaded_at": now,
    })

    logger.info(f"Document uploaded: {doc_id} by {candidate_id} (type={doc_type})")
    return {"doc_id": doc_id, "doc_type": doc_type, "tier_required": DOC_TIER_MAP[doc_type]}


# ---------------------------------------------------------------------------
# GET /documents/list
# ---------------------------------------------------------------------------
@router.get("/list")
async def list_documents(
    candidate_id: str = Query(...),
    jd_id: str = Query(...),
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"])),
):
    """Return documents accessible for this candidate on this JD (tier-filtered)."""
    db = get_db()
    tier = _get_candidate_tier(db, candidate_id, jd_id)

    docs = list(db.documents.find(
        {
            "candidate_id": candidate_id,
            "consent_given": True,
            "access_revoked": False,
            "tier_required": {"$lte": tier},
        },
        {"_id": 0, "stored_path": 0}
    ))

    return {
        "candidate_id": candidate_id,
        "jd_id": jd_id,
        "unlocked_tier": tier,
        "documents": docs,
    }


# ---------------------------------------------------------------------------
# GET /documents/{doc_id}/view
# ---------------------------------------------------------------------------
@router.get("/{doc_id}/view")
async def view_document(
    doc_id: str,
    jd_id: str = Query(...),
    request: Request = None,
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"])),
):
    """Stream a document (view-only). Logs access and notifies the candidate."""
    db = get_db()
    doc = db.documents.find_one({"doc_id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    tier = _get_candidate_tier(db, doc["candidate_id"], jd_id)
    _assert_doc_accessible(doc, tier)

    path = doc["stored_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Document file missing from storage")

    _log_access(db, doc, user, jd_id, "view", tier, request)

    accessor_email = user.get("email", "")
    notify_candidate_document_access.delay(
        doc_id=doc_id,
        candidate_id=doc["candidate_id"],
        doc_type=doc["doc_type"],
        accessor_email=accessor_email,
        access_type="view",
    )

    ext = path.rsplit(".", 1)[-1].lower()
    media_type = "application/pdf" if ext == "pdf" else f"image/{ext}" if ext in {"jpg", "jpeg", "png"} else "application/octet-stream"

    def _stream():
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        _stream(),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{doc["original_filename"]}"'},
    )


# ---------------------------------------------------------------------------
# GET /documents/{doc_id}/download
# ---------------------------------------------------------------------------
@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    jd_id: str = Query(...),
    request: Request = None,
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"])),
):
    """Download a document. Requires Tier 4 (offer stage)."""
    db = get_db()
    doc = db.documents.find_one({"doc_id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    tier = _get_candidate_tier(db, doc["candidate_id"], jd_id)
    _assert_doc_accessible(doc, tier)

    if tier < 4:
        raise HTTPException(status_code=403, detail="Downloads are only unlocked at Tier 4 (offer stage)")

    path = doc["stored_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Document file missing from storage")

    _log_access(db, doc, user, jd_id, "download", tier, request)

    notify_candidate_document_access.delay(
        doc_id=doc_id,
        candidate_id=doc["candidate_id"],
        doc_type=doc["doc_type"],
        accessor_email=user.get("email", ""),
        access_type="download",
    )

    def _stream():
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        _stream(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc["original_filename"]}"'},
    )


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id}/consent
# ---------------------------------------------------------------------------
@router.delete("/{doc_id}/consent")
async def revoke_consent(
    doc_id: str,
    user: dict = Depends(check_role(["candidate"])),
):
    """Candidate revokes consent. Blocked if they are at offer/joined stage in any active pipeline."""
    db = get_db()
    candidate_id = user.get("preferred_username") or user.get("sub")

    doc = db.documents.find_one({"doc_id": doc_id, "candidate_id": candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or not owned by you")

    if doc.get("access_revoked"):
        raise HTTPException(status_code=400, detail="Consent already revoked")

    # Block revocation during active offer
    active_offer = db.pipeline_stages.find_one({
        "candidate_id": candidate_id,
        "current_stage": {"$in": ["offer", "joined"]},
    })
    if active_offer:
        raise HTTPException(
            status_code=403,
            detail="Cannot revoke consent while an active offer is in progress"
        )

    db.documents.update_one(
        {"doc_id": doc_id},
        {"$set": {"access_revoked": True, "revoked_at": datetime.utcnow()}}
    )

    logger.info(f"Consent revoked: {doc_id} by {candidate_id}")
    return {"ok": True, "doc_id": doc_id, "message": "Consent revoked; document is no longer accessible"}


# ---------------------------------------------------------------------------
# GET /documents/access-log
# ---------------------------------------------------------------------------
@router.get("/access-log")
async def get_access_log(
    candidate_id: Optional[str] = Query(None),
    doc_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(check_role(["recruiter", "manager", "hod", "admin"])),
):
    """Immutable audit log. Filter by candidate_id or doc_id."""
    if not candidate_id and not doc_id:
        raise HTTPException(status_code=400, detail="Provide candidate_id or doc_id")

    db = get_db()
    query: dict = {}
    if candidate_id:
        query["candidate_id"] = candidate_id
    if doc_id:
        query["doc_id"] = doc_id

    logs = list(
        db.document_access_log.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return {"total": len(logs), "logs": logs}
