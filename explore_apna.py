"""Throwaway — open Apna blank posting form properly (click button by role), dump fields."""
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

SESSION = "api/sessions/apna.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def dump_fields(page, label):
    print(f"\n===== {label} =====")
    print("URL:", page.url)
    fields = page.eval_on_selector_all(
        "input, textarea, select",
        "els=>els.map(e=>({tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',ph:e.placeholder||'',label:(e.getAttribute('aria-label')||'')}))"
    )
    print("-- FIELDS --")
    for f in fields[:60]:
        print(f"  {f['tag']} type={f['type']} name={f['name']} id={f['id']} ph={f['ph']} aria={f['label']}")
    btns = page.eval_on_selector_all("button", "els=>els.map(e=>(e.innerText||'').trim().slice(0,35)).filter(x=>x)")
    print("-- BUTTONS --")
    for b in btns[:30]:
        print("  [", b, "]")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(
        storage_state=SESSION, user_agent=UA, locale="en-IN",
        timezone_id="Asia/Kolkata", viewport={"width": 1366, "height": 900},
    )
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page = context.new_page()

    page.goto("https://employer.apna.co/jobs", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(7000)

    # The body "Start with blank form" button (role=button), not the heading
    try:
        btn = page.get_by_role("button", name="Start with blank form")
        print("blank-form buttons found:", btn.count())
        with context.expect_page(timeout=8000) as new_page_info:
            btn.last.click(timeout=8000)
        newp = new_page_info.value
        newp.wait_for_timeout(6000)
        print("NEW PAGE opened:", newp.url)
        dump_fields(newp, "BLANK FORM (new tab)")
        newp.screenshot(path="apna_form_step1.png", full_page=True)
    except Exception:
        # No new tab — same-page navigation
        page.wait_for_timeout(6000)
        dump_fields(page, "BLANK FORM (same tab)")
        page.screenshot(path="apna_form_step1.png", full_page=True)

    print("\n[screenshot: apna_form_step1.png]")
    browser.close()
