"""
sources/naukri.py
=================
Naukri candidate search via Apify scraper.
Actor: pratikdaigavane/naukri-scraper  (or apify/naukri-scraper)
Docs: https://apify.com/apify/naukri-scraper

Requires: APIFY_API_TOKEN in sourcing/.env
"""
import os
import time
import requests

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID   = "pratikdaigavane/naukri-scraper"   # change to your preferred actor


def _build_search_url(jd: dict) -> str:
    """
    Naukri search URL for the actor's startUrls field.
    e.g. https://www.naukri.com/python-developer-jobs-in-bangalore?experience=2
    """
    title    = jd.get("title", "").replace(" ", "-").lower()
    location = jd.get("location", "india").replace(" ", "-").lower()
    exp_min  = jd.get("experience_min", 0)

    base = f"https://www.naukri.com/{title}-jobs-in-{location}"
    if exp_min:
        base += f"?experience={exp_min}"
    return base


def fetch(jd: dict, max_results: int = 50) -> list:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("  [Naukri] APIFY_API_TOKEN not set. Skipping.")
        return []

    search_url = _build_search_url(jd)
    print(f"  [Naukri] Starting actor for: {search_url}")

    run_input = {
        "startUrls": [{"url": search_url}],
        "maxItems": min(max_results, 100),
    }

    headers = {"Content-Type": "application/json"}
    params  = {"token": token}

    try:
        # Start actor run
        run_resp = requests.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            json=run_input,
            params=params,
            headers=headers,
            timeout=30,
        )
        run_resp.raise_for_status()
        run_id = run_resp.json()["data"]["id"]
        print(f"  [Naukri] Run started: {run_id}. Waiting for completion...")

        # Poll for completion (max 5 min)
        for _ in range(30):
            time.sleep(10)
            status_resp = requests.get(
                f"{APIFY_BASE}/acts/{ACTOR_ID}/runs/{run_id}",
                params=params,
                timeout=15,
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"  [Naukri] Run {status}. Returning empty.")
                return []

        # Fetch results from default dataset
        dataset_id = status_resp.json()["data"]["defaultDatasetId"]
        items_resp  = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={**params, "limit": max_results},
            timeout=30,
        )
        items_resp.raise_for_status()
        results = items_resp.json()
        print(f"  [Naukri] Retrieved {len(results)} profiles")
        return results
    except requests.HTTPError as e:
        print(f"  [Naukri] HTTP error {e.response.status_code}: {e.response.text[:300]}")
        return []
    except Exception as e:
        print(f"  [Naukri] Error: {e}")
        return []
