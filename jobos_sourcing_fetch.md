# JobOS — External Resume Sourcing Fetch Layer
**Owner:** Srinivas / Fidelitus Corp  
**Path:** `D:\staging\jobos\sourcing\`  
**Purpose:** Given a JD JSON → query external sources → drop raw candidate profile JSONs to a folder  
**Matching:** NOT done here. Matching pipeline consumes the output folder separately.

---

## SOURCE MAP

| Source | Type | Cost | Indian Coverage | What You Get |
|--------|------|------|-----------------|--------------|
| Naukri | Apify scrape | ~$5–20/mo compute | Excellent | Job seekers, resumes |
| Unipile | LinkedIn via recruiter session | €49+/mo | Good (tech) | LinkedIn profiles |
| People Data Labs | REST API | $0 free / $98 pro | Moderate (tech) | Resume-grade profiles |
| Indeed | Apify scrape | ~$5/mo compute | Good | Job seekers |
| GitHub | REST API (free) | Free | Good (dev only) | Developer profiles |
| Coresignal | REST API | $49/mo | Moderate | Scraped professional profiles |

---

## FOLDER STRUCTURE

```
D:\staging\jobos\sourcing\
├── .env
├── requirements.txt
├── fetch_all.py              ← MASTER script — runs all sources for a JD
├── sources\
│   ├── naukri.py
│   ├── unipile.py
│   ├── pdl.py
│   ├── indeed.py
│   ├── github.py
│   └── coresignal.py
└── output\
    └── <jd_id>\
        ├── naukri\
        │   ├── candidate_001.json
        │   └── candidate_002.json
        ├── unipile\
        ├── pdl\
        ├── indeed\
        ├── github\
        └── coresignal\
```

---

## STEP 1 — Setup

```powershell
Set-Location D:\staging\jobos\sourcing
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install requests apify-client python-dotenv
```

**`.env` file:**
```
# Apify (Naukri + Indeed scrapers)
APIFY_API_TOKEN=your_apify_token

# Unipile
UNIPILE_API_KEY=your_unipile_key
UNIPILE_ACCOUNT_ID=your_linked_linkedin_account_id

# People Data Labs
PDL_API_KEY=your_pdl_key

# GitHub (no key needed for light use; add for higher rate limits)
GITHUB_TOKEN=your_github_pat

# Coresignal
CORESIGNAL_API_KEY=your_coresignal_key

# Output root
OUTPUT_DIR=D:\staging\jobos\sourcing\output
```

---

## STEP 2 — Source Scripts

### `sources/naukri.py`
Uses Apify actor `leadstrategus/naukri-job-scraper`.  
Naukri has no public resume search API — Apify is the practical route without an enterprise contract.  
This fetches **candidate-facing job listings** and extracts applicant profile signals where exposed.  
For direct resume DB access, you need Naukri's enterprise contract separately.

```python
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
```

---

### `sources/unipile.py`
Searches LinkedIn via the recruiter's connected Unipile account session.  
Requires: one LinkedIn account connected in your Unipile dashboard → copy the `account_id` to `.env`.

```python
"""
sources/unipile.py
Searches LinkedIn profiles via Unipile API using a connected recruiter session.
Returns list of raw profile dicts.
"""
import os
import requests


UNIPILE_BASE = "https://api2.unipile.com:13090/api/v1"


def fetch(jd: dict, max_results: int = 50) -> list:
    api_key    = os.getenv("UNIPILE_API_KEY")
    account_id = os.getenv("UNIPILE_ACCOUNT_ID")

    if not api_key or not account_id:
        print("  [Unipile] UNIPILE_API_KEY or UNIPILE_ACCOUNT_ID not set. Skipping.")
        return []

    headers = {
        "X-API-KEY":    api_key,
        "Content-Type": "application/json"
    }

    # Build search keywords
    title    = jd.get("title", "")
    skills   = " ".join(jd.get("skills_required", [])[:4])
    location = jd.get("location", "")
    keywords = f"{title} {skills}".strip()

    payload = {
        "account_id": account_id,
        "keywords":   keywords,
        "location":   location,
        "limit":      min(max_results, 50),   # Unipile max per call
    }

    print(f"  [Unipile] Searching LinkedIn: '{keywords}' in '{location}'")

    try:
        resp = requests.post(
            f"{UNIPILE_BASE}/linkedin/search/people",
            json=payload,
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("items", data.get("results", []))
        print(f"  [Unipile] Retrieved {len(results)} profiles")
        return results
    except Exception as e:
        print(f"  [Unipile] Error: {e}")
        return []
```

---

### `sources/pdl.py`
People Data Labs Person Search API.  
Free tier: 100 lookups/month. Pro ($98/mo): 350 enrichment credits.  
Best LinkedIn-equivalent profile data available via API without session dependency.

```python
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
```

---

### `sources/indeed.py`
Uses Apify actor to scrape Indeed job listings and extract candidate signals.  
Note: Indeed does not expose a resume DB publicly — this fetches job postings  
which your team can use to identify active job seekers in the market.

```python
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
```

---

### `sources/github.py`
GitHub User Search API — free, no scraping needed.  
Only useful for tech/developer roles. Skip for non-tech JDs.  
Returns developer profiles with languages, repos, bio.

```python
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
```

---

### `sources/coresignal.py`
Coresignal Employee API — scraped professional profiles, fresher data than PDL for some segments.  
Paid: $49/mo starter.

```python
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
```

---

## STEP 3 — Master Fetch Script

### `fetch_all.py`

```python
"""
fetch_all.py
============
Master sourcing script for JobOS.
Reads a JD JSON, queries all configured sources,
drops raw candidate profile JSONs to output/<jd_id>/<source>/

USAGE:
  python fetch_all.py --jd path\to\jd.json
  python fetch_all.py --jd path\to\jd.json --sources naukri pdl unipile
  python fetch_all.py --jd path\to\jd.json --max-per-source 30
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", r"D:\staging\jobos\sourcing\output"))

# Import all source modules
from sources import naukri, unipile, pdl, indeed, github, coresignal

ALL_SOURCES = {
    "naukri":     naukri,
    "unipile":    unipile,
    "pdl":        pdl,
    "indeed":     indeed,
    "github":     github,
    "coresignal": coresignal,
}


def save_results(jd_id: str, source_name: str, results: list):
    """Drop each candidate as an individual JSON file."""
    folder = OUTPUT_DIR / jd_id / source_name
    folder.mkdir(parents=True, exist_ok=True)

    saved = 0
    for i, item in enumerate(results):
        filename = folder / f"candidate_{i+1:04d}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "_meta": {
                    "source":     source_name,
                    "jd_id":      jd_id,
                    "fetched_at": datetime.utcnow().isoformat(),
                    "index":      i + 1,
                },
                "profile": item
            }, f, indent=2, ensure_ascii=False)
        saved += 1

    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jd",   required=True, help="Path to JD JSON file")
    parser.add_argument("--sources", nargs="+",
                        choices=list(ALL_SOURCES.keys()),
                        default=list(ALL_SOURCES.keys()),
                        help="Which sources to query (default: all)")
    parser.add_argument("--max-per-source", type=int, default=50,
                        help="Max candidates to fetch per source (default: 50)")
    args = parser.parse_args()

    with open(args.jd, "r", encoding="utf-8") as f:
        jd = json.load(f)

    jd_id = jd.get("jd_id", "JD-UNKNOWN")
    print(f"\n{'='*55}")
    print(f"  JobOS Sourcing Fetch")
    print(f"  JD: {jd_id} — {jd.get('title', '')}")
    print(f"  Sources: {args.sources}")
    print(f"  Max per source: {args.max_per_source}")
    print(f"  Output: {OUTPUT_DIR / jd_id}")
    print(f"{'='*55}\n")

    total = 0
    summary = {}

    for source_name in args.sources:
        module = ALL_SOURCES[source_name]
        print(f"--- {source_name.upper()} ---")
        try:
            results = module.fetch(jd, max_results=args.max_per_source)
            saved   = save_results(jd_id, source_name, results)
            summary[source_name] = saved
            total += saved
            print(f"  Saved {saved} profiles to output/{jd_id}/{source_name}/\n")
        except Exception as e:
            print(f"  FAILED: {e}\n")
            summary[source_name] = 0

    # Write run summary
    summary_path = OUTPUT_DIR / jd_id / "fetch_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "jd_id":      jd_id,
            "jd_title":   jd.get("title"),
            "fetched_at": datetime.utcnow().isoformat(),
            "sources":    summary,
            "total":      total
        }, f, indent=2)

    print(f"{'='*55}")
    print(f"  DONE. Total profiles fetched: {total}")
    for s, n in summary.items():
        print(f"    {s:<15} {n} profiles")
    print(f"  Summary: {summary_path}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
```

---

## PS1 DAILY USAGE

```powershell
Set-Location D:\staging\jobos\sourcing
.\venv\Scripts\Activate.ps1

# Fetch from ALL sources
python fetch_all.py --jd D:\staging\jobos\data\jds\JD-2026-001.json

# Fetch from specific sources only
python fetch_all.py --jd D:\staging\jobos\data\jds\JD-2026-001.json --sources pdl unipile

# Limit results per source
python fetch_all.py --jd D:\staging\jobos\data\jds\JD-2026-001.json --max-per-source 30

# Output lands at:
# D:\staging\jobos\sourcing\output\JD-2026-001\naukri\candidate_0001.json
# D:\staging\jobos\sourcing\output\JD-2026-001\pdl\candidate_0001.json
# ... etc
```

---

## WHAT YOUR MATCHING PIPELINE RECEIVES

Each file at `output/<jd_id>/<source>/candidate_XXXX.json` is:

```json
{
  "_meta": {
    "source":     "pdl",
    "jd_id":      "JD-2026-001",
    "fetched_at": "2026-05-08T10:30:00",
    "index":      1
  },
  "profile": {
    // raw response from that source — untouched
    // your existing normalisation + matching pipeline reads this
  }
}
```

Your existing semantic match layer reads the `profile` field. The `_meta` block tells it which source the candidate came from.

---

## CLAUDE CODE CLI PROMPT FOR DEVELOPER

```
You are working on JobOS sourcing fetch at D:\staging\jobos\sourcing.

Files present:
  fetch_all.py          master script
  sources\naukri.py
  sources\unipile.py
  sources\pdl.py
  sources\indeed.py
  sources\github.py
  sources\coresignal.py
  .env                  API keys

Task:
1. Read fetch_all.py and all source files first.
2. Create an empty sources\__init__.py if missing.
3. Test ONE source at a time — start with pdl.py since it needs no scraping setup.
4. Run: python fetch_all.py --jd <sample_jd.json> --sources pdl
5. Confirm JSON files appear in output\<jd_id>\pdl\
6. Then test github (free, no billing risk).
7. Then unipile (needs account_id from dashboard).
8. Then naukri + indeed (needs Apify token + billing).
9. Fix only errors. Do not refactor.
10. Report: which sources produced output, which failed and why.
```

---

## PAID vs FREE SUMMARY

| Source | Free Tier | Monthly Cost |
|--------|-----------|--------------|
| GitHub | Yes — 5000 req/hr with token | Free |
| PDL | 100 lookups/mo | $0 → $98 pro |
| Apify (Naukri+Indeed) | $5 free compute/mo | ~$10–30 |
| Unipile | 7-day trial | €49+ |
| Coresignal | No free tier | $49+ |
