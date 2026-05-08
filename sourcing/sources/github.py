"""
sources/github.py
Searches GitHub users via GitHub REST API.
Only relevant for developer/engineering JDs.
Returns list of raw user profile dicts.
"""
import os
import requests
import time


GITHUB_BASE = "https://api.github.com"


def is_tech_jd(jd: dict) -> bool:
    tech_keywords = {
        "engineer", "developer", "devops", "backend", "frontend",
        "fullstack", "data", "ml", "ai", "python", "java", "node"
    }
    title = jd.get("title", "").lower()
    return any(k in title for k in tech_keywords)


def fetch(jd: dict, max_results: int = 30) -> list:
    token = os.getenv("GITHUB_TOKEN")

    if not is_tech_jd(jd):
        print("  [GitHub] Non-tech JD detected. Skipping GitHub source.")
        return []

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    skills   = jd.get("skills_required", [])
    location = jd.get("location", "India")

    # GitHub user search: language + location
    primary_skill = skills[0] if skills else jd.get("title", "python")
    query = f"language:{primary_skill.lower()} location:{location} type:User"

    params = {
        "q":        query,
        "per_page": min(max_results, 30),
        "sort":     "repositories",
        "order":    "desc"
    }

    print(f"  [GitHub] Searching: {query}")

    try:
        resp = requests.get(
            f"{GITHUB_BASE}/search/users",
            params=params,
            headers=headers,
            timeout=20
        )
        resp.raise_for_status()
        users = resp.json().get("items", [])

        # Fetch full profile for each user
        profiles = []
        for u in users[:max_results]:
            time.sleep(0.5)  # respect rate limit
            profile_resp = requests.get(u["url"], headers=headers, timeout=10)
            if profile_resp.ok:
                profiles.append(profile_resp.json())

        print(f"  [GitHub] Retrieved {len(profiles)} developer profiles")
        return profiles
    except Exception as e:
        print(f"  [GitHub] Error: {e}")
        return []
