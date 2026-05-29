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
    """Post a JD as a JOB on Internshala using Playwright browser automation."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return False, "playwright not installed"

    session_path = _get_session("internshala")
    if not session_path:
        return False, "No saved session — run setup_portal_sessions.py --portal internshala"

    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    responsibilities = structured.get("responsibilities", "")
    if isinstance(responsibilities, list):
        description = "\n".join(str(r) for r in responsibilities)
    else:
        description = str(responsibilities) if responsibilities else title
    if len(description) < 100:
        description += f"\n\nWe are looking for a {title} to join our team. Apply now."
    description = description[:4000]

    skills_list = structured.get("required_skills", structured.get("skills", [])) or []
    skills_str = ", ".join(str(s) for s in skills_list[:8]) if skills_list else title

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context(storage_state=session_path)
            page = context.new_page()

            page.goto("https://internshala.com/job/form", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Fill job title
            try:
                page.fill("input[name='job_title']", title, timeout=5000)
            except PWTimeout:
                page.fill("#job_title", title, timeout=5000)

            # Fill description
            try:
                page.fill("textarea[name='description']", description, timeout=5000)
            except PWTimeout:
                try:
                    page.fill("#description", description, timeout=5000)
                except Exception:
                    pass

            # Fill skills
            try:
                page.fill("input[name='skills[]']", skills_str, timeout=3000)
            except Exception:
                pass

            # Location — try Bengaluru
            try:
                loc_input = page.locator("input[name='location']").first
                loc_input.fill(INTERNSHALA_CITY, timeout=3000)
                page.wait_for_timeout(1000)
                page.keyboard.press("Enter")
            except Exception:
                pass

            # Submit
            try:
                page.click("button[type='submit']", timeout=5000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            browser.close()
            logger.info(f"[Playwright] Posted to Internshala: {title}")
            return True, None

    except Exception as e:
        logger.error(f"[Playwright] Internshala error: {e}")
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
