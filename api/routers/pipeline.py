from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import secrets
import os
import shutil

from auth import check_role
from utils.client_utils import get_db
from utils.config_utils import get_pipeline_config
from routers.recruiter_tasks import create_auto_task
from tasks.invoice_tasks import generate_and_send_invoice
from tasks.retention_tasks import start_retention_clock
from tasks.notification_tasks import send_client_package, send_candidate_profile_to_client

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
    if existing and existing.get("stages"):
        return existing
    cfg = get_pipeline_config()
    sla = int(cfg["sla_hours"].get(stage_name, 72))
    now = datetime.utcnow()

    # Build planned_stages from JD pipeline_config (fallback: 0 assessments, 1 interview)
    jd = db.job_descriptions.find_one({"jd_id": jd_id}, {"pipeline_config": 1})
    pipeline_cfg = (jd or {}).get("pipeline_config") or {}
    assessment_rounds = int(pipeline_cfg.get("assessment_rounds", 0))
    interview_rounds = int(pipeline_cfg.get("interview_rounds", 1))
    planned_stages = _generate_planned_stages(assessment_rounds, interview_rounds)

    # Initialize response_tracking for all stages
    response_tracking = {
        "form_submitted": {
            "status": "pending",
            "reminder_count": 0,
        },
        "interview_availability": {
            "status": "pending",
            "reminder_count": 0,
        },
        "interest_confirmation": {
            "status": "pending",
            "reminder_count": 0,
        },
        "offer_acceptance": {
            "status": "pending",
            "reminder_count": 0,
        },
        "client_feedback": {
            "status": "pending",
            "reminder_count": 0,
        },
    }

    doc = {
        "jd_id": jd_id,
        "candidate_id": candidate_id,
        "current_stage": stage_name,
        "planned_stages": planned_stages,
        "stages": [_build_stage(stage_name, sla, now)],
        "response_tracking": response_tracking,
        "created_at": now,
        "updated_at": now,
    }
    if existing:
        # Repair a partial doc (e.g. created by an early form submission): keep its
        # response_tracking/created_at, fill in the missing stage fields.
        doc["response_tracking"] = {**doc["response_tracking"], **existing.get("response_tracking", {})}
        doc["created_at"] = existing.get("created_at", now)
        db.pipeline_stages.update_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"$set": doc},
        )
    else:
        db.pipeline_stages.insert_one(doc)
    return doc


@router.post("/send-to-client/{jd_id}")
async def send_to_client(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    client_email = jd.get("client_email")
    if not client_email:
        raise HTTPException(status_code=400, detail="No client_email set on this JD")

    evaluated = list(db.candidate_pools.find({"jd_id": jd_id, "status": {"$in": ["pass_2_complete", "shortlisted"]}}).sort("rank", 1))
    if not evaluated:
        raise HTTPException(status_code=400, detail="No evaluated candidates for this JD — run matching first")

    now = datetime.utcnow()
    candidate_ids = [c["candidate_id"] for c in evaluated]
    db.client_submissions.update_one(
        {"jd_id": jd_id},
        {"$set": {
            "jd_id": jd_id,
            "client_email": client_email,
            "candidate_ids": candidate_ids,
            "status": "sent",
            "sent_at": now,
            "sent_by": user.get("sub", "unknown"),
        }},
        upsert=True,
    )

    send_client_package.delay(jd_id, client_email)

    return {
        "ok": True,
        "client_email": client_email,
        "candidates_sent": len(evaluated),
        "sent_at": now.isoformat(),
    }


@router.post("/send-profile-to-client/{jd_id}/{candidate_id}")
async def send_profile_to_client(
    jd_id: str,
    candidate_id: str,
    recruiter_note: Optional[str] = None,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    """Send a single candidate's full profile (resume + video analysis) to the client."""
    db = get_db()
    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    client_email = jd.get("client_email")
    if not client_email:
        raise HTTPException(status_code=400, detail="No client_email set on this JD")

    candidate = db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    send_candidate_profile_to_client.delay(jd_id, candidate_id, client_email, recruiter_note or "")

    return {
        "ok": True,
        "client_email": client_email,
        "candidate_id": candidate_id,
        "sent_at": datetime.utcnow().isoformat()
    }


@router.get("/submission-status/{jd_id}")
async def get_submission_status(
    jd_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    db = get_db()
    doc = db.client_submissions.find_one({"jd_id": jd_id}, {"_id": 0})
    if not doc:
        return {"sent": False}
    return {
        "sent": True,
        "sent_at": doc.get("sent_at"),
        "client_email": doc.get("client_email"),
        "candidates_sent": len(doc.get("candidate_ids", [])),
    }


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


_INTERVIEW_STAGES = {"interview_1", "interview_final"}


class InterviewDetails(BaseModel):
    date: str
    time: str
    mode: str                        # "online" | "in-person"
    meeting_link: Optional[str] = None
    location: Optional[str] = None
    duration: str                    # "30min" | "45min" | "1hour"
    notes: Optional[str] = None


class AdvanceBody(BaseModel):
    next_stage: Optional[str] = None
    interview_details: Optional[InterviewDetails] = None


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

    # Use candidate's planned_stages if available, else fall back to global stage_order
    planned = doc.get("planned_stages") or order

    if body.next_stage:
        next_name = body.next_stage
    else:
        try:
            idx = planned.index(current)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Current stage '{current}' not in planned stages")
        if idx + 1 >= len(planned):
            raise HTTPException(status_code=400, detail="Already at final stage")
        next_name = planned[idx + 1]

    now = datetime.utcnow()
    stages = doc.get("stages", [])
    cur_idx = next((i for i, s in enumerate(stages) if s.get("name") == current), -1)
    if cur_idx < 0:
        raise HTTPException(status_code=500, detail="Inconsistent state: current stage missing from stages array")

    stages[cur_idx]["completed_at"] = now
    # SLA lookup: use specific key, else fall back by stage type
    if next_name in sla_map:
        sla_hours = int(sla_map[next_name])
    elif _is_assessment_stage(next_name):
        sla_hours = int(sla_map.get("assessment_1", 48))
    elif _is_interview_stage(next_name):
        sla_hours = int(sla_map.get("interview_1", 24))
    else:
        sla_hours = 72
    new_stage = _build_stage(next_name, sla_hours, now)
    if body.interview_details and _is_interview_stage(next_name):
        new_stage["interview_details"] = body.interview_details.model_dump()
    stages.append(new_stage)

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

    if body.interview_details and _is_interview_stage(next_name):
        try:
            from tasks.notification_tasks import send_interview_email
            send_interview_email.delay(jd_id, candidate_id, body.interview_details.model_dump())
        except Exception:
            pass  # email must never block stage advance

    try:
        from tasks.notification_tasks import send_stage_notification
        send_stage_notification.delay(candidate_id, jd_id, next_name)
    except Exception:
        pass  # notification must never block stage advance

    if next_name == "offer":
        offer_token = secrets.token_urlsafe(32)
        db.pipeline_stages.update_one(
            {"_id": doc["_id"]},
            {"$set": {"offer_token": offer_token, "offer_sent_at": now}},
        )
        try:
            from tasks.notification_tasks import send_offer_response_email
            send_offer_response_email.delay(jd_id, candidate_id, offer_token)
        except Exception:
            pass  # offer email must never block stage advance

    if next_name == "joined":
        try:
            generate_and_send_invoice.delay(jd_id, candidate_id)
        except Exception:
            pass  # invoice generation must never block pipeline advance
        try:
            start_retention_clock.delay(jd_id, candidate_id)
        except Exception:
            pass  # retention tracking must never block pipeline advance

    return {"ok": True, "current_stage": next_name}


def _is_interview_stage(stage_name: str) -> bool:
    return stage_name.startswith("interview_")


def _is_assessment_stage(stage_name: str) -> bool:
    return stage_name.startswith("assessment_")


def _generate_planned_stages(assessment_rounds: int, interview_rounds: int) -> list:
    stages = ["shortlist"]
    for i in range(1, assessment_rounds + 1):
        stages.append(f"assessment_{i}")
    for i in range(1, interview_rounds + 1):
        stages.append(f"interview_{i}")
    stages += ["offer", "joined"]
    return stages


def _next_interview_stage_name(stages: list) -> str:
    """Return interview_N+1 based on how many interview stages already exist."""
    count = sum(1 for s in stages if _is_interview_stage(s.get("name", "")))
    return f"interview_{count + 1}"


class InterviewOutcomeBody(BaseModel):
    outcome: str                                    # "selected" | "on_hold" | "rejected"
    next_step: Optional[str] = None                 # "next_round" | "offer"  (required when outcome=selected)
    interview_details: Optional[InterviewDetails] = None  # required when next_step=next_round
    reason: Optional[str] = None


@router.post("/interview-outcome/{jd_id}/{candidate_id}")
async def set_interview_outcome(
    jd_id: str,
    candidate_id: str,
    body: InterviewOutcomeBody,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    if body.outcome not in ("selected", "on_hold", "rejected"):
        raise HTTPException(status_code=400, detail="outcome must be selected, on_hold, or rejected")

    db = get_db()
    cfg = get_pipeline_config()
    sla_map = cfg["sla_hours"]

    doc = db.pipeline_stages.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found for this candidate")

    current = doc.get("current_stage")
    if not _is_interview_stage(current):
        raise HTTPException(status_code=400, detail=f"Outcome can only be set during interview stages, current is '{current}'")

    now = datetime.utcnow()

    if body.outcome == "rejected":
        db.pipeline_stages.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "current_stage": "rejected",
                "rejected_at": now,
                "rejection_reason": body.reason,
                "updated_at": now,
            }},
        )
        return {"ok": True, "outcome": "rejected"}

    if body.outcome == "on_hold":
        db.pipeline_stages.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "on_hold": True,
                "on_hold_reason": body.reason,
                "updated_at": now,
            }},
        )
        return {"ok": True, "outcome": "on_hold"}

    # outcome == "selected"
    if body.next_step not in ("next_round", "offer"):
        raise HTTPException(status_code=400, detail="next_step must be 'next_round' or 'offer' when outcome is selected")
    if body.next_step == "next_round" and not body.interview_details:
        raise HTTPException(status_code=400, detail="interview_details required when next_step is next_round")

    stages = doc.get("stages", [])
    cur_idx = next((i for i, s in enumerate(stages) if s.get("name") == current), -1)
    if cur_idx < 0:
        raise HTTPException(status_code=500, detail="Inconsistent state: current stage missing from stages array")

    stages[cur_idx]["completed_at"] = now
    stages[cur_idx]["outcome"] = "selected"

    if body.next_step == "next_round":
        next_name = _next_interview_stage_name(stages)
        sla = int(sla_map.get("interview_1", 24))  # reuse interview SLA for all rounds
        new_stage = _build_stage(next_name, sla, now)
        new_stage["interview_details"] = body.interview_details.model_dump()
        stages.append(new_stage)

        db.pipeline_stages.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "stages": stages,
                "current_stage": next_name,
                "on_hold": False,
                "updated_at": now,
            }},
        )

        try:
            from tasks.notification_tasks import send_interview_email
            send_interview_email.delay(jd_id, candidate_id, body.interview_details.model_dump())
        except Exception:
            pass

        return {"ok": True, "outcome": "selected", "current_stage": next_name}

    # next_step == "offer"
    next_name = "offer"
    new_stage = _build_stage(next_name, int(sla_map.get(next_name, 48)), now)
    stages.append(new_stage)

    offer_token = secrets.token_urlsafe(32)
    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "stages": stages,
            "current_stage": next_name,
            "on_hold": False,
            "offer_token": offer_token,
            "offer_sent_at": now,
            "updated_at": now,
        }},
    )

    if "offer" in _STAGE_TASK_MAP:
        t_type, tmpl, priority, due_h = _STAGE_TASK_MAP["offer"]
        desc = tmpl.format(cid=candidate_id, jid=jd_id)
        try:
            create_auto_task(db, t_type, desc, user.get("sub", "unknown"), jd_id, candidate_id, priority, due_h)
        except Exception:
            pass

    # Offer email is sent later — after recruiter fills in joining date via /give-offer
    return {"ok": True, "outcome": "selected", "current_stage": next_name}


class GiveOfferBody(BaseModel):
    joining_date: str
    work_location: str


OFFER_LETTERS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "offer_letters")


@router.post("/give-offer/{jd_id}/{candidate_id}")
async def give_offer(
    jd_id: str,
    candidate_id: str,
    joining_date: str = Form(...),
    work_location: str = Form(...),
    offer_letter: Optional[UploadFile] = File(None),
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    """Save joining date + location to offer stage, then advance to joined."""
    db = get_db()
    cfg = get_pipeline_config()
    sla_map = cfg["sla_hours"]

    doc = db.pipeline_stages.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found for this candidate")

    if doc.get("current_stage") != "offer":
        raise HTTPException(status_code=400, detail="Candidate is not in offer stage")

    now = datetime.utcnow()
    stages = doc.get("stages", [])
    offer_idx = next((i for i, s in enumerate(stages) if s.get("name") == "offer"), -1)
    if offer_idx < 0:
        raise HTTPException(status_code=500, detail="Offer stage entry missing")

    # Save offer letter PDF if uploaded
    offer_letter_path = None
    if offer_letter and offer_letter.filename:
        save_dir = os.path.join(OFFER_LETTERS_DIR, jd_id)
        os.makedirs(save_dir, exist_ok=True)
        offer_letter_path = os.path.join(save_dir, f"{candidate_id}_offer.pdf")
        with open(offer_letter_path, "wb") as f:
            shutil.copyfileobj(offer_letter.file, f)

    # Save offer details — stay on offer stage, wait for candidate response
    stages[offer_idx]["joining_date"] = joining_date
    stages[offer_idx]["work_location"] = work_location
    stages[offer_idx]["offer_sent_at"] = now
    if offer_letter_path:
        stages[offer_idx]["offer_letter_path"] = offer_letter_path

    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {
            "stages": stages,
            "offer_sent_at": now,
            "candidate_response": None,
            "updated_at": now,
        }},
    )

    # Send offer email to candidate with joining date
    try:
        from tasks.notification_tasks import send_offer_response_email
        send_offer_response_email.delay(jd_id, candidate_id, doc["offer_token"], joining_date, work_location)
    except Exception:
        pass

    return {"ok": True, "current_stage": "offer", "joining_date": joining_date, "work_location": work_location}


@router.post("/confirm-joining/{jd_id}/{candidate_id}")
async def confirm_joining(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    """Recruiter confirms candidate is joining — advances to joined and triggers invoice."""
    db = get_db()
    cfg = get_pipeline_config()
    sla_map = cfg["sla_hours"]

    doc = db.pipeline_stages.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if doc.get("current_stage") != "offer":
        raise HTTPException(status_code=400, detail="Candidate is not in offer stage")

    now = datetime.utcnow()
    stages = doc.get("stages", [])
    offer_idx = next((i for i, s in enumerate(stages) if s.get("name") == "offer"), -1)
    if offer_idx >= 0:
        stages[offer_idx]["completed_at"] = now

    joined_stage = _build_stage("joined", int(sla_map.get("joined", 720)), now)
    stages.append(joined_stage)

    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {"stages": stages, "current_stage": "joined", "updated_at": now}},
    )

    try:
        generate_and_send_invoice.delay(jd_id, candidate_id)
    except Exception:
        pass
    try:
        start_retention_clock.delay(jd_id, candidate_id)
    except Exception:
        pass
    try:
        from tasks.notification_tasks import send_stage_notification
        send_stage_notification.delay(candidate_id, jd_id, "joined")
    except Exception:
        pass

    return {"ok": True, "current_stage": "joined"}


@router.post("/reject-from-offer/{jd_id}/{candidate_id}")
async def reject_from_offer(
    jd_id: str,
    candidate_id: str,
    user: dict = Depends(check_role(["recruiter", "manager", "admin"])),
):
    """Recruiter rejects the candidate from the offer stage."""
    db = get_db()
    doc = db.pipeline_stages.find_one({"jd_id": jd_id, "candidate_id": candidate_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    now = datetime.utcnow()
    db.pipeline_stages.update_one(
        {"_id": doc["_id"]},
        {"$set": {"current_stage": "rejected", "rejected_at": now, "updated_at": now}},
    )
    return {"ok": True, "current_stage": "rejected"}


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


class OfferResponseBody(BaseModel):
    response: str  # "accept" | "hold" | "reject"
    reason: Optional[str] = None
    preferred_joining_date: Optional[str] = None


@router.get("/offer-response/{token}")
async def get_offer_details(token: str):
    """Public endpoint — no auth. Returns offer details for the candidate response page."""
    db = get_db()
    doc = db.pipeline_stages.find_one({"offer_token": token})
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid or expired offer link")

    jd_id = doc["jd_id"]
    candidate_id = doc["candidate_id"]

    jd = db.job_descriptions.find_one({"jd_id": jd_id})
    jd_title = (jd.get("structured_data", {}).get("title") or jd.get("title", "Job Role")) if jd else "Job Role"

    candidate = db.candidates.find_one({"candidate_id": candidate_id}, {"name": 1})
    candidate_name = candidate.get("name", "Candidate") if candidate else "Candidate"

    joining_date = None
    for stage in doc.get("stages", []):
        if stage.get("name") == "offer":
            joining_date = stage.get("joining_date")

    candidate_response = doc.get("candidate_response")

    return {
        "jd_id": jd_id,
        "jd_title": jd_title,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "joining_date": joining_date,
        "already_responded": candidate_response is not None,
        "candidate_response": candidate_response,
    }


@router.post("/offer-response/{token}")
async def submit_offer_response(token: str, body: OfferResponseBody):
    """Public endpoint — no auth. Candidate submits their offer response."""
    if body.response not in ("accept", "hold", "reject"):
        raise HTTPException(status_code=400, detail="response must be accept, hold, or reject")

    db = get_db()
    doc = db.pipeline_stages.find_one({"offer_token": token})
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid or expired offer link")

    if doc.get("candidate_response"):
        raise HTTPException(status_code=400, detail="You have already responded to this offer")

    now = datetime.utcnow()
    response_data = {
        "response": body.response,
        "reason": body.reason,
        "preferred_joining_date": body.preferred_joining_date,
        "responded_at": now,
    }

    db.pipeline_stages.update_one(
        {"offer_token": token},
        {"$set": {"candidate_response": response_data, "updated_at": now}},
    )

    try:
        from tasks.notification_tasks import notify_offer_response
        notify_offer_response.delay(doc["jd_id"], doc["candidate_id"], body.response, body.reason)
    except Exception:
        pass

    return {"ok": True, "response": body.response}


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
