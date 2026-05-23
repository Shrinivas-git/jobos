import os
import logging
import requests

logger = logging.getLogger(__name__)

UNIPILE_DSN = os.getenv("UNIPILE_DSN", "api43.unipile.com:17352")
UNIPILE_BASE = f"https://{UNIPILE_DSN}/api/v1"


# Keywords in headlines that indicate senior/leadership level — skip for junior/fresher roles
_SENIOR_SIGNALS = {"senior", "lead", "principal", "staff", "head", "director", "vp", "vice president", "manager", "architect", "chief", "cto", "ceo"}
_JUNIOR_SIGNALS = {"junior", "fresher", "trainee", "intern", "entry", "associate", "graduate", "entry-level"}


def _is_level_match(headline: str, level: str) -> bool:
    """Returns True if the profile headline matches the expected seniority level."""
    if not headline or not level:
        return True
    headline_lower = headline.lower()
    level_lower = level.lower()
    is_senior_role = any(s in level_lower for s in ["senior", "lead", "principal", "head", "manager", "director"])
    is_junior_role = any(s in level_lower for s in ["junior", "fresher", "trainee", "intern", "entry", "associate"])

    if is_junior_role:
        # Reject profiles with senior signals in headline
        return not any(s in headline_lower for s in _SENIOR_SIGNALS)
    if is_senior_role:
        # Reject profiles with junior/fresher signals in headline
        return not any(s in headline_lower for s in _JUNIOR_SIGNALS)
    return True


def fetch_linkedin_profiles(jd: dict, max_results: int = 20) -> list:
    """
    Searches LinkedIn via Unipile and returns a list of profile dicts filtered by
    location, skills (via keywords), and experience level (via headline filtering).
    Returns [] if credentials are missing or the request fails.
    """
    api_key = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        logger.warning("[Unipile] UNIPILE_API_KEY or UNIPILE_ACCOUNT_ID not set. Skipping.")
        return []

    structured = jd.get("structured_data", jd)
    title = structured.get("title", jd.get("title", ""))
    level = structured.get("level", jd.get("level", ""))
    skills = structured.get("must_have_skills", jd.get("skills", jd.get("skills_required", [])))[:3]
    location = structured.get("location", jd.get("location", ""))
    skills_str = " ".join(skills) if skills else ""

    # Avoid duplicate level prefix (e.g. "Senior" already in "Senior Engineer")
    title_clean = title if level.lower() in title.lower() else title
    parts = [p for p in [title_clean, skills_str, location] if p]
    keywords = " ".join(parts).strip() or "Software Engineer"

    # Fetch more than needed so we have room to filter by level
    fetch_limit = min(max_results * 4, 50)
    logger.info(f"[Unipile] Searching LinkedIn: '{keywords}' (fetch {fetch_limit}, want {max_results}, level={level}, location={location})")

    try:
        resp = requests.post(
            f"{UNIPILE_BASE}/linkedin/search",
            params={"account_id": account_id},
            json={
                "api": "classic",
                "category": "people",
                "keywords": keywords,
                "limit": fetch_limit,
            },
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        logger.info(f"[Unipile] Retrieved {len(items)} profiles before filtering")

        # Filter by experience level using headline
        filtered = [p for p in items if _is_level_match(p.get("headline", ""), level)]
        logger.info(f"[Unipile] {len(filtered)} profiles after level filter (level={level})")

        return filtered[:max_results]
    except Exception as e:
        logger.error(f"[Unipile] Error fetching profiles: {e}")
        return []


def send_linkedin_connection_request(provider_id: str, message: str = "") -> dict:
    """
    Sends a LinkedIn connection request via Unipile.
    Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    api_key = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        return {"ok": False, "error": "Unipile credentials not configured"}

    try:
        payload = {"account_id": account_id, "provider_id": provider_id}
        if message:
            payload["message"] = message
        resp = requests.post(
            f"{UNIPILE_BASE}/users/invite",
            json=payload,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return {"ok": True}
    except Exception as e:
        logger.error(f"[Unipile] Error sending connection request: {e}")
        return {"ok": False, "error": str(e)}


def get_linkedin_relation_type(provider_id: str) -> str | None:
    """
    Returns the relation_type string for a LinkedIn profile, e.g.
    "CONNECTED", "PENDING_SENT", "NOT_CONNECTED".
    Returns None on error.
    """
    api_key = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        return None

    try:
        resp = requests.get(
            f"{UNIPILE_BASE}/users/{provider_id}",
            params={"account_id": account_id},
            headers={"X-API-KEY": api_key},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # Unipile returns network_distance: FIRST_DEGREE=connected, SECOND_DEGREE=pending/not connected
        if data.get("is_relationship"):
            return "CONNECTED"
        return data.get("network_distance", "NOT_CONNECTED")
    except Exception as e:
        logger.error(f"[Unipile] Error fetching relation type for {provider_id}: {e}")
        return None


def send_linkedin_message(provider_id: str, message: str) -> dict:
    """
    Sends a LinkedIn DM to a profile via Unipile.
    provider_id: the Unipile provider_id of the recipient (stored on candidate doc).
    Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    api_key = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        return {"ok": False, "error": "Unipile credentials not configured"}

    try:
        resp = requests.post(
            f"{UNIPILE_BASE}/chats",
            json={
                "account_id": account_id,
                "attendees_ids": [provider_id],
                "text": message,
            },
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return {"ok": True, "chat_id": resp.json().get("id")}
    except Exception as e:
        logger.error(f"[Unipile] Error sending message: {e}")
        return {"ok": False, "error": str(e)}
