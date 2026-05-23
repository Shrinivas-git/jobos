"""Capture WorkIndia's job-creation API call while YOU post one (free) job by hand.

USAGE:
  python capture_workindia.py

WHAT TO DO:
  1. A browser opens, logged into WorkIndia, on the post-job page.
  2. Dismiss the popup ("I want to hire people"), fill the form, POST the job.
  3. If a captcha appears, note it. Solve it.
  4. Come back here and press ENTER.
  5. Everything is saved to workindia_capture.json for analysis.
"""
import json
from playwright.sync_api import sync_playwright

SESSION = "api/sessions/workindia.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

captured = []
saw_captcha = {"v": False}


def interesting(url, method):
    return ("workindia.in" in url and method in ("POST", "PUT", "PATCH")
            and "track" not in url and "analytics" not in url and "log" not in url)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled", "--start-maximized"])
    context = browser.new_context(storage_state=SESSION, user_agent=UA, locale="en-IN",
                                  timezone_id="Asia/Kolkata", no_viewport=True)
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = context.new_page()

    def on_request(req):
        u = req.url
        if "recaptcha" in u or "captcha" in u or "hcaptcha" in u:
            saw_captcha["v"] = True
        if interesting(u, req.method):
            try:
                body = req.post_data
            except Exception:
                body = None
            captured.append({
                "method": req.method, "url": u,
                "auth": (req.headers.get("authorization", "")[:20] + "...") if req.headers.get("authorization") else "",
                "content_type": req.headers.get("content-type", ""),
                "body": body,
            })
            print(f"  captured: {req.method} {u.split('workindia.in')[-1][:70]}")

    page.on("request", on_request)

    page.goto("https://www.workindia.in/post-job/", timeout=60000, wait_until="domcontentloaded")
    print("\n  WorkIndia post-job page is open and logged in.")
    print("  >> Dismiss the popup, fill the form, and POST the job (it's free).")
    print("  >> If you see a captcha ('I'm not a robot' / images), note it.")
    input("  >> When the job is POSTED, press ENTER here...\n")

    with open("workindia_capture.json", "w", encoding="utf-8") as f:
        json.dump({"captcha_script_loaded": saw_captcha["v"], "calls": captured}, f, indent=2)
    print(f"\n  Saved {len(captured)} API calls to workindia_capture.json")
    print(f"  Captcha script seen: {saw_captcha['v']}")
    browser.close()
