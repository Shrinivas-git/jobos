"""Log into Glassdoor employer with email/password and save the session.

USAGE:
  python capture_glassdoor.py

WHAT TO DO:
  1. Browser opens at Glassdoor employer sign-in (email/password pre-filled).
  2. Click Sign In. Handle any 2FA code / captcha if it appears.
  3. Once you're on the employer dashboard, come back and press ENTER.
  4. Session is saved to api/sessions/glassdoor.json
"""
from playwright.sync_api import sync_playwright

EMAIL = "radhika@refiningskills.org"
PASSWORD = "Hiring@rs"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled", "--start-maximized"])
    context = browser.new_context(user_agent=UA, locale="en-IN", no_viewport=True)
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = context.new_page()

    page.goto("https://www.glassdoor.com/employers/", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    print("\n  Glassdoor employers page is open.")
    print(f"  >> Click 'Sign In' / 'Employer Login' and log in:")
    print(f"       Email:    {EMAIL}")
    print(f"       Password: {PASSWORD}")
    print("  >> Handle any 2FA/captcha, reach the employer dashboard.")
    input("  >> When you're logged in, press ENTER here to save the session...\n")

    context.storage_state(path="api/sessions/glassdoor.json")
    print("  Saved -> api/sessions/glassdoor.json")
    print("  Landed URL:", page.url)
    browser.close()
