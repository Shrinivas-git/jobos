"""
sources/pdl.py
==============
People Data Labs — Person Search API
Docs: https://docs.peopledatalabs.com/docs/person-search-api

Requires: PDL_API_KEY in sourcing/.env
"""
import os
import requests

PDL_BASE = "https://api.peopledatalabs.com/v5"


def _build_query(jd: dict) -> dict:
    """Build a PDL Elasticsearch query from JD fields."""
    must = []

    skills = jd.get("skills_required", [])
    if skills:
        must.append({
            "terms": {"skills.name": [s.lower() for s in skills[:5]]}
        })

    location = jd.get("location", "")
    if location:
        must.append({"match": {"location_country": "india"}} if "india" in location.lower()
                    else {"match": {"location_name": location}})

    exp_min = jd.get("experience_min", 0)
    if exp_min:
        must.append({"range": {"experience": {"gte": exp_min}}})

    return {"query": {"bool": {"must": must}}} if must else {"query": {"match_all": {}}}


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key = os.getenv("PDL_API_KEY")
    if not api_key:
        print("  [PDL] PDL_API_KEY not set. Skipping.")
        return []

    es_query = _build_query(jd)
    params = {
        "api_key": api_key,
        "size": min(max_results, 100),
        "pretty": False,
    }

    print(f"  [PDL] Searching with query: {es_query}")

    try:
        resp = requests.post(
            f"{PDL_BASE}/person/search",
            json={"query": es_query["query"]},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data", [])
        print(f"  [PDL] Retrieved {len(results)} profiles (total={data.get('total', '?')})")
        return results
    except requests.HTTPError as e:
        print(f"  [PDL] HTTP error {e.response.status_code}: {e.response.text[:300]}")
        return []
    except Exception as e:
        print(f"  [PDL] Error: {e}")
        return []
