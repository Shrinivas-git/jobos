import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
SESSIONS_DIR = Path("/app/sessions")


def _get_session(portal_key: str) -> Optional[str]:
    session_path = SESSIONS_DIR / f"{portal_key}.json"
    if session_path.exists():
        return str(session_path)
    return None


def _build_apply_url(jd_id: str, portal: str) -> str:
    base = os.getenv("APP_BASE_URL", "http://localhost:5173")
    return f"{base}/apply/{jd_id}?source={portal}"


def _fill_job_form(page, title: str, description: str, location: str, salary: str,
                   skills: str, experience: str, apply_url: str, selectors: dict):
    from playwright.sync_api import TimeoutError as PWTimeout
    if selectors.get("title"):
        page.fill(selectors["title"], title)
    if selectors.get("description"):
        page.fill(selectors["description"], description)
    if selectors.get("location"):
        page.fill(selectors["location"], location)
    if selectors.get("salary") and salary:
        page.fill(selectors["salary"], salary)
    if selectors.get("skills") and skills:
        page.fill(selectors["skills"], skills)
    if selectors.get("experience") and experience:
        page.fill(selectors["experience"], experience)
    if selectors.get("apply_url"):
        page.fill(selectors["apply_url"], apply_url)


INTERNSHALA_CITY = os.getenv("INTERNSHALA_JOB_CITY", "Bengaluru")
# POC phone shown on the listing; overridable via env
INTERNSHALA_POC_PHONE = os.getenv("INTERNSHALA_POC_PHONE", "9902094422")


def _internshala_resolve_location(s, city: str):
    """Resolve a city name to Internshala's (location_id, canonical_name).
    Returns (None, None) if it can't be resolved."""
    try:
        r = s.post(
            f"https://internshala.com/autocomplete/location/{city}",
            data={"location": city, "source": "posting_form"},
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=20,
        )
        results = r.json().get("result", [])
        if not results:
            return None, None
        top = results[0]
        # Existing locations carry a numeric `id`; brand-new ones carry a Google
        # `place_id` that must be converted via /location/get_or_create.
        if top.get("id"):
            return str(top["id"]), top.get("name", city)
        place_id = top.get("place_id")
        if place_id:
            gr = s.post(
                "https://internshala.com/location/get_or_create",
                data={"input_name": "location", "place_id": place_id, "source": "posting_location"},
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=20,
            ).json()
            if gr.get("success") and gr.get("location_id"):
                return str(gr["location_id"]), top.get("name", city)
    except Exception as e:
        logger.warning(f"[HTTP] Internshala location resolve failed for {city!r}: {e}")
    return None, None


def post_to_internshala(jd: dict) -> tuple[bool, Optional[str]]:
    """Post a JD as a JOB (not internship) on Internshala.

    The form page (/job/form) hosts two forms; the real submit is a multipart
    AJAX POST to /job/submit. Field names below are the actual `name` attributes
    of the post_job form (verified against the live form), NOT element ids.
    """
    import requests, json as _json
    import re

    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    description = structured.get("responsibilities", title)
    salary = structured.get("compensation_range", "")
    skills_list = structured.get("skills", []) or []

    session_path = _get_session("internshala")
    if not session_path:
        return False, "No saved session — run setup_portal_sessions.py --portal internshala"

    with open(session_path) as f:
        session_data = _json.load(f)
    cookies = {c["name"]: c["value"] for c in session_data.get("cookies", [])}

    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": "https://internshala.com/job/form",
        "Origin": "https://internshala.com",
    })

    # GET form page for csrf + the per-load unique_key (single-use idempotency key)
    html = s.get("https://internshala.com/job/form", timeout=30).text

    csrf = None
    for tag in re.finditer(r'<input[^>]*name="csrf_test_name"[^>]*>', html):
        vm = re.search(r'value="([^"]*)"', tag.group(0))
        if vm and vm.group(1):
            csrf = vm.group(1)
            break
    if not csrf:
        return False, "Could not extract CSRF token from Internshala form"

    ukm = re.search(r'<input[^>]*name="unique_key"[^>]*>', html)
    unique_key = (re.search(r'value="([^"]*)"', ukm.group(0)).group(1) if ukm else "")

    # Resolve the work-location to Internshala's numeric id (required by the server)
    loc_id, loc_name = _internshala_resolve_location(s, INTERNSHALA_CITY)
    if not loc_id:
        return False, f"Could not resolve Internshala location id for {INTERNSHALA_CITY!r}"

    # Parse salary into an annual min/max range
    sal_min = sal_max = ""
    if salary:
        try:
            parts = salary.replace("₹", "").replace(",", "").replace("LPA", "").strip().split("-")
            s_min = int(''.join(filter(str.isdigit, parts[0].strip())))
            s_max = int(''.join(filter(str.isdigit, parts[1].strip()))) if len(parts) > 1 else s_min + 2
            if s_min < 1000:
                s_min *= 100000
                s_max *= 100000
            sal_min, sal_max = str(s_min), str(s_max)
        except Exception:
            pass
    sal_min = sal_min or "300000"
    sal_max = sal_max or "600000"

    # Description must be >= 100 chars (server-side validation)
    skills_str = ", ".join(skills_list) if skills_list else title
    desc_text = description if description else title
    if len(desc_text) < 100:
        desc_text += (f"\n\nRole: {title}. Key skills: {skills_str}. "
                      f"Location: {loc_name}. We are looking for a motivated candidate to "
                      f"join our team and contribute to impactful projects. Apply now.")
    desc_text = desc_text[:5000]

    # Multipart form fields (use a list so skills[]/location[] can repeat).
    fields = [
        ("csrf_test_name", csrf),
        ("unique_key", unique_key),
        ("status", "pending review"),          # set by JS when "Post job" is clicked
        ("source", ""),
        ("submit_value", "submit"),            # = clicked button id
        ("job_id", ""),
        ("cloned_job_id", ""),
        ("experienced_hiring", "yes"),
        ("form_loader", "on"),
        ("job_title", title),
        ("custom_job_title", ""),
        ("min_experience", "0"),
        ("max_experience", "5"),               # JS hardcodes 5 for new jobs
        ("job_type", "regular"),
        ("job_part_full", "full"),
        ("location", loc_name),
        ("job_office_location", loc_name),
        ("job_office_location_id", loc_id),
        ("Place_id", ""),
        ("is_applications_from_above_cities_allowed", "yes"),
        ("to_bypass_office_location_check", "yes"),
        ("to_show_designation", "false"),
        ("job_open_positions", "1"),
        ("description", desc_text),
        ("who_can_apply_text", ""),
        ("candidate_preference", ""),
        ("job_salary_currency", "rs"),
        ("job_salary", sal_min),
        ("job_salary2", sal_max),
        ("evaluate_comm_skills", "no"),
        ("question2_type", "availability"),
        ("question2_question_type", "text"),
        ("question2", "Please confirm your availability for this job."),
        ("show_cover_letter_job", "0"),
        ("job_poc_country_code", "+91"),
        ("job_poc_contact_no", INTERNSHALA_POC_PHONE),
        ("location[]", loc_id),
    ]
    for sk in (skills_list or [title]):
        fields.append(("skills[]", str(sk)[:50]))

    # processData:false / contentType:false in the JS => multipart/form-data
    files = [(k, (None, str(v))) for k, v in fields]

    try:
        resp = s.post("https://internshala.com/job/submit", files=files, timeout=40)
        try:
            j = resp.json()
        except ValueError:
            return False, f"Internshala non-JSON response ({resp.status_code}): {resp.text[:150]}"

        if j.get("success"):
            logger.info(f"[HTTP] Posted JOB to Internshala (under review): {title}")
            return True, None

        et = j.get("errorThrown", {})
        if isinstance(et, dict):
            err = et.get("validationError") or et.get("errorMsg") or _json.dumps(et)[:200]
        else:
            err = str(et)[:200]
        logger.warning(f"[HTTP] Internshala rejected job: {err}")
        return False, f"Internshala rejected: {err}"
    except Exception as e:
        return False, str(e)


def post_to_shine(jd: dict) -> tuple[bool, Optional[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed"

    jd_id = jd.get("jd_id", "")
    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    description = structured.get("responsibilities", title)
    location = structured.get("location", "Bengaluru")
    salary = structured.get("compensation_range", "")
    skills = ", ".join(structured.get("skills", [])[:8])
    exp_min = str(structured.get("relevant_experience", "0"))
    exp_max = str(structured.get("total_experience", "5"))
    apply_url = _build_apply_url(jd_id, "shine")

    email = os.getenv("SHINE_EMAIL", "")
    password = os.getenv("SHINE_PASSWORD", "")
    session = _get_session("shine")
    if not session and (not email or not password):
        return False, "No saved session and SHINE_EMAIL or SHINE_PASSWORD not set in .env"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            if session:
                context = browser.new_context(storage_state=session)
                page = context.new_page()
                logger.info("[Playwright] Shine: using saved session")
            else:
                page = browser.new_page()
                page.goto("https://www.shine.com/employers/login/", timeout=30000)
                page.fill("input[name='email']", email)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle", timeout=15000)

            page.goto("https://www.shine.com/employers/post-job/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            page.fill("input[name='job_title']", title)
            page.fill("textarea[name='job_description']", description[:3000])
            page.fill("input[name='location']", location)
            if salary:
                page.fill("input[name='salary']", salary)
            page.fill("input[name='key_skills']", skills)
            page.fill("input[name='min_exp']", exp_min)
            page.fill("input[name='max_exp']", exp_max)

            try:
                page.fill("input[name='apply_url']", apply_url)
            except Exception:
                pass

            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=15000)

            browser.close()
            logger.info(f"[Playwright] Posted to Shine: {title}")
            return True, None

    except Exception as e:
        return False, str(e)


def post_to_workindia(jd: dict) -> tuple[bool, Optional[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed"

    jd_id = jd.get("jd_id", "")
    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    description = structured.get("responsibilities", title)
    location = structured.get("location", "Bengaluru")
    salary = structured.get("compensation_range", "")
    apply_url = _build_apply_url(jd_id, "workindia")

    email = os.getenv("WORKINDIA_EMAIL", "")
    password = os.getenv("WORKINDIA_PASSWORD", "")
    session = _get_session("workindia")
    if not session and (not email or not password):
        return False, "No saved session and WORKINDIA_EMAIL or WORKINDIA_PASSWORD not set in .env"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            if session:
                context = browser.new_context(storage_state=session)
                page = context.new_page()
                logger.info("[Playwright] WorkIndia: using saved session")
            else:
                page = browser.new_page()
                page.goto("https://employer.workindia.in/login", timeout=30000)
                page.fill("input[type='email']", email)
                page.fill("input[type='password']", password)
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle", timeout=15000)

            page.goto("https://employer.workindia.in/post-job", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            page.fill("input[placeholder*='title'], input[name*='title']", title)
            page.fill("textarea[placeholder*='description'], textarea[name*='description']", description[:2000])
            page.fill("input[placeholder*='location'], input[name*='location']", location)
            if salary:
                page.fill("input[placeholder*='salary'], input[name*='salary']", salary)

            try:
                page.fill("input[placeholder*='apply'], input[name*='apply_url']", apply_url)
            except Exception:
                pass

            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=15000)

            browser.close()
            logger.info(f"[Playwright] Posted to WorkIndia: {title}")
            return True, None

    except Exception as e:
        return False, str(e)


def post_to_glassdoor(jd: dict) -> tuple[bool, Optional[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed"

    jd_id = jd.get("jd_id", "")
    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    description = structured.get("responsibilities", title)
    location = structured.get("location", "Bengaluru, India")
    apply_url = _build_apply_url(jd_id, "glassdoor")

    email = os.getenv("GLASSDOOR_EMAIL", "")
    password = os.getenv("GLASSDOOR_PASSWORD", "")
    session = _get_session("glassdoor")
    if not session and (not email or not password):
        return False, "No saved session and GLASSDOOR_EMAIL or GLASSDOOR_PASSWORD not set in .env"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            if session:
                context = browser.new_context(storage_state=session)
                page = context.new_page()
                logger.info("[Playwright] Glassdoor: using saved session")
            else:
                page = browser.new_page()
                page.goto("https://www.glassdoor.co.in/employers/sign-in", timeout=30000)
                page.fill("input[name='username']", email)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle", timeout=15000)

            page.goto("https://www.glassdoor.co.in/employers/post-a-job", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            page.fill("input[placeholder*='title'], input[name*='title']", title)
            page.fill("input[placeholder*='location'], input[name*='location']", location)

            try:
                page.fill("textarea[name='description']", description[:3000])
            except Exception:
                pass

            try:
                page.fill("input[placeholder*='apply'], input[name*='apply']", apply_url)
            except Exception:
                pass

            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=15000)

            browser.close()
            logger.info(f"[Playwright] Posted to Glassdoor: {title}")
            return True, None

    except Exception as e:
        return False, str(e)


def post_to_placementindia(jd: dict) -> tuple[bool, Optional[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "playwright not installed"

    jd_id = jd.get("jd_id", "")
    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    description = structured.get("responsibilities", title)
    location = structured.get("location", "Bengaluru")
    salary = structured.get("compensation_range", "")
    exp_min = str(structured.get("relevant_experience", "0"))
    exp_max = str(structured.get("total_experience", "5"))
    apply_url = _build_apply_url(jd_id, "placementindia")

    email = os.getenv("PLACEMENTINDIA_EMAIL", "")
    password = os.getenv("PLACEMENTINDIA_PASSWORD", "")
    session = _get_session("placementindia")
    if not session and (not email or not password):
        return False, "No saved session and PLACEMENTINDIA_EMAIL or PLACEMENTINDIA_PASSWORD not set in .env"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            if session:
                context = browser.new_context(storage_state=session)
                page = context.new_page()
                logger.info("[Playwright] PlacementIndia: using saved session")
            else:
                page = browser.new_page()
                page.goto("https://www.placementindia.com/recruiter/login.asp", timeout=30000)
                page.fill("input[name='email']", email)
                page.fill("input[name='password']", password)
                page.click("input[type='submit'], button[type='submit']")
                page.wait_for_load_state("networkidle", timeout=15000)

            page.goto("https://www.placementindia.com/recruiter/post-job.asp", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            page.fill("input[name='job_title']", title)
            page.fill("textarea[name='job_description']", description[:2000])
            page.fill("input[name='location']", location)
            if salary:
                page.fill("input[name='salary']", salary)
            page.fill("input[name='min_exp']", exp_min)
            page.fill("input[name='max_exp']", exp_max)

            try:
                page.fill("input[name='apply_url'], input[placeholder*='apply']", apply_url)
            except Exception:
                pass

            page.click("input[type='submit'], button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=15000)

            browser.close()
            logger.info(f"[Playwright] Posted to PlacementIndia: {title}")
            return True, None

    except Exception as e:
        return False, str(e)


PORTAL_FUNCTIONS = {
    "internshala": post_to_internshala,
    "shine": post_to_shine,
    "workindia": post_to_workindia,
    "glassdoor": post_to_glassdoor,
    "placementindia": post_to_placementindia,
}


def post_to_all_portals(jd: dict) -> dict:
    """
    Tries to post jd to all 5 portals.
    Returns dict of {portal: {"success": bool, "error": str|None}}
    """
    results = {}
    for portal, fn in PORTAL_FUNCTIONS.items():
        logger.info(f"[Playwright] Posting to {portal}...")
        success, error = fn(jd)
        results[portal] = {"success": success, "error": error}
        if not success:
            logger.warning(f"[Playwright] {portal} failed: {error}")
    return results
