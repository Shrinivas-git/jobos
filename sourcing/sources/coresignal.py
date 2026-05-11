"""
sources/coresignal.py
Searches Coresignal Employee API for professional profiles.
Returns list of raw profile dicts.
"""
import os
import requests


CORESIGNAL_BASE = "https://api.coresignal.com/cdapi/v1"


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key = os.getenv("CORESIGNAL_API_KEY")
    if not api_key:
        print("  [Coresignal] CORESIGNAL_API_KEY not set. Skipping.")
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json"
    }

    skills   = jd.get("skills_required", [])
    title    = jd.get("title", "")
    exp_min  = jd.get("experience_years", {}).get("min", 0)
    exp_max  = jd.get("experience_years", {}).get("max", 20)

    payload = {
        "title":                  title,
        "skills":                 skills[:5],
        "location":               "India",
        "experience_count_min":   max(exp_min - 1, 0),
        "experience_count_max":   exp_max + 1,
        "limit":                  min(max_results, 100),
    }

    print(f"  [Coresignal] Searching: '{title}' skills={skills[:3]}")

    try:
        resp = requests.post(
            f"{CORESIGNAL_BASE}/linkedin/member/search/filter",
            json=payload,
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        results = resp.json()
        # Coresignal returns list or dict with items
        if isinstance(results, list):
            items = results
        else:
            items = results.get("data", results.get("items", []))
        print(f"  [Coresignal] Retrieved {len(items)} profiles")
        return items[:max_results]
    except Exception as e:
        print(f"  [Coresignal] Error: {e}")
        return []
