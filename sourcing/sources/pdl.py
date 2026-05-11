"""
sources/pdl.py
Searches People Data Labs Person Search API.
Returns list of raw profile dicts.
"""
import os
import requests


PDL_BASE = "https://api.peopledatalabs.com/v5/person/search"


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key = os.getenv("PDL_API_KEY")
    if not api_key:
        print("  [PDL] PDL_API_KEY not set. Skipping.")
        return []

    skills   = jd.get("skills_required", [])
    title    = jd.get("title", "")
    location = jd.get("location", "india")  # default India
    exp_min  = jd.get("experience_years", {}).get("min", 0)

    # PDL uses Elasticsearch query syntax
    must_clauses = []
    if skills:
        must_clauses.append({
            "terms": {"skills": [s.lower() for s in skills[:5]]}
        })
    if title:
        must_clauses.append({
            "match": {"job_title": title}
        })
    must_clauses.append({
        "term": {"location_country": "india"}
    })

    es_query = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        }
    }

    params = {
        "query":       str(es_query).replace("'", '"'),
        "size":        min(max_results, 100),
        "pretty":      True,
        "dataset":     "resume,contact,social",
    }

    headers = {
        "X-Api-Key": api_key
    }

    print(f"  [PDL] Searching: '{title}' skills={skills[:3]} location=India")

    try:
        resp = requests.get(PDL_BASE, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("data", [])
        print(f"  [PDL] Retrieved {len(results)} profiles (total available: {data.get('total', '?')})")
        return results
    except Exception as e:
        print(f"  [PDL] Error: {e}")
        return []
