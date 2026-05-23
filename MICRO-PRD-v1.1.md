# MICRO-PRD: Fidelitus HR — Multi-Portal JD Distribution & Candidate Intake Pipeline
**Version:** 1.1  
**Owner:** Srinivas / Fidelitus Corp – HR Services Vertical  
**Status:** Ready for Development  
**Stack:** Python 3.13 · FastAPI · MongoDB · Unipile API · Claude API · Playwright · PowerShell automation  

---

## 1. Problem Statement

Fidelitus HR (recruitment agency) posts jobs across multiple portals manually, receives applications in disparate systems, and manages candidate screening ad hoc via LinkedIn DMs through Unipile. There is no unified intake pipeline. Resumes are scattered across portal dashboards, emails, and DMs.

**Goal:** Parse a JD once → auto-distribute to all portals (API where available, Playwright browser automation where not) → receive all applications at a single webhook endpoint or intake form → store, parse, and screen candidates uniformly.

---

## 2. Scope & Constraints

### In Scope
- JD parsing and enrichment via Claude API  
- Indeed posting via XML feed (API)
- Internshala, Apna, Shine, WorkIndia, PlacementIndia, Glassdoor posting via **Playwright browser automation** (legal — uses your registered employer accounts, posts real jobs)
- LinkedIn posting: **manual** (no API available without enterprise partner programme)
- Hosted intake web form (`apply_url`) embedded as external apply link on all non-Indeed portals
- Indeed Apply `postUrl` webhook receiver — resume delivered as Base64 POST
- Unipile: LinkedIn applicant polling + auto-DM fallback to intake form
- Candidate record creation in MongoDB with resume file storage
- Resume text extraction (PDF/DOCX/Base64)
- Claude API screening score per candidate
- Email publisher as **fallback** if Playwright breaks on a portal after a UI change

### Out of Scope (Phase 1)
- LinkedIn Job Posting API (requires LinkedIn Talent Solutions Partner Programme — enterprise only)
- OTP automation for Apna (requires SMS gateway like MSG91; Apna login is phone + OTP)
- Paid portal integrations (Naukri, Foundit premium)
- Interview scheduling
- Client-facing portal

---

## 3. Portal Capability Matrix

| Portal | Post via API | Receive Apps via API | Posting Approach | Application Intake |
|---|---|---|---|---|
| **Indeed** | ✅ XML feed (free) | ✅ `postUrl` webhook | XML feed auto-generated | Indeed POSTs resume JSON to `/webhook/indeed` |
| **LinkedIn** | ❌ Partner programme only | ✅ Unipile session poll | **Manual post** with external apply URL | Unipile poll + DM fallback to intake form |
| **Internshala** | ❌ No API | ❌ No API | **Playwright automation** | External apply URL → intake form |
| **Apna** | ❌ No API | ❌ No API | **Playwright automation** (OTP login — see note) | External apply URL → intake form |
| **Glassdoor** | ❌ No API | ❌ No API | **Playwright automation** | External apply URL → intake form |
| **Shine.com** | ❌ No API | ❌ No API | **Playwright automation** | External apply URL → intake form |
| **WorkIndia** | ❌ No API | ❌ No API | **Playwright automation** | External apply URL → intake form |
| **PlacementIndia** | ❌ No API | ❌ No API | **Playwright automation** | External apply URL → intake form |

> **Apna OTP note:** Apna login requires phone + OTP. For full headless automation, integrate an SMS gateway (MSG91 or 2factor.in, ~₹500/month) to intercept and auto-fill the OTP. Without it, Apna requires a one-time manual OTP entry per session (~24h session lifetime).

> **Application intake design:** Because all non-Indeed portals use the external `apply_url` with `?source=<portal>`, every application regardless of origin lands in the same FastAPI `/apply` endpoint. No portal-specific scraping required. This is fully legal and the cleanest possible design.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JD INGESTION LAYER                              │
│  Recruiter pastes raw JD text / uploads PDF                             │
│  → Claude API parses: title, skills, location, experience, salary       │
│  → Structured JD object stored in MongoDB                               │
│  → Unique apply_url generated: https://apply.fidelitus.com/apply?jd=ID  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
  ┌─────────────────┐ ┌──────────────┐  ┌────────────────────┐
  │  INDEED PUBLISHER│ │ UNIPILE/LI   │  │  EMAIL PUBLISHER   │
  │                 │ │              │  │                    │
  │ Auto-generates  │ │ Poll          │  │ Formats JD email   │
  │ XML feed entry  │ │ /jobs/{id}/  │  │ per portal with    │
  │ with postUrl=   │ │ applicants   │  │ apply_url embedded │
  │ our webhook     │ │ every 4h     │  │                    │
  │                 │ │ DM fallback  │  │ Recruiter receives │
  │ XML hosted at   │ │ → intake form│  │ → Ctrl+V posts     │
  │ /feed/indeed.xml│ │              │  │                    │
  └────────┬────────┘ └──────┬───────┘  └────────────────────┘
           │                 │
           ▼                 ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    CANDIDATE INTAKE LAYER                           │
  │                                                                     │
  │  Path A: Indeed Apply webhook POST → /webhook/indeed                │
  │  Path B: Intake web form → POST /apply (resume upload)             │
  │  Path C: Unipile applicant poll → normalized into same schema       │
  │  Path D: Apna CSV ingestion script → normalized into same schema    │
  │                                                                     │
  │  All paths → CandidateRecord in MongoDB                            │
  └────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    SCREENING LAYER                                  │
  │                                                                     │
  │  Claude API: resume text → structured fields + screening score      │
  │  Score 0-100 based on: skills match, experience, location          │
  │  Flag: shortlist / review / reject                                  │
  │  Auto-email to candidate: acknowledgement                          │
  │  Recruiter dashboard: sorted by score                              │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Module Breakdown

### Module 1: JD Parser (`src/jd_parser/`)
**Input:** Raw JD text (paste or PDF upload)  
**Output:** Structured JD object  

```python
# Fields extracted by Claude API:
{
  "jd_id": "uuid",
  "title": "Senior React Developer",
  "company": "Fidelitus Client",  # or "Confidential"
  "location": "Bengaluru, Karnataka",
  "work_mode": "hybrid",  # remote/hybrid/onsite
  "experience_min": 4,
  "experience_max": 8,
  "salary_min": 1200000,
  "salary_max": 1800000,
  "skills_required": ["React", "TypeScript", "Node.js"],
  "skills_preferred": ["GraphQL", "AWS"],
  "description_html": "<p>...</p>",
  "apply_url": "https://apply.fidelitus.com/apply?jd=abc123",
  "source_portals": ["indeed", "linkedin", "internshala"],
  "status": "active",
  "created_at": "2026-05-13T10:00:00Z"
}
```

Claude prompt template: `src/jd_parser/prompt.txt`

---

### Module 2: Indeed Publisher (`src/publisher/indeed.py`)

**Mechanism:** Direct employer XML feed (free, no ATS partner required).  

Indeed's XML feed integration works as follows:
- You host a publicly accessible XML file at a stable URL (e.g., `https://apply.fidelitus.com/feed/indeed.xml`)
- You register this URL once with Indeed via your employer dashboard
- Indeed polls the feed on a schedule and ingests job changes automatically
- Each job in the feed includes `<indeed-apply-postUrl>` pointing to your webhook
- When a candidate applies via "Easily Apply" on Indeed, Indeed POSTs the application JSON (including Base64-encoded resume) to your `postUrl`

**Registration steps (one-time, done by recruiter):**
1. Log into `employers.indeed.com`
2. Go to Settings → Job Feed → Register XML Feed URL
3. Provide: `https://apply.fidelitus.com/feed/indeed.xml`
4. Wait up to 5 business days for Indeed to review

**Feed auto-generation:** Each time a new JD is parsed and tagged for Indeed, the system regenerates `indeed.xml` with all active jobs and serves it at the registered URL.

**Application delivery:** Indeed POSTs to `/webhook/indeed` (per job's `postUrl` field). Resume is Base64-encoded in `applicant.file.data`.

---

### Module 3: Unipile / LinkedIn Pipeline (`src/candidate_pipeline/linkedin.py`)

**Mechanism:** Unipile session-based proxy of your connected LinkedIn account.

**What works without LinkedIn Recruiter seat:**
- `GET /api/v1/linkedin/jobs/{job_id}/applicants` — works if the job was posted from your connected LinkedIn Company Page account
- Returns: applicant name, LinkedIn profile URL, headline, profile data
- Resume file: only available if the candidate uploaded one (not just used their LinkedIn profile)

**Polling strategy:**
- Cron job every 4 hours: `GET /api/v1/linkedin/jobs` → for each job, get applicants → diff against known applicant IDs → process new ones
- For applicants without a resume file: auto-trigger Unipile DM via `POST /api/v1/linkedin/chats` with message: *"Hi [Name], thank you for your interest in [Role] at Fidelitus. To complete your application, please upload your resume here: [apply_url]"*

**LinkedIn job posting (manual path):**
- System generates a formatted LinkedIn post draft (not job listing — a post) with the JD summary and apply_url
- Recruiter copies and posts manually OR uses LinkedIn's web UI to create a job listing with the external apply URL

**Key constraint:** Unipile's scope is bounded by what the authenticated LinkedIn user session can see. Without a Recruiter seat, access to job applicant data depends on the job being posted under the connected Company Page.

---

### Module 4: Intake Web Form (`src/intake_form/`)

**Tech:** FastAPI + Jinja2 templates (or static HTML served by FastAPI)  
**URL pattern:** `https://apply.fidelitus.com/apply?jd=<jd_id>&source=<portal>`  

**Form fields:**
- Full Name (required)
- Email (required)
- Phone / WhatsApp number (required)
- Role applied for (pre-filled from `jd_id`, read-only)
- Current CTC (₹ LPA)
- Expected CTC (₹ LPA)
- Notice Period (dropdown: Immediate / 15 days / 30 days / 60 days / 90 days)
- Resume upload (PDF/DOCX, max 5MB, required)
- LinkedIn Profile URL (optional)
- Consent: "I agree to my data being processed by Fidelitus HR Services" (checkbox, required)
- Source tracked via `?source=` URL param (hidden field)

**Backend POST handler (`/apply`):**
1. Validate form fields
2. Store resume to `./uploads/{jd_id}/{timestamp}_{name}.pdf`
3. Extract text from resume (pdfminer / python-docx)
4. Create `CandidateRecord` in MongoDB
5. Trigger Claude API screening (async background task)
6. Return success page / JSON  
7. Send acknowledgement email to candidate via Gmail (SMTP or Gmail MCP)

---

### Module 5: Browser Automation Publisher (`src/publisher/browser_poster.py`)

**Primary posting mechanism for all non-API portals:** Internshala, Apna, Shine, WorkIndia, PlacementIndia, Glassdoor.

**Technology:** Playwright (async, Chromium). Uses your registered employer accounts on each portal. Posts real jobs with the `apply_url` set as the external apply link. Legal — identical to a human recruiter filling the form.

**Per-portal flow:**
1. Launch Chromium (headless in prod, headed during initial setup/debugging)
2. Log in using stored credentials from env vars
3. Navigate to "Post a Job" / "Add Listing"
4. Fill: title, description, location, salary, skills, employment type
5. Set external apply URL: `{apply_url}&source={portal_name}`
6. Submit and capture confirmation

**Portal-specific notes:**

| Portal | Login Method | External Apply Field | Notes |
|---|---|---|---|
| Internshala | Email + Password | `Apply URL` field on post form | Free: 1 post/month. Premium unlocks more. |
| Apna | Phone + OTP | `Apply Link` or job URL field | OTP: manual or MSG91/2factor.in gateway |
| Glassdoor | Email + Password | Routes through Indeed employer backend | Free posting |
| Shine | Email + Password | `Apply URL` on post form | 10 free posts/month |
| WorkIndia | Email + Password | External apply link field | Free unlimited |
| PlacementIndia | Email + Password | Apply URL field | 30 free posts/month |

**Trigger:** Called as a FastAPI background task via `POST /publish/browser` immediately after JD parsing.

**Resilience:** If a portal's UI changes and Playwright selectors break, the system automatically falls back to sending the recruiter an email with the formatted JD (Module 5b below). This means the pipeline never silently drops a posting.

---

### Module 5b: Email Fallback Publisher (`src/publisher/email_publisher.py`)

Fallback for when Playwright fails on a portal (UI change, CAPTCHA, account issue). Also used as the primary channel for LinkedIn (manual post).

**Output per portal:** Formatted email to recruiter with:
- Subject: `[Post Now] {title} on {portal_name} | JD-{jd_id}`
- Portal-specific step-by-step instructions
- Full formatted JD text ready to paste
- `apply_url` prominently highlighted
- Direct link to the portal's "Post a Job" page

Emails sent automatically when `browser_poster.py` raises an exception for a given portal.

---

### Module 6: Screening Engine (`src/candidate_pipeline/screener.py`)

**Claude API call per candidate:**

```
System: You are a recruitment screener for Fidelitus HR Services.
User: 
  JD: {structured_jd_json}
  Resume text: {extracted_resume_text}
  
  Return JSON:
  {
    "score": 0-100,
    "flag": "shortlist|review|reject",
    "skills_matched": [...],
    "skills_missing": [...],
    "experience_years": N,
    "summary": "2-sentence recruiter summary",
    "red_flags": [...]
  }
```

Results stored in `CandidateRecord.screening` in MongoDB.

---

### Module 7: Apna CSV Ingestion (`scripts/apna_ingest.py`)

Apna posting is handled by Playwright (Module 5). However, since Apna has no webhook for application delivery, a recruiter manually exports CSV from the Apna employer dashboard periodically and drops it into a watched folder. This script normalizes and ingests into MongoDB, deduplicates by email+jd_id, and triggers Claude screening for new records.

Note: Because all Apna job posts include the external `apply_url`, most serious candidates will apply via your intake form directly. The CSV ingestion catches the remainder who apply natively within Apna.

---

## 6. Data Models (MongoDB)

### Collection: `jobs`
```json
{
  "_id": "ObjectId",
  "jd_id": "uuid string",
  "title": "string",
  "company": "string",
  "location": "string",
  "work_mode": "remote|hybrid|onsite",
  "experience_min": "int",
  "experience_max": "int",
  "salary_min": "int",
  "salary_max": "int",
  "skills_required": ["array"],
  "skills_preferred": ["array"],
  "description_html": "string",
  "apply_url": "string",
  "source_portals": ["indeed", "linkedin", "internshala", ...],
  "indeed_posting_id": "string|null",
  "linkedin_job_id": "string|null",
  "status": "active|closed|draft",
  "created_at": "datetime",
  "closed_at": "datetime|null"
}
```

### Collection: `candidates`
```json
{
  "_id": "ObjectId",
  "jd_id": "string (ref jobs.jd_id)",
  "source": "indeed|linkedin|internshala|apna|shine|workindia|placementindia|glassdoor|direct",
  "name": "string",
  "email": "string",
  "phone": "string",
  "linkedin_url": "string|null",
  "resume_path": "string (local path or S3 key)",
  "resume_text": "string",
  "current_ctc": "float|null",
  "expected_ctc": "float|null",
  "notice_period": "string|null",
  "screening": {
    "score": "int",
    "flag": "shortlist|review|reject",
    "skills_matched": ["array"],
    "skills_missing": ["array"],
    "experience_years": "int",
    "summary": "string",
    "red_flags": ["array"],
    "screened_at": "datetime"
  },
  "dm_sent": "bool (linkedin DM fallback)",
  "dm_sent_at": "datetime|null",
  "acknowledged": "bool",
  "created_at": "datetime",
  "raw_payload": "object (original webhook/form payload)"
}
```

---

## 7. API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/jd/parse` | Parse raw JD text → structured JD, store, generate apply_url, trigger all publishers |
| GET | `/jd/{jd_id}` | Get JD details |
| GET | `/jd/{jd_id}/close` | Close/expire a job |
| GET | `/feed/indeed.xml` | Serve live Indeed XML feed (all active jobs) |
| POST | `/webhook/indeed` | Indeed Apply delivery endpoint (receives Base64 resume + applicant JSON) |
| GET | `/apply` | Serve intake form HTML (pre-filled from `?jd=` param) |
| POST | `/apply` | Intake form submission — stores resume, triggers screening |
| GET | `/candidates` | List candidates (filter by jd_id, flag, source, min_score) |
| GET | `/candidates/{id}` | Get single candidate record |
| POST | `/candidates/{id}/screen` | Re-trigger Claude screening |
| POST | `/publish/browser` | **Playwright auto-post** to specified non-API portals |
| POST | `/publish/email` | Email fallback — send formatted JD to recruiter for manual posting |
| POST | `/publish/email/all-active` | Re-send email for all active jobs |
| POST | `/jobs/linkedin/poll` | Trigger manual Unipile LinkedIn applicant poll |
| POST | `/ingest/apna-csv` | Ingest Apna CSV export into MongoDB |

---

## 8. Environment Variables

```env
# App
APP_BASE_URL=https://apply.fidelituscorp.com
PORT=8000

# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=fidelitus_ats

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Unipile
UNIPILE_API_KEY=...
UNIPILE_DSN=https://api1.unipile.com:13111
UNIPILE_LINKEDIN_ACCOUNT_ID=...

# Indeed
INDEED_APPLY_TOKEN=...   # From Indeed employer dashboard → App Credentials

# Email (recruiter notifications + candidate acknowledgement)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=hr@fidelituscorp.com
SMTP_PASSWORD=...
RECRUITER_EMAIL=recruiter@fidelituscorp.com
RECRUITER_NAME=Hiring Team

# Storage
RESUME_UPLOAD_DIR=./uploads

# ── Portal Credentials (Playwright browser automation) ─────────────────────
INTERNSHALA_EMAIL=hr@fidelituscorp.com
INTERNSHALA_PASSWORD=...

APNA_PHONE=+919876543210
# Optional: MSG91 or 2factor.in for OTP automation
# APNA_OTP_API_KEY=...

GLASSDOOR_EMAIL=hr@fidelituscorp.com
GLASSDOOR_PASSWORD=...

SHINE_EMAIL=hr@fidelituscorp.com
SHINE_PASSWORD=...

WORKINDIA_EMAIL=hr@fidelituscorp.com
WORKINDIA_PASSWORD=...

PLACEMENTINDIA_EMAIL=hr@fidelituscorp.com
PLACEMENTINDIA_PASSWORD=...

# Playwright mode: false = headed (for debugging), true = headless (production)
PLAYWRIGHT_HEADLESS=true
```

---

## 9. Phased Delivery Plan

### Phase 1 — Core (2 weeks)
- [ ] JD Parser (Claude API)
- [ ] MongoDB schema + connection + indexes
- [ ] Intake form (FastAPI + HTML)
- [ ] Indeed XML feed generator + webhook receiver
- [ ] Candidate record creation + resume extraction
- [ ] Claude screening engine

### Phase 2 — Distribution (1 week)
- [ ] Playwright browser poster (`browser_poster.py`) — Internshala, Glassdoor, Shine, WorkIndia, PlacementIndia
- [ ] Playwright Apna poster (manual OTP initially; MSG91 integration optional)
- [ ] Email fallback publisher (triggers automatically if Playwright fails)
- [ ] Unipile LinkedIn applicant poller + DM fallback

### Phase 3 — Automation (1 week)
- [ ] Apna CSV ingestion script
- [ ] Playwright selector maintenance (run headed, fix broken selectors after portal UI changes)
- [ ] Recruiter dashboard (HTML table, sortable by score/source/flag)
- [ ] Candidate acknowledgement emails

### Phase 4 — Hardening
- [ ] API key auth on all endpoints
- [ ] Rate limiting
- [ ] Webhook failure alerting
- [ ] DPDP consent logging
- [ ] Playwright retry logic + screenshot on failure for debugging

---

## 10. Key Decisions & Rationale

| Decision | Rationale |
|---|---|
| Indeed XML feed (not Job Sync API) | Job Sync API is ATS-partner only. Direct employer XML feed is free, works for agencies, and activates Indeed Apply webhook with Base64 resume delivery. |
| LinkedIn: manual post + Unipile poll + DM fallback | LinkedIn Talent Solutions Partner API requires enterprise approval. Unipile session-level access is sufficient for polling applicants. Manual post takes 2 minutes. |
| Playwright browser automation for non-API portals | No Indian portal (Internshala, Apna, Shine, WorkIndia, PlacementIndia, Glassdoor) exposes a public job posting API. Playwright using your own registered employer accounts is legal, widely used in HR-tech, and identical to a human filling the form. |
| External `apply_url` on every portal | Inserting your intake form URL as the apply link on all non-Indeed portals means every application regardless of source lands in your pipeline without scraping. Clean, legal, and portal-agnostic. |
| Email publisher as Playwright fallback | Portal UIs change. When Playwright selectors break, the email fallback ensures the recruiter can still post within hours. Prevents silent failures. |
| Intake form as primary resume collection | Guarantees a PDF resume file from every candidate regardless of portal. Portal native resume access is paywalled or nonexistent across Indian portals. |
| Claude API for parsing + screening | Already in stack. No separate resume parser needed. Handles Indian resume formats and regional language nuances better than off-the-shelf parsers. |
| MongoDB | Flexible schema for varying application payloads per portal. Already in Fidelitus tech stack. |
