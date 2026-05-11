"""
sources/indeed.py
=================
Indeed job seeker / resume search via Apify scraper.
Actor: misceres/indeed-scraper  (searches Indeed for job postings, extracts applicant signals)
Docs: https://apify.com/misceres/indeed-scraper

Note: Indeed does not expose a public resume database. This source searches
job postings matching the JD's requirements to identify active job-seekers
(companies hiring the same skills = people looking to move).

Requires: APIFY_API_TOKEN in sourcing/.env
"""
import os
import time
import requests

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID   = "misceres/indeed-scraper"


def fetch(jd: dict, max_results: int = 50) -> list:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("  [Indeed] APIFY_API_TOKEN not set. Skipping.")
        return []

    title    = jd.get("title", "Software Engineer")
    location = jd.get("location", "India")
    country  = "IN" if "india" in location.lower() else "US"

    print(f"  [Indeed] Scraping Indeed for '{title}' in '{location}'")

    run_input = {
        "position":   title,
        "country":    country,
        "location":   location,
        "maxItems":   min(max_results, 100),
        "parseCompanyDetails": False,
        "saveOnlyUniqueItems": True,
    }

    params  = {"token": token}
    headers = {"Content-Type": "application/json"}

    try:
        run_resp = requests.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            json=run_input,
            params=params,
            headers=headers,
            timeout=30,
        )
        run_resp.raise_for_status()
        run_id = run_resp.json()["data"]["id"]
        print(f"  [Indeed] Run started: {run_id}. Waiting for completion...")

        # Poll for completion (max 5 min)
        status_resp = None
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
                print(f"  [Indeed] Run {status}. Returning empty.")
                return []

        dataset_id = status_resp.json()["data"]["defaultDatasetId"]
        items_resp  = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={**params, "limit": max_results},
            timeout=30,
        )
        items_resp.raise_for_status()
        results = items_resp.json()
        print(f"  [Indeed] Retrieved {len(results)} job posting records")
        return results
    except requests.HTTPError as e:
        print(f"  [Indeed] HTTP error {e.response.status_code}: {e.response.text[:300]}")
        return []
    except Exception as e:
        print(f"  [Indeed] Error: {e}")
        return []
