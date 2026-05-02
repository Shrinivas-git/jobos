from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid

from auth import check_role
from utils.client_utils import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])

TaskType = Literal["call", "follow_up", "document_request", "interview", "reminder", "custom"]
Priority = Literal["low", "medium", "high"]
CallOutcome = Literal["connected", "no_answer", "callback_requested"]


def _new_task_id() -> str:
    return f"RTASK-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in doc.items()}


def create_auto_task(
    db,
    task_type: str,
    description: str,
    owner_id: str,
    jd_id: str,
    candidate_id: str,
    priority: str,
    due_hours: int,
) -> dict:
    now = datetime.utcnow()
    doc = {
        "task_id": _new_task_id(),
        "type": task_type,
        "description": description,
        "owner_id": owner_id,
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "linked_type": "pipeline",
        "linked_id": f"{jd_id}:{candidate_id}",
        "priority": priority,
        "due_at": now + timedelta(hours=due_hours),
        "completed_at": None,
        "created_at": now,
        "created_by": "system",
        "notes": None,
        "call_outcome": None,
        "call_duration_mins": None,
    }
    db.recruiter_tasks.insert_one(doc)
    return doc


# ── Models ────────────────────────────────────────────────────────────────────

class CreateTaskBody(BaseModel):
    type: TaskType = "custom"
    description: str
    jd_id: Optional[str] = None
    candidate_id: Optional[str] = None
    priority: Priority = "medium"
    due_at: datetime
    notes: Optional[str] = None


class UpdateTaskBody(BaseModel):
    description: Optional[str] = None
    priority: Optional[Priority] = None
    due_at: Optional[datetime] = None
    notes: Optional[str] = None
    completed: Optional[bool] = None
    owner_id: Optional[str] = None


class LogCallBody(BaseModel):
    jd_id: Optional[str] = None
    candidate_id: Optional[str] = None
    outcome: CallOutcome
    duration_mins: Optional[int] = None
    notes: Optional[str] = None
    due_at: Optional[datetime] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_task(
    body: CreateTaskBody,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    now = datetime.utcnow()
    doc = {
        "task_id": _new_task_id(),
        "type": body.type,
        "description": body.description,
        "owner_id": user.get("sub", "unknown"),
        "jd_id": body.jd_id,
        "candidate_id": body.candidate_id,
        "linked_type": "pipeline" if (body.jd_id and body.candidate_id) else None,
        "linked_id": f"{body.jd_id}:{body.candidate_id}" if (body.jd_id and body.candidate_id) else None,
        "priority": body.priority,
        "due_at": body.due_at,
        "completed_at": None,
        "created_at": now,
        "created_by": user.get("sub", "unknown"),
        "notes": body.notes,
        "call_outcome": None,
        "call_duration_mins": None,
    }
    db.recruiter_tasks.insert_one(doc)
    return _serialize(doc)


@router.get("/")
async def list_tasks(
    owner_me: bool = False,
    overdue: bool = False,
    jd_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    completed: Optional[bool] = None,
    task_type: Optional[str] = None,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    query: dict = {}
    if owner_me:
        query["owner_id"] = user.get("sub")
    if overdue:
        query["due_at"] = {"$lt": datetime.utcnow()}
        query["completed_at"] = {"$eq": None}
    elif completed is not None:
        query["completed_at"] = {"$ne": None} if completed else {"$eq": None}
    if jd_id:
        query["jd_id"] = jd_id
    if candidate_id:
        query["candidate_id"] = candidate_id
    if task_type:
        query["type"] = task_type
    docs = list(db.recruiter_tasks.find(query).sort("due_at", 1).limit(200))
    return [_serialize(d) for d in docs]


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    doc = db.recruiter_tasks.find_one({"task_id": task_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize(doc)


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    body: UpdateTaskBody,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    doc = db.recruiter_tasks.find_one({"task_id": task_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")

    updates: dict = {}
    if body.description is not None:
        updates["description"] = body.description
    if body.priority is not None:
        updates["priority"] = body.priority
    if body.due_at is not None:
        updates["due_at"] = body.due_at
    if body.notes is not None:
        updates["notes"] = body.notes
    if body.owner_id is not None:
        updates["owner_id"] = body.owner_id
    if body.completed is True:
        updates["completed_at"] = datetime.utcnow()
    elif body.completed is False:
        updates["completed_at"] = None

    if updates:
        db.recruiter_tasks.update_one({"task_id": task_id}, {"$set": updates})

    updated = db.recruiter_tasks.find_one({"task_id": task_id})
    return _serialize(updated)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    result = db.recruiter_tasks.delete_one({"task_id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")


# ── Call logging ───────────────────────────────────────────────────────────────

@router.post("/calls", status_code=201)
async def log_call(
    body: LogCallBody,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    now = datetime.utcnow()
    doc = {
        "task_id": _new_task_id(),
        "type": "call",
        "description": f"Call logged — {body.outcome.replace('_', ' ')}",
        "owner_id": user.get("sub", "unknown"),
        "jd_id": body.jd_id,
        "candidate_id": body.candidate_id,
        "linked_type": "pipeline" if (body.jd_id and body.candidate_id) else None,
        "linked_id": f"{body.jd_id}:{body.candidate_id}" if (body.jd_id and body.candidate_id) else None,
        "priority": "medium",
        "due_at": body.due_at or now,
        "completed_at": now,
        "created_at": now,
        "created_by": user.get("sub", "unknown"),
        "notes": body.notes,
        "call_outcome": body.outcome,
        "call_duration_mins": body.duration_mins,
    }
    db.recruiter_tasks.insert_one(doc)
    return _serialize(doc)


@router.get("/calls/list")
async def list_calls(
    jd_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    query: dict = {"type": "call"}
    if jd_id:
        query["jd_id"] = jd_id
    if candidate_id:
        query["candidate_id"] = candidate_id
    docs = list(db.recruiter_tasks.find(query).sort("created_at", -1).limit(200))
    return [_serialize(d) for d in docs]
