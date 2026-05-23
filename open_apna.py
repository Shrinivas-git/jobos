"""Open Apna employer dashboard in a real browser, already logged in (no OTP).
Uses the saved session. Browser stays open until you close it or press ENTER here.

USAGE:  python open_apna.py
"""
from playwright.sync_api import sync_playwright

SESSION = "api/sessions/apna.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(
        storage_state=SESSION, user_agent=UA, locale="en-IN",
        timezone_id="Asia/Kolkata", viewport={"width": 1366, "height": 768},
    )
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = context.new_page()
    page.goto("https://employer.apna.co/jobs", timeout=60000, wait_until="domcontentloaded")

    print("\n  Apna is open and logged in. Check your jobs in the browser window.")
    input("  Press ENTER here when you're done to close the browser...\n")
    browser.close()
