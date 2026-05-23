"""Capture Apna's job-creation API call while YOU post one job by hand.

USAGE:
  python capture_apna.py

WHAT TO DO:
  1. A browser opens, logged into Apna, on the post-job page.
  2. Fill the form yourself and POST the job (solve the captcha).
  3. Come back here and press ENTER.
  4. It saves everything to apna_capture.json for analysis.
"""
import json
from playwright.sync_api import sync_playwright

SESSION = "api/sessions/apna.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

captured = []


def looks_interesting(url, method):
    return (
        "apna.co" in url
        and method in ("POST", "PUT", "PATCH")
        and "mixpanel" not in url
        and "track" not in url
    )


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled", "--start-maximized"])
    context = browser.new_context(
        storage_state=SESSION, user_agent=UA, locale="en-IN",
        timezone_id="Asia/Kolkata", no_viewport=True,
    )
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = context.new_page()

    def on_request(req):
        if looks_interesting(req.url, req.method):
            body = None
            try:
                body = req.post_data
            except Exception:
                pass
            captured.append({
                "method": req.method,
                "url": req.url,
                "auth_header": req.headers.get("authorization", "")[:25] + "..." if req.headers.get("authorization") else "",
                "content_type": req.headers.get("content-type", ""),
                "body": body,
            })
            print(f"  captured: {req.method} {req.url.split('apna.co')[-1][:70]}")

    page.on("request", on_request)

    page.goto("https://employer.apna.co/post-job", timeout=60000, wait_until="domcontentloaded")
    print("\n  Apna post-job page is open and logged in.")
    print("  >> Fill the form and POST a job (solve the captcha).")
    input("  >> When the job is POSTED, press ENTER here...\n")

    with open("apna_capture.json", "w", encoding="utf-8") as f:
        json.dump(captured, f, indent=2)
    print(f"\n  Saved {len(captured)} API calls to apna_capture.json")
    browser.close()
