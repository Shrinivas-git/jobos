"""HTTP-only helpers for reading employer data from Internshala using a saved session.

Internshala has no public API; these replicate the AJAX calls the employer
dashboard SPA makes (verified against the live site):
  - POST /employer/paginated_jobs            -> posted jobs (HTML rows)
  - POST /api/employer/ats/init/{id}/open    -> ATS session init (required first)
  - POST /api/employer/ats/paginated_applications/{id} -> applicant records (JSON)
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("/app/sessions")
_BASE = "https://internshala.com"


def _load_session() -> Optional[requests.Session]:
    session_path = SESSIONS_DIR / "internshala.json"
    if not session_path.exists():
        logger.warning("[Internshala] No saved session at %s", session_path)
        return None
    with open(session_path) as f:
        data = json.load(f)
    cookies = {c["name"]: c["value"] for c in data.get("cookies", [])}
    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{_BASE}/employer/dashboard",
    })
    return s


def fetch_posted_jobs(s: requests.Session) -> list[dict]:
    """Returns [{job_id, title, applicant_count}] across all dashboard pages."""
    jobs: list[dict] = []
    page = 1
    while True:
        try:
            r = s.post(
                f"{_BASE}/employer/paginated_jobs",
                data=f"page_number={page}&employment_type=job&reload_if_no_job_found=false",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            j = r.json()
        except Exception as e:
            logger.error("[Internshala] paginated_jobs page %s failed: %s", page, e)
            break

        html = j.get("view", "") or ""
        for row in re.finditer(r'<tr class="job"[^>]*\bid="(\d+)"', html):
            job_id = row.group(1)
            # title and applicant count appear after the row's opening tag
            segment = html[row.start():row.start() + 3000]
            title_m = re.search(r'<div class="text">([^<]+)</div>', segment)
            count_m = re.search(r'View applications \((\d+)\)', segment)
            jobs.append({
                "job_id": job_id,
                "title": (title_m.group(1).strip() if title_m else ""),
                "applicant_count": int(count_m.group(1)) if count_m else 0,
            })

        total_pages = j.get("total_pages", 1) or 1
        if page >= total_pages:
            break
        page += 1

    return jobs


def fetch_applicants(s: requests.Session, job_id: str) -> list[dict]:
    """Returns the raw applicant records for an Internshala job id."""
    try:
        s.post(
            f"{_BASE}/api/employer/ats/init/{job_id}/open",
            files={"is_node_request": (None, "1")},
            timeout=30,
        )
        r = s.post(
            f"{_BASE}/api/employer/ats/paginated_applications/{job_id}",
            files={"status": (None, "open"), "is_node_request": (None, "1")},
            timeout=30,
        )
        return r.json().get("applications_results", {}).get("records", []) or []
    except Exception as e:
        logger.error("[Internshala] fetch applicants for job %s failed: %s", job_id, e)
        return []
