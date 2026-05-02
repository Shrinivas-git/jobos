from fastapi import APIRouter, Depends
from datetime import datetime
from collections import defaultdict

from auth import check_role
from utils.client_utils import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

STAGE_ORDER = ["shortlist", "interview", "offer", "joined"]


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


@router.get("/pipeline-health")
async def pipeline_health(user: dict = Depends(check_role(["manager", "admin", "hod"]))):
    db = get_db()
    now = datetime.utcnow()
    docs = list(db.pipeline_stages.find({}))

    stage_counts = defaultdict(int)
    breach_counts = defaultdict(int)
    reached_counts = defaultdict(int)

    for doc in docs:
        current = doc.get("current_stage", "")
        stage_counts[current] += 1
        for s in doc.get("stages", []):
            reached_counts[s["name"]] += 1
        for s in doc.get("stages", []):
            if s.get("name") == current and not s.get("completed_at"):
                ext = s.get("extension")
                effective_due = s.get("due_at")
                if ext and ext.get("approved") and ext.get("approved_until"):
                    effective_due = ext["approved_until"]
                if effective_due and effective_due < now:
                    breach_counts[current] += 1

    total = len(docs)
    funnel = []
    for stage in STAGE_ORDER:
        reached = reached_counts.get(stage, 0)
        funnel.append({
            "stage": stage,
            "current_count": stage_counts.get(stage, 0),
            "reached_count": reached,
            "breach_count": breach_counts.get(stage, 0),
            "conversion_pct": round(reached / total * 100, 1) if total > 0 else 0,
        })

    return {
        "total_active": total,
        "sla_breach_total": sum(breach_counts.values()),
        "funnel": funnel,
    }


@router.get("/recruiter-performance")
async def recruiter_performance(user: dict = Depends(check_role(["manager", "admin", "hod"]))):
    db = get_db()
    now = datetime.utcnow()
    tasks = list(db.recruiter_tasks.find({}))

    stats: dict = defaultdict(lambda: {
        "total": 0, "completed": 0, "overdue": 0,
        "total_days": 0.0, "completed_for_avg": 0,
    })

    for t in tasks:
        owner = t.get("owner_id", "unknown")
        s = stats[owner]
        s["total"] += 1
        completed_at = t.get("completed_at")
        due_at = t.get("due_at")
        created_at = t.get("created_at")
        if completed_at:
            s["completed"] += 1
            if created_at:
                s["total_days"] += (completed_at - created_at).total_seconds() / 86400
                s["completed_for_avg"] += 1
        elif due_at and due_at < now:
            s["overdue"] += 1

    owner_ids = list(stats.keys())
    users_docs = list(db.users.find({"keycloak_id": {"$in": owner_ids}}, {"keycloak_id": 1, "email": 1, "username": 1}))
    id_to_name = {u["keycloak_id"]: u.get("email") or u.get("username") or u["keycloak_id"] for u in users_docs}

    result = []
    for owner_id, s in stats.items():
        avg_days = round(s["total_days"] / s["completed_for_avg"], 1) if s["completed_for_avg"] > 0 else None
        result.append({
            "recruiter_id": owner_id,
            "recruiter_name": id_to_name.get(owner_id, f"...{owner_id[-8:]}"),
            "total_tasks": s["total"],
            "completed_tasks": s["completed"],
            "overdue_tasks": s["overdue"],
            "avg_days_to_complete": avg_days,
            "completion_rate": round(s["completed"] / s["total"] * 100, 1) if s["total"] > 0 else 0,
        })

    result.sort(key=lambda x: x["completion_rate"], reverse=True)
    return result


@router.get("/time-to-fill")
async def time_to_fill(user: dict = Depends(check_role(["manager", "admin", "hod"]))):
    db = get_db()
    jds = list(db.job_descriptions.find({}, {"jd_id": 1, "title": 1, "created_at": 1, "status": 1, "_id": 0}))

    pipeline_docs = list(db.pipeline_stages.find({}, {"jd_id": 1, "stages": 1, "_id": 0}))
    first_joined: dict = {}
    for doc in pipeline_docs:
        jd_id = doc.get("jd_id")
        for s in doc.get("stages", []):
            if s.get("name") == "joined":
                entered = s.get("entered_at")
                if entered and (jd_id not in first_joined or entered < first_joined[jd_id]):
                    first_joined[jd_id] = entered

    rows = []
    days_list = []
    for jd in jds:
        jd_id = jd.get("jd_id")
        created_at = jd.get("created_at")
        joined_at = first_joined.get(jd_id)
        days = None
        if created_at and joined_at:
            days = round((joined_at - created_at).total_seconds() / 86400, 1)
            days_list.append(days)
        rows.append({
            "jd_id": jd_id,
            "title": jd.get("title", "Untitled"),
            "status": jd.get("status", ""),
            "created_at": _iso(created_at),
            "filled_at": _iso(joined_at),
            "days_to_fill": days,
        })

    rows.sort(key=lambda x: (x["days_to_fill"] is None, -(x["days_to_fill"] or 0)))

    summary = {
        "total_jds": len(rows),
        "filled_count": len(days_list),
        "open_count": sum(1 for r in rows if r["days_to_fill"] is None),
        "avg_days": round(sum(days_list) / len(days_list), 1) if days_list else None,
        "min_days": min(days_list) if days_list else None,
        "max_days": max(days_list) if days_list else None,
    }
    return {"summary": summary, "jds": rows}
