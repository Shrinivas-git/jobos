# ==============================================================================
# jobos-sourcing-sessions.ps1
# Owner: Srinivas / Fidelitus Corp
# PRD:   C:\staging\jobos\jobos_sourcing_fetch.md
# Path:  D:\staging\jobos\sourcing\
# ==============================================================================
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("setup","pdl","github","unipile","naukri","indeed","coresignal","master","debug","list")]
    [string]$Session
)

$PROJECT_ROOT = "D:\staging\jobos\sourcing"
$HAIKU        = "claude-haiku-4-5-20251001"
$SONNET       = "claude-sonnet-4-6"

$sessions = @{

    setup = @{
        model = $HAIKU
        task  = "TASK-001"
        label = "Session 1 - Setup - venv, folders, .env, __init__"
        prompt = @'
Stack: Python 3.x, PowerShell, Windows
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-001 - Initial setup

Steps to execute in order:
1. Set-Location D:\staging\jobos\sourcing
2. python -m venv venv
3. .\venv\Scripts\Activate.ps1
4. pip install requests apify-client python-dotenv
5. Create folder structure exactly as in PRD:
   - sources\
   - output\
6. Create sources\__init__.py (empty)
7. Create .env file with all keys as placeholders (do NOT fill real keys)
8. Create requirements.txt with: requests, apify-client, python-dotenv

Module scope: D:\staging\jobos\sourcing\ ONLY.
PDCA: present plan before touching any file.
Do not create any source scripts yet - setup only.
'@
    }

    pdl = @{
        model = $HAIKU
        task  = "TASK-002"
        label = "Session 2 - Source - PDL (People Data Labs)"
        prompt = @'
Stack: Python 3.x, requests, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-002 - Create and test sources\pdl.py

Steps:
1. Create sources\pdl.py exactly as in PRD (no changes)
2. Create a sample JD JSON at D:\staging\jobos\sourcing\sample_jd.json:
   {
     "jd_id": "JD-2026-TEST",
     "title": "Python Developer",
     "skills_required": ["python", "django", "postgresql"],
     "location": "Bengaluru",
     "experience_years": { "min": 2, "max": 6 }
   }
3. Test ONLY pdl source:
   python fetch_all.py --jd sample_jd.json --sources pdl
4. Confirm JSON files appear at output\JD-2026-TEST\pdl\
5. Report: how many profiles returned, any errors

Module scope: sources\pdl.py ONLY.
Key facts:
- PDL free tier: 100 lookups/month - do not over-test
- PDL_API_KEY must be set in .env before running
- ES query uses single-quote/double-quote - watch JSON stringify
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    github = @{
        model = $HAIKU
        task  = "TASK-003"
        label = "Session 3 - Source - GitHub (free, no billing risk)"
        prompt = @'
Stack: Python 3.x, requests, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-003 - Create and test sources\github.py

Steps:
1. Create sources\github.py exactly as in PRD (no changes)
2. Create sample_jd.json if it does not exist:
   {
     "jd_id": "JD-2026-TEST",
     "title": "Python Developer",
     "skills_required": ["python", "django", "postgresql"],
     "location": "Bengaluru",
     "experience_years": { "min": 2, "max": 6 }
   }
3. Create fetch_all.py exactly as in PRD (needed to run the test)
4. Create sources\__init__.py if missing (empty file)
5. Test ONLY github source:
   python fetch_all.py --jd sample_jd.json --sources github
6. Confirm JSON files appear at output\JD-2026-TEST\github\
7. Report: how many profiles returned, any rate limit warnings

Module scope: sources\github.py ONLY.
Key facts:
- GitHub is FREE - safe to test without billing concern
- GITHUB_TOKEN optional but increases rate limit from 60 to 5000 req/hr
- is_tech_jd() filter: skips non-tech JDs automatically
- 0.5s sleep between profile fetches - do not remove
- max 30 results per call (GitHub search API cap)
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    unipile = @{
        model = $SONNET
        task  = "TASK-004"
        label = "Session 4 - Source - Unipile (LinkedIn)"
        prompt = @'
Stack: Python 3.x, requests, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-004 - Create and test sources\unipile.py

Steps:
1. Create sources\unipile.py exactly as in PRD (no changes)
2. Confirm .env has: UNIPILE_API_KEY and UNIPILE_ACCOUNT_ID
   (account_id comes from Unipile dashboard after connecting LinkedIn)
3. Test ONLY unipile source:
   python fetch_all.py --jd sample_jd.json --sources unipile
4. Confirm JSON files appear at output\JD-2026-TEST\unipile\
5. Report: profiles returned, any auth errors

Module scope: sources\unipile.py ONLY.
Key facts:
- Base URL: https://api2.unipile.com:13090/api/v1
- Endpoint: POST /linkedin/search/people
- Max 50 results per call (Unipile hard cap)
- Requires ONE LinkedIn account connected in Unipile dashboard first
- 7-day trial - check expiry before testing
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    naukri = @{
        model = $SONNET
        task  = "TASK-005"
        label = "Session 5 - Source - Naukri (Apify scraper)"
        prompt = @'
Stack: Python 3.x, apify-client, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-005 - Create and test sources\naukri.py

Steps:
1. Create sources\naukri.py exactly as in PRD (no changes)
2. Confirm .env has: APIFY_API_TOKEN
3. Test ONLY naukri source:
   python fetch_all.py --jd sample_jd.json --sources naukri
4. Confirm JSON files appear at output\JD-2026-TEST\naukri\
5. Report: profiles returned, Apify compute used, any errors

Module scope: sources\naukri.py ONLY.
Key facts:
- Apify actor: leadstrategus/naukri-job-scraper
- APIFY_API_TOKEN must be set and account must have compute credits
- Naukri has NO public resume DB API - fetches job listings + applicant signals
- Apify free tier: $5 compute/mo - watch usage
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    indeed = @{
        model = $HAIKU
        task  = "TASK-006"
        label = "Session 6 - Source - Indeed (Apify scraper)"
        prompt = @'
Stack: Python 3.x, apify-client, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-006 - Create and test sources\indeed.py

Steps:
1. Create sources\indeed.py exactly as in PRD (no changes)
2. Confirm .env has: APIFY_API_TOKEN (same token as Naukri)
3. Test ONLY indeed source:
   python fetch_all.py --jd sample_jd.json --sources indeed
4. Confirm JSON files appear at output\JD-2026-TEST\indeed\
5. Report: results returned, any errors

Module scope: sources\indeed.py ONLY.
Key facts:
- Apify actor: misceres/indeed-scraper
- country code: IN for India
- Indeed has NO resume DB - returns job postings to identify active job seekers
- Shares APIFY_API_TOKEN with Naukri - same billing pool
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    coresignal = @{
        model = $HAIKU
        task  = "TASK-007"
        label = "Session 7 - Source - Coresignal"
        prompt = @'
Stack: Python 3.x, requests, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-007 - Create and test sources\coresignal.py

Steps:
1. Create sources\coresignal.py exactly as in PRD (no changes)
2. Confirm .env has: CORESIGNAL_API_KEY
3. Test ONLY coresignal source:
   python fetch_all.py --jd sample_jd.json --sources coresignal
4. Confirm JSON files appear at output\JD-2026-TEST\coresignal\
5. Report: profiles returned, any errors

Module scope: sources\coresignal.py ONLY.
Key facts:
- Base URL: https://api.coresignal.com/cdapi/v1
- Endpoint: POST /linkedin/member/search/filter
- No free tier - $49/mo starter, confirm subscription before running
- Returns list OR dict with data/items key - handle both (already in script)
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    master = @{
        model = $SONNET
        task  = "TASK-008"
        label = "Session 8 - Master - fetch_all.py + full run + summary"
        prompt = @'
Stack: Python 3.x, all source modules, python-dotenv
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\
Task: TASK-008 - Create fetch_all.py and run full fetch

Steps:
1. Create fetch_all.py exactly as in PRD (no changes)
2. Confirm all sources\*.py files exist
3. Confirm sources\__init__.py exists (empty)
4. Run full fetch (all sources that have keys configured):
   python fetch_all.py --jd sample_jd.json
5. Confirm fetch_summary.json written to output\JD-2026-TEST\
6. Report final summary: which sources succeeded, which failed and why

Module scope: fetch_all.py ONLY (do not touch source files).
Key facts:
- OUTPUT_DIR read from .env - confirm it matches D:\staging\jobos\sourcing\output
- Sources with missing API keys skip gracefully - that is expected behaviour
- fetch_summary.json is the handoff artifact for the matching pipeline
- Each candidate file has _meta block: source, jd_id, fetched_at, index
PDCA: present plan before touching any file.
Fix errors only. Do not refactor.
'@
    }

    debug = @{
        model = $SONNET
        task  = "TASK-DBG"
        label = "Debug Session - One error, one file, one session"
        prompt = @'
Stack: Python 3.x, sourcing fetch layer
PRD: C:\staging\jobos\jobos_sourcing_fetch.md
Project root: D:\staging\jobos\sourcing\

Task: Fix ONE error only.
Paste below:
  1. Full traceback / error output
  2. Only the function that threw it (not entire file)

Known gotchas:
- PDL ES query: single-quote/double-quote mismatch in JSON string
- Unipile: account_id must be from dashboard, not API key
- GitHub: rate limit 60/hr without token, 5000/hr with token
- Apify: actor names are case-sensitive
- .env not loaded: confirm load_dotenv() called before os.getenv()
- sources\__init__.py missing: causes ImportError in fetch_all.py

Fix the error. Do not refactor. Do not touch other files.
'@
    }

}

# ------------------------------------------------------------------
if ($Session -eq "list") {
    Write-Host ""
    Write-Host "  Available sessions:" -ForegroundColor Cyan
    Write-Host ""
    foreach ($key in $sessions.Keys | Sort-Object) {
        $s = $sessions[$key]
        $tag = if ($s.model -like "*haiku*") { "Haiku  [GREEN]" } else { "Sonnet [BLUE]" }
        Write-Host ("  {0,-14} {1,-50} [{2}]" -f $key, $s.label, $tag)
    }
    Write-Host ""
    exit 0
}

# ------------------------------------------------------------------
$s = $sessions[$Session]
Write-Host ""
Write-Host "  +----------------------------------------------+" -ForegroundColor Cyan
Write-Host ("  |  {0,-44}|" -f $s.label) -ForegroundColor Cyan
Write-Host ("  |  Model : {0,-38}|" -f $s.model) -ForegroundColor Cyan
Write-Host ("  |  Task  : {0,-38}|" -f $s.task) -ForegroundColor Cyan
Write-Host "  +----------------------------------------------+" -ForegroundColor Cyan
Write-Host ""
Write-Host $s.prompt -ForegroundColor White
Write-Host ""
$s.prompt | Set-Clipboard
Write-Host "  Copied to clipboard. Paste into Claude Code and run." -ForegroundColor Green
Write-Host ""
Set-Location $PROJECT_ROOT
$env:ANTHROPIC_MODEL = $s.model
claude --model $s.model
