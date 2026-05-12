"""
sources/unipile.py
Searches LinkedIn profiles via Unipile API using a connected recruiter session.
Returns list of raw profile dicts.
"""
import os
import requests


UNIPILE_DSN  = os.getenv("UNIPILE_DSN", "api43.unipile.com:17352")
UNIPILE_BASE = f"https://{UNIPILE_DSN}/api/v1"


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key    = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        print("  [Unipile] UNIPILE_API_KEY or UNIPILE_ACCOUNT_ID not set. Skipping.")
        return []

    headers = {
        "X-API-KEY":    api_key,
        "Content-Type": "application/json"
    }

    # Build search keywords
    title    = jd.get("title", "")
    skills   = " ".join(jd.get("skills_required", [])[:4])
    location = jd.get("location", "")
    keywords = f"{title} {skills}".strip()

    payload = {
        "account_id": account_id,
        "keywords":   keywords,
        "location":   location,
        "limit":      min(max_results, 50),   # Unipile max per call
    }

    print(f"  [Unipile] Searching LinkedIn: '{keywords}' in '{location}'")

    try:
        resp = requests.post(
            f"{UNIPILE_BASE}/linkedin/search/people",
            json=payload,
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("items", data.get("results", []))
        print(f"  [Unipile] Retrieved {len(results)} profiles")
        return results
    except Exception as e:
        print(f"  [Unipile] Error: {e}")
        return []
