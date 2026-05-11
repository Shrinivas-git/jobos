"""
sources/naukri.py
Fetches candidate profiles from Naukri via Apify actor.
Returns list of raw profile dicts.
"""
import os
from apify_client import ApifyClient


def fetch(jd: dict, max_results: int = 50) -> list:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print("  [Naukri] APIFY_API_TOKEN not set. Skipping.")
        return []

    client = ApifyClient(token)

    # Build search keyword from JD
    keywords = jd.get("title", "")
    skills   = jd.get("skills_required", [])
    if skills:
        keywords += " " + " ".join(skills[:3])  # top 3 skills
    location = jd.get("location", "")
    exp_min  = jd.get("experience_years", {}).get("min", 0)
    exp_max  = jd.get("experience_years", {}).get("max", 15)

    run_input = {
        "keyword":    keywords.strip(),
        "location":   location,
        "experience": f"{exp_min}-{exp_max}",
        "maxResults": max_results,
    }

    print(f"  [Naukri] Searching: '{keywords}' in '{location}' exp {exp_min}-{exp_max}yrs")

    try:
        run = client.actor("leadstrategus/naukri-job-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  [Naukri] Retrieved {len(items)} results")
        return items
    except Exception as e:
        print(f"  [Naukri] Error: {e}")
        return []
