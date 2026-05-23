"""
Find the form action URL and CSRF token from the job form.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION = Path("api/sessions/internshala.json")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(storage_state=str(SESSION))
    page = context.new_page()

    page.goto("https://internshala.com/job/form", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=30000)
    page.evaluate("var b=document.getElementById('job_form_btn_2'); if(b) b.click();")
    page.wait_for_timeout(1500)

    # Get all form elements and their actions
    forms = page.evaluate("""
        Array.from(document.querySelectorAll('form')).map(f => ({
            action: f.action,
            method: f.method,
            id: f.id,
            hasJobTitle: !!f.querySelector('#job_title'),
            hasProfile: !!f.querySelector('#profile'),
        }))
    """)
    print("\\nForms on page:")
    for f in forms:
        print(f)

    # Get CSRF token
    csrf = page.evaluate("document.getElementById('csrf') ? document.getElementById('csrf').value : 'NOT FOUND'")
    print(f"\\nCSRF token: {csrf!r}")

    # Check which radio is selected
    form_loader = page.evaluate("""
        var radios = document.querySelectorAll('input[name=form_loader]');
        var selected = '';
        radios.forEach(r => { if(r.checked) selected = r.id + '=' + r.value; });
        selected;
    """)
    print(f"Selected form_loader radio: {form_loader!r}")

    browser.close()
