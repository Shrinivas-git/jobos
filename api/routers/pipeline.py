from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

from auth import check_role
from utils.client_utils import get_db
from utils.config_utils import get_pipeline_config
from routers.recruiter_tasks import create_auto_task

# stage → (task_type, description_template, priority, due_hours)
_STAGE_TASK_MAP = {
    "shortlist":  ("follow_up",  "Initial outreach to candidate {cid} for {jid}", "medium", 72),
    "interview":  ("interview",  "Schedule interview call for candidate {cid} ({jid})", "high",   24),
    "offer":      ("reminder",   "Prepare offer letter for candidate {cid} ({jid})", "high",   48),
}

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _serialize(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


def _build_stage(name: str, sla_hours: int, now: datetime) -> dict:
    return {
        "name": name,
        "entered_at": now,
        "sla_hours": sla_hours,
        "due_at": now + timedelta(hours=sla_hours),
        "warned_at": None,
        "escalated_at": None,
        "completed_at": None,
        "extension": None,
    }


def upsert_initial_stage(db, jd_id: str, candidate_id: str, stage_name: str = "shortlist") -> dict:
    """Create the first pipeline stage for a candidate when they enter the pipeline.

    Idempotent — if a doc already exists for (jd_id, candidate_id), returns it untouched.
    """
    existing = db.pipeline_stages.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
    if existing:
        return existing
    cfg = get_pipeline_config()
    sla = int(cfg["sla_hours"].get(stage_name, 72))
    now = datetime.utcnow()
    doc = {
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "current_stage": stage_name,
        "stages": [_build_stage(stage_name, sla, now)],
        "created_at": now,
        "updated_at": now,
    }
    db.pipeline_stages.insert_one(doc)
    return doc


@router.get("/status")
async def get_pipeline_status(user: dict = Depends(check_role(["recruiter", "manager", "admin"]))):
    return {"message": "Pipeline status"}


@router.get("/breaches")
async def list_breaches(
    user: dict = Depends(check_role(["manager", "admin"])),
):
    """All pipelines whose current stage is past due_at (with no active extension)."""
    db = get_db()
    now = datetime.utcnow()
    docs = list(db.pipeline_stages.find({}))
    out = []
    for d in docs:
        current = d.get("current_stage")
        stage = next((s for s in d.get("stages", []) if s.get("name") == current), None)
        if not stage or stage.get("completed_at"):
            continue
        ext = stage.get("extension")
        effective_due = stage.get("due_at")
        if ext and ext.get("approved") and ext.get("approved_until"):
            effective_due = ext["approved_until"]
        if effective_due and effective_due < now:
            out.append({
                "jd_id": d.get("jd_id"),
                "candidate_id": d.get("candidate_id"),
                "stage": current,
                "due_at": effective_due,
                "escalated": bool(stage.get("escalated_at")),
            })
    return out


@router.get("/{jd_id}")
async def list_pipeline_for_jd(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    docs = list(db.pipeline_stages.find({"jd_id": jd_id}))
    return [_serialize(d) for d in docs]


class AdvanceBody(BaseModel):
    next_stage: Optional[str] = None


@router.post("/advance/{jd_id}/{candidate_id}")
async def advance_stage(
    jd_id: str,
    candidate_id: str,
    body: AdvanceBody,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    cfg = get_pipeline_config()
    order = cfg["stage_order"]
    sla_map = cfg["sla_hours"]

    doc = db.pipeline_stages.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found for this candidate")

    current = doc.get("current_stage")
    if not current:
        raise HTTPException(status_code=400, detail="No current stage set")

    if body.next_stage:
        next_name = body.next_stage
        if next_name not in order:
            raise HTTPException(status_code=400, detail=f"Unknown stage '{next_name}'")
    else:
        try:
            idx = order.index(current)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Current stage '{current}' not in stage_order")
        if idx + 1 >= len(order):
            raise HTTPException(status_code=400, detail="Already at final stage")
        next_name = order[idx + 1]

    now = datetime.utcnow()
    stages = doc.get("stages", [])
    cur_idx = next((i for i, s in enumerate(stages) if s.get("name") == current), -1)
    if cur_idx < 0:
        raise HTTPException(status_code=500, detail="Inconsistent state: current stage missing from stages array")

    stages[cur_idx]["completed_at"] = now
    stages.append(_build_stage(next_name, int(sla_map.get(next_name, 72)), now))

    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {"stages": stages, "current_stage": next_name, "updated_at": now}},
    )

    if next_name in _STAGE_TASK_MAP:
        t_type, tmpl, priority, due_h = _STAGE_TASK_MAP[next_name]
        desc = tmpl.format(cid=candidate_id, jid=jd_id)
        owner = user.get("sub", "unknown")
        try:
            create_auto_task(db, t_type, desc, owner, jd_id, candidate_id, priority, due_h)
        except Exception:
            pass  # task creation must never block pipeline advance

    return {"ok": True, "current_stage": next_name}


class ExtensionRequest(BaseModel):
    jd_id: str
    candidate_id: str
    additional_hours: int
    reason: str


@router.post("/extension-request")
async def request_extension(
    body: ExtensionRequest,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    if body.additional_hours <= 0:
        raise HTTPException(status_code=400, detail="additional_hours must be positive")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="Reason required")

    db = get_db()
    doc = db.pipeline_stages.find_one({"jd_id": body.jd_id, "candidate_id": body.candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    current = doc.get("current_stage")
    stages = doc.get("stages", [])
    cur_idx = next((i for i, s in enumerate(stages) if s.get("name") == current), -1)
    if cur_idx < 0:
        raise HTTPException(status_code=500, detail="Current stage missing")

    now = datetime.utcnow()
    stages[cur_idx]["extension"] = {
        "requested_at": now,
        "requested_by": user.get("sub", "unknown"),
        "additional_hours": body.additional_hours,
        "reason": body.reason,
        "approved": False,
        "approved_until": None,
        "approved_by": None,
        "approved_at": None,
    }
    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {"stages": stages, "updated_at": now}},
    )
    return {"ok": True, "stage": current}


class ExtensionDecision(BaseModel):
    jd_id: str
    candidate_id: str
    approve: bool


@router.post("/extension-approve")
async def decide_extension(
    body: ExtensionDecision,
    user: dict = Depends(check_role(["manager", "admin"])),
):
    db = get_db()
    doc = db.pipeline_stages.find_one({"jd_id": body.jd_id, "candidate_id": body.candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    current = doc.get("current_stage")
    stages = doc.get("stages", [])
    cur_idx = next((i for i, s in enumerate(stages) if s.get("name") == current), -1)
    if cur_idx < 0:
        raise HTTPException(status_code=500, detail="Current stage missing")

    ext = stages[cur_idx].get("extension")
    if not ext:
        raise HTTPException(status_code=400, detail="No extension request to decide on")

    now = datetime.utcnow()
    ext["approved"] = bool(body.approve)
    ext["approved_by"] = user.get("sub", "unknown")
    ext["approved_at"] = now
    if body.approve:
        base_due = stages[cur_idx].get("due_at") or now
        if base_due < now:
            base_due = now
        ext["approved_until"] = base_due + timedelta(hours=int(ext.get("additional_hours", 0)))
        stages[cur_idx]["escalated_at"] = None

    stages[cur_idx]["extension"] = ext
    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {"stages": stages, "updated_at": now}},
    )
    return {"ok": True, "approved": ext["approved"], "approved_until": ext.get("approved_until")}
