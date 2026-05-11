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
    summary_path.parent.mkdir(parents=True, exist_ok=True)
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
