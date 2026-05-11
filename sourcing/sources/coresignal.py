"""
sources/coresignal.py
=====================
Coresignal — professional profiles & fresh data API.
Docs: https://docs.coresignal.com/

Endpoint used: Member Search API (LinkedIn-style professional profiles)

Requires: CORESIGNAL_API_KEY in sourcing/.env
"""
import os
import requests

CORESIGNAL_BASE = "https://api.coresignal.com/cdapi/v1"


def _build_filters(jd: dict) -> dict:
    filters = {}

    skills = jd.get("skills_required", [])
    if skills:
        filters["member_skills"] = skills[:10]

    location = jd.get("location", "")
    if location:
        if "india" in location.lower():
            filters["location_country"] = "India"
        else:
            filters["location"] = location

    title = jd.get("title", "")
    if title:
        filters["title"] = title

    exp_min = jd.get("experience_min")
    exp_max = jd.get("experience_max")
    if exp_min is not None:
        filters["experience_years_from"] = exp_min
    if exp_max is not None:
        filters["experience_years_to"] = exp_max

    return filters


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key = os.getenv("CORESIGNAL_API_KEY")
    if not api_key:
        print("  [Coresignal] CORESIGNAL_API_KEY not set. Skipping.")
        return []

    filters = _build_filters(jd)
    print(f"  [Coresignal] Searching with filters: {filters}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }

    results = []

    try:
        # Step 1: Search for member IDs
        search_payload = {
            "filters": filters,
            "limit":   min(max_results, 100),
            "offset":  0,
        }
        search_resp = requests.post(
            f"{CORESIGNAL_BASE}/linkedin/member/search/filter",
            json=search_payload,
            headers=headers,
            timeout=30,
        )
        search_resp.raise_for_status()
        member_ids = search_resp.json()  # returns list of int IDs

        print(f"  [Coresignal] Found {len(member_ids)} member IDs. Fetching profiles...")

        # Step 2: Fetch each profile
        for mid in member_ids[:max_results]:
            try:
                profile_resp = requests.get(
                    f"{CORESIGNAL_BASE}/linkedin/member/collect/{mid}",
                    headers=headers,
                    timeout=20,
                )
                if profile_resp.ok:
                    results.append(profile_resp.json())
            except Exception as e:
                print(f"  [Coresignal] Failed to fetch member {mid}: {e}")

        print(f"  [Coresignal] Retrieved {len(results)} full profiles")
        return results
    except requests.HTTPError as e:
        print(f"  [Coresignal] HTTP error {e.response.status_code}: {e.response.text[:300]}")
        return []
    except Exception as e:
        print(f"  [Coresignal] Error: {e}")
        return []
