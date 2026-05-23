import os
import base64
import logging
import uuid
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

from celery import chain

from utils.client_utils import get_db
from utils.storage_utils import save_resume_file
from utils.resume_utils import extract_text_from_file
from tasks.resume_tasks import process_resume_task
from tasks.matching_tasks import run_matching

logger = logging.getLogger(__name__)

router = APIRouter(tags=["indeed"])

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Refining Skills")
INDEED_APPLY_TOKEN = os.getenv("INDEED_APPLY_TOKEN", "")


@router.get("/feed/indeed.xml", response_class=Response)
async def serve_indeed_feed():
    """
    Serves all active JDs as an Indeed-compatible XML feed.
    Register this URL once in Indeed employer dashboard under ATS Integrations.
    Indeed polls this automatically — no manual action needed after registration.
    """
    db = get_db()
    jds = list(db.job_descriptions.find(
        {"status": {"$nin": ["closed", "cancelled"]}},
        {"_id": 0}
    ).sort("created_at", -1))

    source = Element("source")

    publisher = SubElement(source, "publisher")
    publisher.text = COMPANY_NAME

    publisher_url = SubElement(source, "publisherurl")
    publisher_url.text = APP_BASE_URL

    last_build = SubElement(source, "lastBuildDate")
    last_build.text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    for jd in jds:
        jd_id = jd.get("jd_id", "")
        title = jd.get("title", "Untitled")
        structured = jd.get("structured_data") or {}

        description = structured.get("responsibilities", "") or jd.get("recruiter_notes", "") or title
        location = structured.get("location", "Bengaluru, Karnataka")
        salary = structured.get("compensation_range", "")
        experience_min = structured.get("relevant_experience", 0)
        experience_max = structured.get("total_experience", 0)
        work_structure = structured.get("work_structure", "onsite").lower()

        apply_url = f"{APP_BASE_URL}/apply/{jd_id}"
        post_url = f"{API_BASE_URL}/webhook/indeed"

        job_el = SubElement(source, "job")

        def add(tag, text):
            el = SubElement(job_el, tag)
            el.text = str(text) if text else ""

        add("title", title)
        add("date", jd.get("created_at", datetime.now()).strftime("%Y-%m-%d") if hasattr(jd.get("created_at"), "strftime") else str(jd.get("created_at", ""))[:10])
        add("referencenumber", jd_id)
        add("url", apply_url)
        add("company", COMPANY_NAME)

        # Parse city/state from location string (e.g. "Bengaluru, Karnataka")
        loc_parts = [p.strip() for p in location.split(",")]
        add("city", loc_parts[0] if loc_parts else "Bengaluru")
        add("state", loc_parts[1] if len(loc_parts) > 1 else "Karnataka")
        add("country", "IN")

        add("description", description)
        add("salary", salary)
        add("jobtype", "fulltime")

        exp_text = f"{experience_min}-{experience_max} years" if experience_min or experience_max else ""
        add("experience", exp_text)

        remote_el = SubElement(job_el, "remotetype")
        remote_el.text = "Remote" if "remote" in work_structure else ("Hybrid" if "hybrid" in work_structure else "")

        # Indeed Apply fields — enable "Easy Apply" on Indeed
        add("indeed-apply-jobTitle", title)
        add("indeed-apply-jobId", jd_id)
        add("indeed-apply-jobUrl", apply_url)
        add("indeed-apply-apiToken", INDEED_APPLY_TOKEN)
        add("indeed-apply-postUrl", post_url)
        add("indeed-apply-phone", "false")
        add("indeed-apply-questions", "")

    xml_str = parseString(tostring(source, encoding="unicode")).toprettyxml(indent="  ")
    # Remove the extra XML declaration added by toprettyxml since we add our own
    xml_lines = xml_str.split("\n")
    if xml_lines[0].startswith("<?xml"):
        xml_lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_output = "\n".join(xml_lines)

    return Response(content=xml_output, media_type="application/xml")


@router.post("/webhook/indeed")
async def indeed_webhook(request: Request):
    """
    Receives candidate application from Indeed Easy Apply.
    Indeed POSTs JSON with applicant info + Base64-encoded resume.
    We decode, save, create candidate record, trigger matching.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(f"[Indeed Webhook] Received application: {payload.get('job', {})}")

    applicant = payload.get("applicant", {})
    job_info = payload.get("job", {})

    name = applicant.get("fullName", "").strip()
    email = (applicant.get("email") or "").strip().lower()
    phone = (applicant.get("phoneNumber") or "").strip()
    jd_id = job_info.get("jobId") or job_info.get("indeedJobId", "")

    if not name or not email:
        raise HTTPException(status_code=400, detail="Missing applicant name or email")

    db = get_db()

    # De-duplicate by email + jd_id
    existing = db.candidates.find_one({"email": email, "jd_id": jd_id})
    if existing:
        logger.info(f"[Indeed Webhook] Duplicate application from {email} for {jd_id} — skipped")
        return {"status": "duplicate", "message": "Application already received"}

    # Decode and save resume
    resume_path = None
    resume_text = ""
    resume_info = applicant.get("resume", {})
    file_info = resume_info.get("file", {})
    b64_data = file_info.get("data", "")
    file_name = file_info.get("fileName", "resume.pdf")

    if b64_data:
        try:
            resume_bytes = base64.b64decode(b64_data)
            candidate_id = f"CAN-IN-{uuid.uuid4().hex[:8]}"
            resume_path = save_resume_file(candidate_id, file_name, resume_bytes)
            resume_text = extract_text_from_file(resume_path) if resume_path else ""
        except Exception as e:
            logger.error(f"[Indeed Webhook] Failed to decode/save resume: {e}")
            candidate_id = f"CAN-IN-{uuid.uuid4().hex[:8]}"
    else:
        candidate_id = f"CAN-IN-{uuid.uuid4().hex[:8]}"

    candidate_doc = {
        "candidate_id": candidate_id,
        "name": name,
        "email": email,
        "phone": phone,
        "jd_id": jd_id,
        "source": "indeed",
        "status": "received",
        "resume_text": resume_text,
        "resume_path": resume_path,
        "skills": [],
        "experience_years": 0,
        "location": applicant.get("location", ""),
        "headline": "",
        "file_paths": [resume_path] if resume_path else [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "raw_payload": payload,
    }

    db.candidates.insert_one(candidate_doc)
    logger.info(f"[Indeed Webhook] Created candidate {candidate_id} — {name} for JD {jd_id}")

    # Parse the resume (skills, experience, embedding), then match against the JD.
    # Chained so matching runs only after the candidate is in the vector DB.
    if resume_path and jd_id:
        chain(
            process_resume_task.si(candidate_id, resume_path, "indeed"),
            run_matching.si(jd_id),
        ).delay()
    elif resume_path:
        process_resume_task.delay(candidate_id, resume_path, source="indeed")
    elif jd_id:
        run_matching.delay(jd_id)

    return {"status": "received", "candidate_id": candidate_id}
