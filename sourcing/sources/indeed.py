"""
sources/indeed.py
Scrapes Indeed via Apify actor.
Returns list of job/candidate signal dicts.
"""
import os
from apify_client import ApifyClient


def fetch(jd: dict, max_results: int = 50) -> list:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("  [Indeed] APIFY_API_TOKEN not set. Skipping.")
        return []

    client   = ApifyClient(token)
    title    = jd.get("title", "")
    skills   = " ".join(jd.get("skills_required", [])[:3])
    location = jd.get("location", "Bengaluru")
    query    = f"{title} {skills}".strip()

    run_input = {
        "position":   query,
        "country":    "IN",
        "location":   location,
        "maxItems":   max_results,
    }

    print(f"  [Indeed] Searching: '{query}' in '{location}'")

    try:
        run   = client.actor("misceres/indeed-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  [Indeed] Retrieved {len(items)} results")
        return items
    except Exception as e:
        print(f"  [Indeed] Error: {e}")
        return []
