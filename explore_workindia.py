"""Throwaway — check if WorkIndia job posting is free or paid (logged-in session)."""
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

SESSION = "api/sessions/workindia.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

PRICE_WORDS = ["price", "pay", "₹", "rupee", "credit", "plan", "subscription", "buy", "premium", "free", "checkout", "cost"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(
        storage_state=SESSION, user_agent=UA, locale="en-IN",
        timezone_id="Asia/Kolkata", viewport={"width": 1366, "height": 900},
    )
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = context.new_page()

    page.goto("https://www.workindia.in/recruiter/home/", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)

    body = page.inner_text("body").lower()
    logged_in = "refining skills" in body or "logout" in body or "post a job" in body
    print("Logged in signal:", logged_in)
    print("Has 'login' button:", "login" in body)

    # Try clicking a posting entry point by role
    for name in ["Post a Job", "Start Hiring Now", "Post Job", "Start Hiring"]:
        try:
            btn = page.get_by_role("button", name=name)
            if btn.count() == 0:
                btn = page.get_by_text(name, exact=False)
            if btn.count() > 0:
                with context.expect_page(timeout=6000) as np:
                    btn.first.click(timeout=5000)
                page = np.value
                page.wait_for_timeout(5000)
                print(f"Clicked '{name}' -> new tab: {page.url}")
                break
        except Exception:
            try:
                page.wait_for_timeout(5000)
                print(f"Clicked '{name}' (same tab) -> {page.url}")
                break
            except Exception:
                pass

    print("FINAL URL:", page.url)
    body2 = page.inner_text("body").lower()
    import re
    print("\n-- price/free signals on this page --")
    for w in PRICE_WORDS:
        hits = [m.strip() for m in re.findall(r'[^\n]{0,30}' + re.escape(w) + r'[^\n]{0,30}', body2)][:3]
        for h in hits:
            print(f"  [{w}] {h}")

    page.screenshot(path="workindia_post.png", full_page=True)
    print("\n[screenshot: workindia_post.png]")
    browser.close()
