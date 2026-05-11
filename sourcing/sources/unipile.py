"""
sources/unipile.py
==================
LinkedIn candidate search via Unipile API (LinkedIn automation layer).
Docs: https://developer.unipile.com/reference/

Requires:
  UNIPILE_API_KEY       — your Unipile API key
  UNIPILE_ACCOUNT_ID    — the linked LinkedIn account ID in Unipile
"""
import os
import requests

UNIPILE_BASE = "https://api1.unipile.com:13301/api/v1"


def _build_keywords(jd: dict) -> str:
    parts = [jd.get("title", "")]
    skills = jd.get("skills_required", [])[:3]
    parts.extend(skills)
    return " ".join(p for p in parts if p)


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key    = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        print("  [Unipile] UNIPILE_API_KEY or UNIPILE_ACCOUNT_ID not set. Skipping.")
        return []

    keywords = _build_keywords(jd)
    location = jd.get("location", "India")

    print(f"  [Unipile] Searching LinkedIn: '{keywords}' in '{location}'")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    # LinkedIn people search via Unipile
    search_payload = {
        "account_id": account_id,
        "keywords":   keywords,
        "geo_codes":  [location],
        "limit":      min(max_results, 50),
    }

    results = []

    try:
        resp = requests.post(
            f"{UNIPILE_BASE}/linkedin/search/people",
            json=search_payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data  = resp.json()
        items = data.get("items", data.get("results", []))

        # Optionally enrich each profile
        for item in items[:max_results]:
            profile_id = item.get("id") or item.get("profile_id")
            if profile_id:
                try:
                    profile_resp = requests.get(
                        f"{UNIPILE_BASE}/linkedin/profiles/{profile_id}",
                        headers=headers,
                        params={"account_id": account_id},
                        timeout=20,
                    )
                    if profile_resp.ok:
                        results.append(profile_resp.json())
                        continue
                except Exception:
                    pass
            results.append(item)

        print(f"  [Unipile] Retrieved {len(results)} LinkedIn profiles")
        return results
    except requests.HTTPError as e:
        print(f"  [Unipile] HTTP error {e.response.status_code}: {e.response.text[:300]}")
        return []
    except Exception as e:
        print(f"  [Unipile] Error: {e}")
        return []
