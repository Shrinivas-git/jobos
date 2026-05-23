"""
setup_portal_sessions.py
========================
One-time setup script — run this on your LOCAL machine (not in Docker).
Opens a real browser for each portal so you can log in manually (handle OTP yourself).
Saves the session (cookies) so the robot never needs to log in again.

USAGE:
  pip install playwright
  playwright install chromium
  python setup_portal_sessions.py

  Or to do just one portal:
  python setup_portal_sessions.py --portal glassdoor
"""

import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSIONS_DIR = Path(__file__).parent / "api" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

PORTALS = {
    "internshala": {
        "name": "Internshala",
        "url": "https://internshala.com/hire-talent/",
        "ready_hint": "You are on the Internshala recruiter dashboard",
    },
    "apna": {
        "name": "Apna",
        "url": "https://employer.apna.co/jobs",
        "ready_hint": "You are on the Apna employer dashboard",
    },
    "placementindia": {
        "name": "PlacementIndia",
        "url": "https://www.placementindia.com/job-recruiters/",
        "ready_hint": "You are on the PlacementIndia recruiter dashboard",
    },
    "workindia": {
        "name": "WorkIndia",
        "url": "https://www.workindia.in/recruiter/home/",
        "ready_hint": "You are on the WorkIndia recruiter dashboard",
    },
    "shine": {
        "name": "Shine",
        "url": "https://recruiter.shine.com/",
        "ready_hint": "You are on the Shine recruiter dashboard",
    },
    "glassdoor": {
        "name": "Glassdoor",
        "url": "https://www.glassdoor.com/employers/",
        "ready_hint": "You are on the Glassdoor employer dashboard",
    },
    "indeed": {
        "name": "Indeed",
        "url": "https://employers.indeed.com/",
        "ready_hint": "You are on the Indeed employer dashboard",
    },
}


def save_session(portal_key: str, portal: dict):
    print(f"\n{'='*55}")
    print(f"  {portal['name']}")
    print(f"{'='*55}")
    print(f"  Opening browser at: {portal['url']}")
    print(f"  → Log in manually (handle OTP on your phone)")
    print(f"  → Once you are fully logged in and can see the dashboard,")
    print(f"    come back here and press ENTER to save the session.")
    print(f"{'='*55}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(portal["url"], timeout=30000)

        input("  Press ENTER after you are fully logged in... ")

        session_path = SESSIONS_DIR / f"{portal_key}.json"
        context.storage_state(path=str(session_path))
        browser.close()

    print(f"  Session saved → api/sessions/{portal_key}.json\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--portal",
        choices=list(PORTALS.keys()),
        help="Run for a single portal only (default: all)",
    )
    args = parser.parse_args()

    portals_to_run = (
        {args.portal: PORTALS[args.portal]} if args.portal else PORTALS
    )

    print("\n  JobOS — One-Time Portal Session Setup")
    print("  A browser will open for each portal.")
    print("  Log in manually, then press ENTER to save.\n")

    saved = []
    failed = []

    for key, portal in portals_to_run.items():
        try:
            save_session(key, portal)
            saved.append(portal["name"])
        except Exception as e:
            print(f"  ERROR for {portal['name']}: {e}\n")
            failed.append(portal["name"])

    print(f"\n{'='*55}")
    print(f"  Setup complete!")
    if saved:
        print(f"  Saved : {', '.join(saved)}")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    print(f"\n  Sessions are in: api/sessions/")
    print(f"  Docker will pick them up automatically on next restart.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
