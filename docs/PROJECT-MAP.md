# JobOS — Complete Project File Map

Generated: 2026-04-28

---

## Project Overview

JobOS is an AI-powered **Recruitment Operating System** built for staffing agencies and internal HR teams. It automates the end-to-end hiring pipeline:

1. **JD Intake** — Receives job descriptions via email (IMAP) or web form upload
2. **AI Structuring** — Extracts structured fields from raw JD text using Groq LLM
3. **Resume Ingestion** — Accepts PDF/DOCX resumes from web upload or email attachments
4. **Two-Pass Matching Engine**
   - Pass 1 (Speed Layer): Cosine similarity via Qdrant vector search
   - Pass 2 (Intelligence Layer): Deep reasoning via Groq llama-3.3-70b
5. **Contextual Scoring** — Bonus scoring for company type, team size, and role type alignment
6. **Notifications** — Email + in-app alerts to managers/HoDs when a candidate pool is ready
7. **Recruiter Dashboard** — React UI for reviewing stack-ranked candidates with shortlist/reject actions

**Tech stack:** Python 3.11, FastAPI, Celery, MongoDB, Qdrant, Redis, Keycloak, React + Vite + Tailwind, Docker Compose, Groq API, sentence-transformers (all-MiniLM-L6-v2).

---

## Directory Structure

```
jobos/
├── .env                          # All secrets and service URLs (never committed)
├── CLAUDE.md                     # AI assistant project instructions
├── PRD.md                        # Product Requirements Document
├── docker-compose.yml            # Orchestrates all 12 services
├── config/
│   └── config.yaml               # Matching thresholds and sourcing config
├── nginx/
│   └── nginx.conf                # Reverse proxy: routes / to frontend, /api to backend
│
├── api/                          # FastAPI backend + Celery worker
│   ├── Dockerfile                # Builds the api and worker containers
│   ├── requirements.txt          # All Python dependencies
│   ├── main.py                   # FastAPI app: registers routers, CORS
│   ├── auth.py                   # Keycloak JWT verification, role checking
│   ├── celery_app.py             # Celery instance with Redis broker
│   ├── celerybeat-schedule       # Celery Beat scheduler state (auto-generated)
│   │
│   ├── routers/
│   │   ├── auth.py               # GET /auth/me — upserts user on login
│   │   ├── jd.py                 # POST /jd/upload, /jd/create, GET /jd/
│   │   ├── candidates.py         # POST /candidates/upload-resume, /email-intake, GET /candidates/
│   │   ├── matching.py           # POST /matching/run/{jd_id}, GET /matching/results/{jd_id}
│   │   ├── notifications.py      # GET /notifications/, PUT /notifications/read-all
│   │   ├── pipeline.py           # GET /pipeline/status (stub)
│   │   ├── documents.py          # GET /documents/vault (stub)
│   │   ├── crm.py                # GET /crm/messages (stub)
│   │   └── analytics.py          # GET /analytics/dashboard (stub)
│   │
│   ├── tasks/
│   │   ├── jd_tasks.py           # Celery task: extract, embed, upsert JD to Qdrant
│   │   ├── resume_tasks.py       # Celery task: extract text, embed, upsert resume
│   │   ├── matching_tasks.py     # Celery tasks: Pass 1 (cosine), Pass 2 (Groq reasoning)
│   │   └── notification_tasks.py # Celery task: email + in-app notify managers/HoDs
│   │
│   ├── utils/
│   │   ├── client_utils.py       # MongoDB connection, find-or-create client by email domain
│   │   ├── config_utils.py       # Reads config.yaml, exposes matching thresholds
│   │   ├── email_utils.py        # SMTP send_email helper
│   │   ├── gemini_utils.py       # All Groq LLM calls + local embedding model
│   │   ├── jd_utils.py           # generate_jd_id() — date + uuid8 format
│   │   ├── pydantic_utils.py     # PyObjectId type for Pydantic/MongoDB ObjectId bridge
│   │   ├── qdrant_utils.py       # Qdrant client, upsert/search/get for JD+resume vectors
│   │   ├── resume_utils.py       # PDF/DOCX text extraction via pdfplumber + python-docx
│   │   └── storage_utils.py      # File system: JD folder structure, resume versioning, match JSON
│   │
│   ├── scripts/
│   │   ├── seed_db.py            # Bootstrap: creates all MongoDB collections + Qdrant collections
│   │   ├── seed_users.py         # Inserts manager/hod/admin users into users collection
│   │   ├── update_users.py       # Replaces users collection with specific test users
│   │   ├── fix_mongodb_indexes.py# Drops and recreates correct compound indexes
│   │   ├── reingest_samples.py   # Bulk-triggers resume ingestion from /data/samples/
│   │   ├── recreate_collections.py # Drops + rebuilds Qdrant collections, re-embeds all data
│   │   ├── migrate_contextual_fields.py    # Re-extracts company_types/avg_team_size/role_type for candidates
│   │   ├── migrate_jd_contextual_fields.py # Adds contextual preference defaults to JD records
│   │   ├── sync_qdrant_payloads.py         # Syncs all candidate fields from MongoDB → Qdrant (no re-embed)
│   │   └── sync_jd_qdrant_payloads.py      # Syncs all JD fields from MongoDB → Qdrant (no re-embed)
│   │
│   ├── email_watcher/
│   │   ├── Dockerfile            # Separate container for the IMAP polling loop
│   │   ├── requirements.txt      # Minimal: requests, python-dotenv
│   │   └── main.py               # Polls Gmail INBOX, extracts resume attachments, calls /candidates/email-intake
│   │
│   └── tests/                    # Pytest tests (inside api container)
│
├── frontend/                     # React + Vite + Tailwind PWA
│   ├── Dockerfile                # Runs vite dev server in container
│   ├── .dockerignore
│   ├── index.html                # Vite entry point
│   ├── package.json              # Dependencies: React 18, keycloak-js, lucide-react, axios, tailwind
│   ├── tailwind.config.js        # Tailwind configuration
│   ├── postcss.config.js         # PostCSS for Tailwind
│   └── src/
│       ├── main.tsx              # ReactDOM.render entry point
│       ├── App.tsx               # Root component: Keycloak init + React Router
│       ├── keycloak.ts           # Keycloak-js singleton instance
│       ├── index.css             # Global styles including custom-scrollbar
│       ├── components/
│       │   └── Layout.tsx        # Sidebar nav, header, notification bell, role-based menu
│       ├── pages/
│       │   ├── Dashboard.tsx     # Role-aware: RecruiterDashboard for staff, profile editor for candidates
│       │   ├── RecruiterDashboard.tsx # Batch-mode candidate review with contextual match analysis
│       │   ├── Jobs.tsx          # JD upload (file or structured form) and JD list
│       │   ├── Candidates.tsx    # Resume upload and candidate list
│       │   ├── Matching.tsx      # Trigger matching, view ranked results with expand/collapse
│       │   ├── Analytics.tsx     # Analytics stub
│       │   ├── CRM.tsx           # CRM stub
│       │   └── Documents.tsx     # Document vault stub
│       └── utils/
│           ├── api.ts            # API base URL, auth headers, fetch wrappers, TypeScript interfaces
│           └── badges.tsx        # Recommendation badge component (shortlist/hold/reject)
│
├── naukri-sourcer/
│   ├── Dockerfile
│   └── main.py                   # Stub: future Naukri portal scraping service
│
├── data/                         # Runtime data (gitignored except match output)
│   ├── clients/
│   │   └── <client-slug>/
│   │       └── <JD-ID>/
│   │           ├── raw/          # Original uploaded file (email_body.txt / .pdf / .docx)
│   │           ├── jd.json       # Extracted structured JD data
│   │           ├── internal.md   # Internal format with salary and full details
│   │           ├── short.md      # Recruiter-facing summary
│   │           ├── candidate.md  # Candidate-facing description
│   │           └── candidates/
│   │               └── <CAN-ID>/
│   │                   ├── match_score.json  # Pass 2 evaluation result
│   │                   └── pointer.json      # Candidate file path pointer
│   ├── resumes/
│   │   ├── <CAN-ID>/
│   │   │   └── <CAN-ID>_v1.pdf  # Versioned resume file
│   │   └── intake/               # Temporary landing zone for email watcher attachments
│   └── samples/                  # Sample resumes for bulk re-ingestion testing
│
├── sampleresumes/                # Local copy of sample resumes (pre-mount)
├── tasks/                        # Feature specification markdown files (TASK-XXX)
└── tests/                        # Root-level Pytest tests
    ├── test_matching_pass1.py
    └── test_tasks_1_to_6.py
```

---

## File-by-File Explanation

---

### Root Level

#### `.env`
- **What:** Environment variable file with all secrets and service connection strings
- **Why:** Single source of truth for all configuration that must not be hardcoded; loaded by Docker Compose into every container via `env_file: .env`
- **Solves:** Prevents credentials from leaking into source code; centralizes config for local dev
- **Depends on:** Nothing
- **Used by:** docker-compose.yml (loads into api, worker, scheduler, email-watcher containers); all Python files that call `os.getenv()`
- **Key vars:** `GROQ_API_KEY`, `MONGO_URI`, `REDIS_URL`, `QDRANT_HOST/PORT`, `KEYCLOAK_*`, `SMTP_*`, `EMAIL_IMAP_*`, `INTERNAL_API_KEY`

#### `docker-compose.yml`
- **What:** Defines and orchestrates all 12 Docker services as a single stack
- **Why:** Eliminates "works on my machine" by pinning service versions and wiring network aliases; one `docker-compose up` starts the entire system
- **Solves:** Service discovery (containers address each other by name: `mongodb`, `redis`, `qdrant`, `api`), volume persistence, port exposure
- **Depends on:** `./api/Dockerfile`, `./frontend/Dockerfile`, `./api/email_watcher/Dockerfile`, `./naukri-sourcer/Dockerfile`, `.env`
- **Services defined:**
  | Service | Image/Build | Purpose |
  |---------|-------------|---------|
  | mongodb | mongo:6.0 | Primary database |
  | qdrant | qdrant/qdrant:v1.7.0 | Vector database |
  | redis | redis:7.2-alpine | Celery broker + result backend |
  | postgres-keycloak | postgres:15 | Keycloak's internal store |
  | keycloak | quay.io/keycloak/keycloak:23.0 | Auth / SSO server |
  | api | ./api | FastAPI server (uvicorn) |
  | worker | ./api | Celery task consumer |
  | scheduler | ./api | Celery Beat periodic scheduler |
  | flower | mher/flower:1.2 | Celery task monitor UI |
  | frontend | ./frontend | Vite dev server |
  | email-watcher | ./api/email_watcher | IMAP polling loop |
  | nginx | nginx:alpine | Reverse proxy on port 80 |

#### `CLAUDE.md`
- **What:** Project-specific instructions for the Claude Code AI assistant
- **Why:** Defines module boundaries, tech stack, current task, and coding conventions so the AI operates within the project's architecture
- **Solves:** Keeps AI context consistent across sessions; prevents accidental cross-module edits
- **Depends on / Used by:** Read by Claude at the start of every session

#### `PRD.md`
- **What:** Product Requirements Document — defines what JobOS must do, for whom, and why
- **Why:** Single canonical spec; referenced when deciding what to build in each TASK
- **Depends on / Used by:** tasks/TASK-XXX.md files reference it for scope

#### `config/config.yaml`
- **What:** Runtime configuration for matching thresholds and sourcing behavior
- **Why:** Separates tunable parameters from code; change thresholds without rebuilding the container
- **Solves:** `p_threshold` (minimum cosine similarity to include a candidate), `k_threshold` (minimum pool size before triggering external sourcing)
- **Key values:** `p_threshold: 0.15`, `k_threshold: 10`, `batch_size: 3`
- **Depends on:** Nothing
- **Used by:** `api/utils/config_utils.py` → `matching_tasks.py`

#### `nginx/nginx.conf`
- **What:** Nginx reverse proxy configuration
- **Why:** Provides a single entry point on port 80; routes `/` to frontend Vite server and `/api` to the FastAPI backend
- **Solves:** Eliminates CORS issues in production; handles WebSocket upgrade headers for Vite HMR
- **Depends on:** frontend container (port 5173), api container (port 8000)
- **Used by:** nginx Docker service

---

### `/api` — FastAPI Backend

#### `api/Dockerfile`
- **What:** Multi-purpose Docker image for `api`, `worker`, and `scheduler` containers
- **Why:** All three services share the same codebase; only the CMD differs (uvicorn vs celery worker vs celery beat)
- **Solves:** Pre-bakes the `all-MiniLM-L6-v2` sentence-transformers model into the image so it works offline inside the container without downloading at runtime
- **Key steps:** python:3.11-slim → install build-essential → pip install requirements → pre-download embedding model → COPY code → CMD uvicorn
- **Depends on:** `requirements.txt`
- **Used by:** docker-compose.yml (api, worker, scheduler services)

#### `api/requirements.txt`
- **What:** Python package manifest for the API container
- **Why:** Pins exact versions to prevent dependency drift between developers and CI
- **Key packages:**
  | Package | Role |
  |---------|------|
  | fastapi==0.109.0 | HTTP framework |
  | uvicorn==0.27.0 | ASGI server |
  | pymongo==4.6.1 | MongoDB driver |
  | celery==5.3.6 | Async task queue |
  | qdrant-client==1.13.2 | Vector DB client |
  | groq>=0.9.0 | Groq LLM API client |
  | sentence-transformers==3.0.1 | Local embedding model |
  | pdfplumber==0.10.3 | PDF text extraction |
  | python-docx==1.1.0 | DOCX text extraction |
  | python-jose[cryptography]==3.3.0 | JWT validation |
  | python-slugify==8.0.4 | Client email→slug |
  | httpx==0.26.0 | Async HTTP for Keycloak JWKS fetch |

#### `api/main.py`
- **What:** FastAPI application factory — registers all routers and CORS middleware
- **Why:** Central mount point; keeps router registration separate from router logic
- **Solves:** CORS allow-all for local dev; exposes `/health` for Docker health checks
- **Depends on:** `celery_app.py`, all router modules in `routers/`
- **Used by:** Uvicorn CMD (`uvicorn main:app`); `celery_app.py` uses `main.celery` reference in worker command

#### `api/auth.py`
- **What:** Keycloak JWT authentication and role-based access control dependency
- **Why:** Centralizes all auth logic; every protected endpoint imports `check_role()` or `get_current_user()`
- **Solves:** Fetches Keycloak's JWKS public keys at runtime (no hardcoded certs), validates RS256 tokens, extracts realm roles and client roles
- **Key functions:**
  - `get_current_user()` — validates token, returns decoded payload
  - `check_role(roles)` — returns a FastAPI Depends factory that enforces role membership
- **Depends on:** `httpx` (for JWKS fetch), `python-jose` (JWT decode), Keycloak container
- **Used by:** Every router via `Depends(check_role([...]))`

#### `api/celery_app.py`
- **What:** Celery application singleton with Redis as both broker and result backend
- **Why:** Separates the Celery config from task definitions; `main.py` imports it so the worker command `celery -A main.celery` resolves correctly
- **Solves:** Task serialization (JSON), timezone (UTC), includes all task modules so workers discover them automatically
- **Depends on:** Redis (from `.env`), all `tasks/` modules
- **Used by:** `main.py`, all `tasks/` modules (`from celery_app import celery`)

---

### `/api/routers`

#### `api/routers/auth.py`
- **What:** `GET /auth/me` — returns current user profile and upserts into MongoDB `users` collection
- **Why:** Ensures every user who logs in has a record in the database (enables notification targeting); also returns full JWT payload for frontend role detection
- **Solves:** The users collection is the source of truth for notification recipients; this endpoint populates it on login
- **Depends on:** `auth.get_current_user`, `utils/client_utils.get_db`
- **Used by:** Frontend `App.tsx` (called after Keycloak auth to verify token)

#### `api/routers/jd.py`
- **What:** JD ingestion router — `POST /jd/upload` (file), `POST /jd/create` (structured form), `GET /jd/`
- **Why:** Two intake paths: raw file (triggers AI extraction) and structured form (skips extraction, goes straight to embedding). Both ultimately call `process_jd_task`
- **Solves:** Client identity is derived from the email domain (e.g., `@fidelitus.com` → client slug `fidelitus`); folder structure is created on disk at intake time
- **Depends on:** `auth.check_role`, `utils/client_utils`, `utils/jd_utils`, `utils/storage_utils`, `tasks/jd_tasks`
- **Used by:** Frontend `Jobs.tsx`

#### `api/routers/candidates.py`
- **What:** Resume ingestion router — `POST /candidates/upload-resume` (web), `POST /candidates/email-intake` (email watcher), `GET /candidates/`, `GET/PUT /candidates/me`
- **Why:** Two intake paths: web upload (synchronous processing) and email intake (triggered by email watcher service)
- **Solves:**
  - Deduplication: if a resume's email already exists in DB, updates the existing record rather than creating a duplicate
  - Internal email generation: candidates without email in their resume get `<candidate_id>@jobos.internal`
  - Internal API key auth: `email-intake` accepts either a Keycloak bearer token OR an `X-Internal-Key` header so the email watcher can call it without Keycloak credentials
- **Key mechanism — `_internal_or_auth`:** `HTTPBearer(auto_error=False)` allows the endpoint to check for internal key first, then fall back to Keycloak auth
- **Depends on:** `auth`, `utils/storage_utils`, `utils/gemini_utils`, `utils/qdrant_utils`, `utils/resume_utils`, `tasks/matching_tasks`, `tasks/notification_tasks`
- **Used by:** Frontend `Candidates.tsx`; `api/email_watcher/main.py`

#### `api/routers/matching.py`
- **What:** Matching control and results router
- **Why:** Provides endpoints to trigger matching and retrieve ranked results enriched with both candidate and JD contextual fields
- **Endpoints:**
  - `POST /matching/run/{jd_id}` — triggers Pass 1 + Pass 2 as Celery tasks
  - `POST /matching/pass2/{jd_id}` — triggers only Pass 2 on existing Pass 1 results
  - `GET /matching/results/{jd_id}` — returns ranked pool with candidate contextual data and JD preferences merged in
  - `POST /matching/action/{jd_id}/{candidate_id}` — records shortlist/reject decision
  - `GET /matching/pipeline-stats/{jd_id}` — counts shortlisted/rejected/pending
- **Solves:** The results endpoint reads JD preferences from `structured_data` (nested sub-document in MongoDB) and merges them with candidate fields so the frontend has everything it needs in one response
- **Depends on:** `auth.check_role`, `tasks/matching_tasks`, `utils/client_utils`
- **Used by:** Frontend `Matching.tsx`, `RecruiterDashboard.tsx`

#### `api/routers/notifications.py`
- **What:** Notification inbox router — `GET /notifications/`, `GET /notifications/unread-count`, `PUT /notifications/read-all`, `PUT /notifications/{id}/read`
- **Why:** Provides the in-app notification feed shown in the header bell; notifications are created by `notification_tasks.py` when Pass 2 completes
- **Depends on:** `auth.get_current_user`, `utils/client_utils`
- **Used by:** Frontend `Layout.tsx` (bell icon, dropdown, 30-second polling)

#### `api/routers/pipeline.py`
- **What:** `GET /pipeline/status` stub — placeholder for future pipeline monitoring
- **Why:** Reserves the route namespace; will expose batch progress and stage tracking when TASK-013 is implemented
- **Depends on:** `auth.check_role`

#### `api/routers/documents.py`
- **What:** `GET /documents/vault` stub — placeholder for tiered document storage (TASK-017)
- **Why:** Reserves the route; will serve candidate documents, offer letters, agreements
- **Depends on:** `auth.check_role`

#### `api/routers/crm.py`
- **What:** `GET /crm/messages` stub — placeholder for candidate communications (TASK-019)
- **Why:** Reserves the route; will expose drafted and approved outreach messages
- **Depends on:** `auth.check_role`

#### `api/routers/analytics.py`
- **What:** `GET /analytics/dashboard` stub — placeholder for metrics (TASK-023)
- **Why:** Reserves the route; will serve placement rates, time-to-fill, funnel metrics
- **Depends on:** `auth.check_role`

---

### `/api/tasks`

#### `api/tasks/jd_tasks.py`
- **What:** Celery task `process_jd_task` — the full JD processing pipeline
- **Why:** Runs asynchronously so the API doesn't block on LLM calls during JD upload
- **Pipeline:**
  1. Reads raw file from disk (email_body.txt, PDF, or DOCX)
  2. Calls `extract_jd_data()` (Groq fast model) → structured JSON
  3. Saves `jd.json` to disk
  4. Calls `generate_jd_formats()` → writes `internal.md`, `short.md`, `candidate.md`
  5. Calls `generate_embedding()` → 384-dim vector
  6. Upserts vector + payload to Qdrant `jd_vectors` collection
  7. Updates MongoDB status to `structured`
  8. Triggers `run_matching` for the new JD
- **Also contains:** `backfill_jd_vectors` — re-upserts all existing JD vectors with full payload schema (useful after adding new payload fields)
- **Depends on:** `celery_app`, `utils/client_utils`, `utils/gemini_utils`, `utils/qdrant_utils`, `utils/resume_utils`, `utils/storage_utils`
- **Used by:** `routers/jd.py` (`.delay()` call); `matching_tasks.py` (chained after JD processing)

#### `api/tasks/resume_tasks.py`
- **What:** Celery task `process_resume_task` — async resume processing (used by reingest script)
- **Why:** Offloads text extraction and embedding generation from the web upload path when called from scripts
- **Pipeline:** extract text → extract metadata via Groq → generate embedding → upsert to MongoDB + Qdrant
- **Note:** For web upload, `routers/candidates.py` does this synchronously; `process_resume_task` is primarily used by `reingest_samples.py`
- **Depends on:** `celery_app`, `utils/gemini_utils`, `utils/qdrant_utils`, `utils/resume_utils`, `utils/client_utils`

#### `api/tasks/matching_tasks.py`
- **What:** Two Celery tasks — `run_matching` (Pass 1) and `run_pass_2` (Pass 2)
- **Why:** Matching is compute-intensive and must not block the API; Celery ensures it runs in the worker container
- **Pass 1 — `run_matching`:**
  1. Fetches JD vector from Qdrant
  2. Searches `resume_vectors` for top 50 by cosine similarity
  3. Filters by `p_threshold` (default 0.15)
  4. Saves top 20 matches to `candidate_pools` collection
  5. If pool < `k_threshold`, flags JD for external sourcing
  6. Triggers `run_pass_2`
- **Pass 2 — `run_pass_2`:**
  1. Fetches JD structured data from MongoDB
  2. For each of top 20 Pass 1 candidates, calls `evaluate_candidate_fitment()` (Groq 70b)
  3. Calculates composite score: `(fitment × 0.65) + (cosine × 0.2) + (completeness × 0.1) + (context_bonus × 0.05)`
  4. Updates `candidate_pools` with fitment, strengths (5), gaps (5), recommendation
  5. Re-ranks all candidates by composite score
  6. Writes `match_score.json` + `pointer.json` to filesystem
  7. Triggers `notify_pool_ready`
- **Depends on:** `celery_app`, `utils/qdrant_utils`, `utils/config_utils`, `utils/gemini_utils`, `utils/storage_utils`, `utils/client_utils`
- **Used by:** `routers/matching.py` (trigger endpoints); `tasks/jd_tasks.py` (auto-triggered after JD processing)

#### `api/tasks/notification_tasks.py`
- **What:** Celery task `notify_pool_ready` — sends email + creates in-app notifications for managers/HoDs
- **Why:** Decouples notification delivery from matching logic; if email fails, in-app notification still works
- **What it does:**
  1. Looks up all users with role `manager` or `hod` in MongoDB `users` collection
  2. Builds a rich HTML email with a stack-ranked candidate table (dark theme)
  3. Sends email via SMTP using `email_utils.send_email()`
  4. Inserts notification documents into `notifications` collection (for in-app bell)
- **Depends on:** `celery_app`, `utils/client_utils`, `utils/email_utils`
- **Used by:** `tasks/matching_tasks.run_pass_2` (chained automatically after Pass 2 completes)

---

### `/api/utils`

#### `api/utils/client_utils.py`
- **What:** MongoDB connection factory + `find_or_create_client()` function
- **Why:** Centralizes MongoDB connection; all routers and tasks call `get_db()` rather than managing their own `MongoClient` instances
- **Solves:** Client identity — extracts domain from uploader email (e.g., `@fidelitus.com` → slug `fidelitus`), creates client record if first time seen
- **Depends on:** `pymongo`, `python-slugify`
- **Used by:** Every router, every task, every script that touches MongoDB

#### `api/utils/config_utils.py`
- **What:** YAML config loader with fallback path resolution
- **Why:** `config.yaml` is mounted at `/config/config.yaml` in Docker but may be at a relative path in local dev; tries multiple paths
- **Exposes:** `get_matching_thresholds()` → `(p_threshold, k_threshold)` tuple
- **Depends on:** `pyyaml`, `config/config.yaml`
- **Used by:** `tasks/matching_tasks.py`

#### `api/utils/email_utils.py`
- **What:** SMTP email sender with Gmail App Password support
- **Why:** Wraps smtplib with TLS upgrade, graceful failure (returns False instead of crashing if credentials missing)
- **Depends on:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` from `.env`
- **Used by:** `tasks/notification_tasks.py`

#### `api/utils/gemini_utils.py`
- **What:** All AI model interactions — both the local embedding model and Groq LLM calls
- **Why:** Central AI layer; all other modules import from here, making it easy to swap models
- **Key functions:**
  | Function | Model | Purpose |
  |----------|-------|---------|
  | `generate_embedding(text)` | all-MiniLM-L6-v2 (local) | 384-dim dense vector for semantic search |
  | `extract_jd_data(raw_text)` | llama-3.1-8b-instant | Extracts 16 structured fields from JD |
  | `generate_jd_formats(data)` | llama-3.1-8b-instant | Generates internal/short/candidate markdown |
  | `extract_resume_metadata(raw_text)` | llama-3.1-8b-instant | Extracts 18 fields from resume; regex fallback |
  | `evaluate_candidate_fitment(jd, resume)` | llama-3.3-70b-versatile | Deep evaluation: fitment 0-100, 5 strengths, 5 gaps, recommendation, context_bonus 0-15 |
- **Solves:** HuggingFace offline mode (sets env vars before any imports to prevent network calls); `_parse_json_response` strips markdown fences from LLM output before JSON parsing
- **Depends on:** `groq`, `sentence-transformers`, `GROQ_API_KEY` from `.env`
- **Used by:** `tasks/jd_tasks.py`, `tasks/resume_tasks.py`, `tasks/matching_tasks.py`, `routers/candidates.py`, `scripts/migrate_contextual_fields.py`

#### `api/utils/jd_utils.py`
- **What:** JD ID generator
- **Why:** Centralizes the ID format `JD-YYYYMMDD-{uuid8}` so it's consistent wherever JDs are created
- **Depends on:** `uuid`, `datetime`
- **Used by:** `routers/jd.py`

#### `api/utils/pydantic_utils.py`
- **What:** `PyObjectId` — a Pydantic type annotation that converts between MongoDB `ObjectId` and JSON-serializable strings
- **Why:** FastAPI/Pydantic can't serialize `ObjectId` natively; this type bridges MongoDB documents to API responses
- **Depends on:** `bson`, `pydantic`
- **Used by:** `routers/jd.py` (JDResponse model)

#### `api/utils/qdrant_utils.py`
- **What:** Qdrant vector database client wrapper
- **Why:** Abstracts all Qdrant operations; collections are auto-created on import via `init_qdrant()`
- **Key details:**
  - Point IDs are `uuid5(NAMESPACE_DNS, jd_id/candidate_id)` — deterministic, collision-free, reproducible
  - Collections: `jd_vectors` (384-dim, cosine) and `resume_vectors` (384-dim, cosine)
  - `search_resumes_by_vector()` returns top-N candidates ordered by cosine similarity
- **Depends on:** `qdrant-client==1.13.2`, `QDRANT_HOST/PORT` from `.env`
- **Used by:** `tasks/jd_tasks.py`, `tasks/resume_tasks.py`, `tasks/matching_tasks.py`, `routers/candidates.py`, all sync scripts

#### `api/utils/resume_utils.py`
- **What:** PDF and DOCX text extraction
- **Why:** Centralizes file parsing; both PDF (pdfplumber) and DOCX (python-docx) are supported
- **Depends on:** `pdfplumber`, `python-docx`
- **Used by:** `tasks/jd_tasks.py`, `tasks/resume_tasks.py`, `routers/candidates.py`, `scripts/recreate_collections.py`, `scripts/migrate_contextual_fields.py`

#### `api/utils/storage_utils.py`
- **What:** All filesystem I/O for JD folders, resume files, and match result JSON
- **Why:** Centralizes the on-disk folder convention so all services write to the same structure
- **Key functions:**
  - `create_jd_folder_structure(client_slug, jd_id)` → creates `/data/clients/<slug>/<JD-ID>/raw/` and `/candidates/`
  - `save_resume_file(candidate_id, filename, content)` → saves with version suffix `_v1.pdf`, `_v2.pdf` etc.
  - `save_candidate_match_results(...)` → writes `match_score.json` + `pointer.json`; uses custom `_default` serializer to handle `datetime` objects
- **Depends on:** `os`, `json`, `datetime`
- **Used by:** `routers/jd.py`, `routers/candidates.py`, `tasks/matching_tasks.py`, `scripts/reingest_samples.py`

---

### `/api/email_watcher`

#### `api/email_watcher/Dockerfile`
- **What:** Minimal Python image for the IMAP polling loop
- **Why:** Separate from the main API image; doesn't need FastAPI, Celery, or ML dependencies — only `requests` and `python-dotenv`
- **Depends on:** `requirements.txt` (in the same directory)

#### `api/email_watcher/requirements.txt`
- **What:** Minimal dependency set for the email watcher (`requests==2.31.0`, `python-dotenv==1.0.1`)
- **Why:** The watcher only makes HTTP calls to the API and reads env vars; a 2-package image is much lighter than the full API image

#### `api/email_watcher/main.py`
- **What:** Standalone IMAP polling service — monitors Gmail inbox for emails with resume attachments
- **Why:** Provides an automated intake channel; candidates or recruiters can email resumes directly to a monitored inbox
- **How it works:**
  1. Connects to Gmail via IMAP SSL every `EMAIL_POLL_INTERVAL_SECS` (default 60s)
  2. Fetches all UNSEEN emails
  3. For each email: extracts PDF/DOCX attachments, parses JD-ID from subject/body (`JD-YYYYMMDD-xxxxxxxx` pattern)
  4. Saves attachments to `/data/resumes/intake/`
  5. POSTs to `POST /candidates/email-intake` with `X-Internal-Key` header (bypasses Keycloak auth)
  6. Marks email as SEEN
- **Depends on:** `EMAIL_IMAP_*`, `INTAKE_API_URL`, `INTERNAL_API_KEY` from `.env`; API container must be running
- **Used by:** docker-compose.yml email-watcher service

---

### `/api/scripts`

These scripts are run manually inside the `api` container (`docker exec api python scripts/<script>.py`).

#### `api/scripts/seed_db.py`
- **What:** One-time bootstrap: creates all 22 MongoDB collections with correct indexes, creates Qdrant `jd_vectors` and `resume_vectors` collections (384-dim, cosine)
- **Why:** Fresh environments have no collections; this script sets them up before any data is ingested
- **Depends on:** `pymongo`, `qdrant-client`, `MONGO_URI`, `QDRANT_HOST/PORT`
- **Run:** Once after `docker-compose up`

#### `api/scripts/seed_users.py`
- **What:** Inserts test manager/hod/admin users into the `users` collection with unique Keycloak IDs
- **Why:** `notify_pool_ready` queries the `users` collection for `manager`/`hod` roles to send notifications; without seed data no notifications are sent
- **Depends on:** `utils/client_utils`

#### `api/scripts/update_users.py`
- **What:** Deletes all existing users and inserts a specific set of test users
- **Why:** Used during development to reset the users collection to a known state with specific email addresses
- **Depends on:** `utils/client_utils`

#### `api/scripts/fix_mongodb_indexes.py`
- **What:** Drops all indexes on `candidate_pools` and `pipeline_stages`, then recreates the correct compound unique index `(jd_id, candidate_id)`
- **Why:** `seed_db.py` originally created incorrect single-field unique indexes; this repairs existing deployments without dropping collections
- **Depends on:** `pymongo`

#### `api/scripts/reingest_samples.py`
- **What:** Bulk-ingests all PDF/DOCX files from `/data/samples/` by creating candidate records and triggering `process_resume_task` for each
- **Why:** Quickly populates the candidate pool for testing without manual UI uploads
- **Depends on:** `utils/storage_utils`, `tasks/resume_tasks`, `pymongo`

#### `api/scripts/recreate_collections.py`
- **What:** Nuclear option — deletes and recreates both Qdrant collections, then re-embeds all JDs from MongoDB and all resumes from `/data/resumes/`
- **Why:** Used when embedding dimensions change or vector data is corrupt
- **Depends on:** `qdrant-client`, `utils/gemini_utils`, `utils/resume_utils`

#### `api/scripts/migrate_contextual_fields.py`
- **What:** For candidates missing `company_types`, `avg_team_size`, `role_type` — re-extracts these from their resume files using the Groq fast model and updates MongoDB + Qdrant
- **Why:** These fields were added in TASK-014; existing candidates ingested before that task needed backfilling
- **Depends on:** `utils/client_utils`, `utils/gemini_utils`, `utils/qdrant_utils`, `utils/resume_utils`

#### `api/scripts/migrate_jd_contextual_fields.py`
- **What:** For JDs missing `preferred_company_type`, `preferred_team_size`, `role_type` — sets sensible defaults (all company types, "Any" team size and role type)
- **Why:** These fields were added in TASK-014; existing JDs needed defaults to enable contextual scoring without breaking existing flows
- **Depends on:** `utils/client_utils`

#### `api/scripts/sync_qdrant_payloads.py`
- **What:** Syncs all candidate fields from MongoDB → Qdrant `resume_vectors` payloads without regenerating embeddings
- **Why:** After adding new fields to MongoDB (like `company_types`), Qdrant payloads need to be updated so search results include those fields; regenerating embeddings would be wasteful
- **How:** Calls `client.set_payload()` (update-in-place) for each candidate using `uuid5(NAMESPACE_DNS, candidate_id)` as point ID
- **Depends on:** `utils/client_utils`, `utils/qdrant_utils`

#### `api/scripts/sync_jd_qdrant_payloads.py`
- **What:** Syncs all JD fields from MongoDB `structured_data` sub-document → Qdrant `jd_vectors` payloads
- **Why:** Same reason as above but for JDs; includes `preferred_company_type`, `preferred_team_size`, `role_type`
- **Note:** JDs without a Qdrant vector (never processed through jd_tasks) will 404 silently and be counted as errors; they simply don't participate in matching
- **Depends on:** `utils/client_utils`, `utils/qdrant_utils`

---

### `/frontend`

#### `frontend/Dockerfile`
- **What:** Runs Vite dev server inside the container
- **Why:** Enables hot module replacement in Docker without requiring Node.js locally
- **Depends on:** `package.json`, `src/`

#### `frontend/package.json`
- **What:** Node.js project manifest with all frontend dependencies
- **Key dependencies:**
  | Package | Role |
  |---------|------|
  | react 18 + react-dom | UI framework |
  | react-router-dom 7 | Client-side routing |
  | keycloak-js 26 | Keycloak OIDC adapter |
  | lucide-react | Icon library |
  | axios | HTTP client (used in Jobs.tsx) |
  | tailwindcss 4 | Utility CSS framework |
  | vite 5 | Dev server + bundler |

#### `frontend/index.html`
- **What:** HTML entry point for the Vite SPA
- **Why:** Vite injects the bundled `main.tsx` here; the `<div id="root">` is where React mounts

#### `frontend/tailwind.config.js` / `postcss.config.js`
- **What:** Tailwind CSS v4 configuration and PostCSS pipeline
- **Why:** Tailwind v4 uses `@tailwindcss/postcss` as the PostCSS plugin; these files enable utility class compilation

---

### `/frontend/src`

#### `frontend/src/main.tsx`
- **What:** ReactDOM entry point — mounts `<App />` into `<div id="root">`
- **Why:** Standard React 18 root creation pattern
- **Depends on:** `App.tsx`, `index.css`

#### `frontend/src/App.tsx`
- **What:** Root React component — initializes Keycloak SSO and renders the route tree
- **Why:** Keycloak must be initialized before any API calls can be made; this component blocks rendering until auth resolves
- **Solves:** Uses `initialized.current` ref to prevent double-initialization in React StrictMode
- **Key behavior:** `onLoad: 'login-required'` redirects unauthenticated users to Keycloak login page
- **Depends on:** `keycloak.ts`, `components/Layout.tsx`, all page components, `react-router-dom`

#### `frontend/src/keycloak.ts`
- **What:** Keycloak-js singleton instance
- **Why:** A single instance must be shared across the app (not re-created per component); exported as default and imported wherever auth is needed
- **Config:** Points to `http://localhost:8080`, realm `jobos`, client `jobos-frontend`
- **Used by:** `App.tsx` (init), `Layout.tsx` (token/roles), `utils/api.ts` (token for API calls)

#### `frontend/src/index.css`
- **What:** Global stylesheet — imports Tailwind, defines `.custom-scrollbar` utility
- **Why:** Tailwind v4 is imported as a CSS layer here; custom scrollbar styles for the dark theme sidebar

#### `frontend/src/components/Layout.tsx`
- **What:** The persistent shell of the application — sidebar navigation, header, notification bell
- **Why:** All pages render inside `Layout`'s `{children}` slot; navigation and notifications are shared state
- **Key features:**
  - Role-based nav filtering (e.g., Analytics only shows for manager/hod/admin)
  - Notification bell with 30-second polling unread count
  - Dropdown notification panel with mark-as-read
- **Depends on:** `keycloak.ts`, `utils/api.ts` (notification functions), `lucide-react` icons
- **Used by:** `App.tsx` (wraps all routes)

#### `frontend/src/utils/api.ts`
- **What:** API client layer — base URL, auth header factory, fetch wrappers, TypeScript interfaces
- **Why:** Centralizes API calls; if the API URL changes, only this file changes
- **Key exports:**
  - `API = 'http://localhost:8000'` — backend URL
  - `getAuthHeaders()` — returns `{ Authorization: 'Bearer <token>' }` from Keycloak singleton
  - `MatchResult` interface — includes all contextual fields (`company_types`, `preferred_company_type`, `jd_role_type`, etc.)
  - `Notification` interface
  - `CandidateProfile` interface
  - Fetch wrappers: `getUnreadCount`, `listNotifications`, `markNotificationRead`, `markAllRead`, `getMyProfile`, `updateMyProfile`
- **Used by:** All page components and `Layout.tsx`

#### `frontend/src/utils/badges.tsx`
- **What:** `recommendationBadge(rec)` — renders a styled badge for shortlist/hold/reject recommendations
- **Why:** Used in both `Matching.tsx` and `RecruiterDashboard.tsx`; extracted to avoid duplication
- **Used by:** `pages/Matching.tsx`, `pages/RecruiterDashboard.tsx`

#### `frontend/src/pages/Dashboard.tsx`
- **What:** Role-aware landing page
- **Why:** Different roles see different content — staff see `RecruiterDashboard`, candidates see their own profile editor
- **Key logic:** `primaryRole()` function maps the role array to a single primary role; managers and HoDs see the recruiter view
- **Depends on:** `RecruiterDashboard.tsx`, `utils/api.ts` (getMyProfile, updateMyProfile), `keycloak.ts`

#### `frontend/src/pages/RecruiterDashboard.tsx`
- **What:** The core operational UI — batch-mode candidate review with contextual match analysis
- **Why:** Recruiters need to quickly review and act on ranked candidates for each JD; batch mode surfaces 3 at a time to avoid decision fatigue
- **Key features:**
  - JD selector dropdown
  - Batch display (3 candidates at a time, up to 9 total)
  - Candidate card with: rank, scores, recommendation badge, expand/collapse for full analysis
  - Expanded card: reasoning, 5 strengths, 5 gaps, contextual match section
  - Contextual match: checks candidate's company_types/avg_team_size/role_type against JD preferences; shows matches (green) and gaps (red)
  - Shortlist/reject with rejection reason selector
  - Race condition prevention via `pendingJdRef`
- **Key function — `evaluateContextualMatch(result, jd)`:** Computes human-readable contextual match/gap strings from raw fields; reads all data from the enriched `MatchResult` object (no separate JD fetch needed)
- **Depends on:** `utils/api.ts`, `utils/badges.tsx`, `lucide-react`
- **Used by:** `Dashboard.tsx`

#### `frontend/src/pages/Jobs.tsx`
- **What:** JD management page — upload raw file or fill structured form; lists all JDs
- **Why:** Primary intake UI; supports both file-based and form-based JD submission
- **Key fields in form:** title, level, skills, experience, compensation, work structure, location, urgency, num_positions, gender preference, preferred company type, preferred team size, role type, obfuscate toggle
- **Depends on:** `utils/api.ts`, `axios`

#### `frontend/src/pages/Matching.tsx`
- **What:** Full matching engine UI — trigger Pass 1+2, view ranked candidates with expanded reasoning
- **Why:** Provides manual control over matching; useful when a new JD is ready or after adding new candidates
- **Key features:** JD selector, Run Matching button, last-run timestamp, expandable candidate rows showing full analysis
- **Depends on:** `utils/api.ts`, `utils/badges.tsx`

#### `frontend/src/pages/Candidates.tsx`
- **What:** Resume upload page and candidate list
- **Why:** Allows recruiters to manually upload resumes into the pool
- **Depends on:** `utils/api.ts`

#### `frontend/src/pages/Analytics.tsx`
- **What:** Stub analytics page — placeholder for TASK-023
- **Depends on:** Nothing (empty layout)

#### `frontend/src/pages/CRM.tsx`
- **What:** Stub CRM page — placeholder for TASK-019
- **Depends on:** Nothing

#### `frontend/src/pages/Documents.tsx`
- **What:** Stub document vault page — placeholder for TASK-017
- **Depends on:** Nothing

---

### `/naukri-sourcer`

#### `naukri-sourcer/Dockerfile`
- **What:** Minimal Python image for the Naukri portal sourcing service
- **Why:** Will eventually scrape or call the Naukri API to source candidates when the internal pool is insufficient

#### `naukri-sourcer/main.py`
- **What:** Infinite loop stub — does nothing but sleep, waiting for TASK-010 implementation
- **Why:** Reserves the container slot; when Pass 1 flags a JD as needing external sourcing, this service will be activated
- **Future role:** Will monitor MongoDB for JDs with `needs_external_sourcing: true` and call Naukri/LinkedIn APIs

---

### `/tasks` — Feature Specification Files

Each file is a markdown specification for one development task. They define scope, acceptance criteria, and technical notes.

| File | What it specifies |
|------|------------------|
| `TASK-000-infrastructure-foundation.md` | Docker Compose setup, all services, initial network |
| `TASK-001-auth-keycloak-setup.md` | Keycloak realm, client, roles (manager/recruiter/hod/candidate) |
| `TASK-002-data-model-bootstrap.md` | MongoDB collection design, indexes, seed data |
| `TASK-003-api-skeleton-pwa-shell.md` | FastAPI skeleton, React PWA shell, routing |
| `TASK-004-jd-intake-engine.md` | JD upload endpoint, folder structure, MongoDB write |
| `TASK-005-jd-structuring-gemini.md` | AI extraction of JD fields, format generation, Qdrant upsert |
| `TASK-006-resume-ingestion-pipeline.md` | Resume upload, text extraction, metadata extraction, Qdrant upsert |
| `TASK-007-matching-engine-pass1.md` | Pass 1 cosine similarity matching, p_threshold, k_threshold |
| `TASK-008-matching-engine-pass2.md` | Pass 2 Groq reasoning, composite score, re-ranking |
| `TASK-009-manager-hod-notifications.md` | Email + in-app notifications when pool ready |
| `TASK-010-external-sourcing-adapters.md` | Naukri/LinkedIn sourcing when k_threshold not met |
| `TASK-011-obfuscated-jd-posting.md` | Anonymized JD posting to job boards |
| `TASK-012-inbound-resume-routing.md` | Email watcher IMAP intake, JD-ID routing |
| `TASK-013-recruiter-dashboard-batches.md` | Batch-mode review UI, shortlist/reject actions |
| `TASK-014-rejection-taxonomy-refinement.md` | Contextual scoring (company type, team size, role type), 5-point evaluation |
| `TASK-015-closure-enforcement-rules.md` | Auto-close JDs after filling num_positions |
| `TASK-016-why-not-selected-engine.md` | Candidate-facing rejection explanation |
| `TASK-017-document-vault-tiered.md` | Tiered document storage by sensitivity |
| `TASK-018-candidate-live-sync.md` | Real-time candidate profile sync |
| `TASK-019-crm-message-approval.md` | Outreach message drafting and approval workflow |
| `TASK-020-task-management-calls.md` | Call scheduling and task management |
| `TASK-021-invoice-generation-tracking.md` | Placement invoices and retention tracking |
| `TASK-022-retention-clock-finance.md` | Retention period enforcement, finance triggers |
| `TASK-023-analytics-dashboards.md` | Placement rates, time-to-fill, funnel metrics |
| `TASK-024-admin-config-ui.md` | Admin UI for threshold and config management |
| `TASK-025-security-hardening-audit.md` | CORS, rate limiting, secrets rotation |
| `TASK-026-ci-cd-github-actions.md` | GitHub Actions CI/CD pipeline |
| `TASK-027-aws-deployment-monitoring.md` | AWS ECS/EKS deployment with CloudWatch |

---

### `/tests`

#### `tests/test_matching_pass1.py`
- **What:** Pytest tests for the Pass 1 matching Celery task
- **Why:** Verifies that cosine similarity search returns candidates above threshold
- **Depends on:** `tasks/matching_tasks`, `utils/qdrant_utils`

#### `tests/test_tasks_1_to_6.py`
- **What:** Integration tests for the JD intake and resume ingestion pipelines (TASK-001 through TASK-006)
- **Why:** Verifies end-to-end: upload → extract → embed → store
- **Depends on:** All `api/` modules

---

### `/data` — Runtime Data Directory

All files here are generated at runtime. The directory is mounted into `api`, `worker`, and `email-watcher` containers via Docker volumes.

#### `data/clients/<client-slug>/<JD-ID>/`
- **`raw/`** — Original JD file as uploaded (email body text, PDF, or DOCX)
- **`jd.json`** — Structured JSON extracted by Groq from the raw file
- **`internal.md`** — Full JD with salary, timeline, internal notes (generated by Groq)
- **`short.md`** — Recruiter-facing bullet summary
- **`candidate.md`** — Candidate-facing description (salary replaced with "Competitive")
- **`candidates/<CAN-ID>/match_score.json`** — Pass 2 evaluation: fitment_score, composite_score, strengths, gaps, recommendation, context_bonus
- **`candidates/<CAN-ID>/pointer.json`** — Links candidate ID to their resume file path

#### `data/resumes/<CAN-ID>/`
- **`<CAN-ID>_v1.pdf`** — Versioned resume file (version increments on re-upload)

#### `data/resumes/intake/`
- Temporary landing zone for email watcher attachments; files are processed immediately and stay here for audit trail

#### `data/samples/`
- Sample resumes copied here for bulk re-ingestion via `reingest_samples.py`

---

## Key Data Flows

### JD Intake → Matching → Notification

```
Client email/upload
      │
      ▼
POST /jd/upload or /jd/create
      │
      ├── Save raw file to /data/clients/<slug>/<JD-ID>/raw/
      ├── Insert MongoDB job_descriptions record (status: received)
      └── process_jd_task.delay(jd_id) ────────────────────────────┐
                                                                    │ (Celery worker)
                                                                    ▼
                                                         1. Extract text from raw file
                                                         2. extract_jd_data() → Groq fast model
                                                         3. Save jd.json to disk
                                                         4. generate_jd_formats() → 3 markdown files
                                                         5. generate_embedding() → 384-dim vector
                                                         6. upsert_jd_vector() → Qdrant jd_vectors
                                                         7. MongoDB status → structured
                                                         8. run_matching.delay(jd_id) ──────────────┐
                                                                                                     │
                                                                                        Pass 1:      ▼
                                                                              get_jd_vector → Qdrant search
                                                                              filter by p_threshold
                                                                              save to candidate_pools
                                                                              run_pass_2.delay(jd_id) ──┐
                                                                                                        │
                                                                                           Pass 2:      ▼
                                                                                 evaluate_candidate_fitment() × N
                                                                                 composite_score calculation
                                                                                 re-rank all candidates
                                                                                 write match_score.json files
                                                                                 notify_pool_ready.delay(jd_id)
                                                                                           │
                                                                                           ▼
                                                                                 Email to managers/HoDs
                                                                                 In-app notifications created
```

### Resume Intake (Web Upload)

```
POST /candidates/upload-resume
      │
      ├── save_resume_file() → /data/resumes/<CAN-ID>/<CAN-ID>_v1.pdf
      ├── extract_text_from_file() → raw text
      ├── extract_resume_metadata() → Groq fast model
      ├── generate_embedding() → 384-dim vector
      ├── upsert to MongoDB candidates
      ├── upsert_resume_vector() → Qdrant resume_vectors
      └── (no auto-matching triggered for web uploads)
```

### Email Intake Flow

```
Gmail INBOX (UNSEEN emails)
      │ (email_watcher polls every 60s)
      ▼
Save attachment → /data/resumes/intake/
POST /candidates/email-intake (X-Internal-Key auth)
      │
      ├── Same as web upload (extract, embed, store)
      └── run_matching.delay(jd_id) if JD-ID found in subject/body
                        OR
          run_matching for all open JDs if no JD-ID
```

---

## MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `users` | All logged-in users; notification recipients (managers/HoDs) |
| `clients` | Client companies derived from email domains |
| `job_descriptions` | All JDs with structured_data sub-document and status |
| `candidates` | All candidates with metadata, resume_text, contextual fields |
| `candidate_pools` | Match results: one doc per (jd_id, candidate_id) pair with scores |
| `notifications` | In-app notification inbox per user |
| `pipeline_stages` | Future: candidate pipeline stage tracking |
| `rejections` | Future: rejection taxonomy records |
| `invoices` | Future: placement invoices |
| `tasks` | Future: recruiter task management |
| `documents` | Future: document vault |
| `calls` | Future: call scheduling records |
| `offers` | Future: offer letter tracking |
| `messages` | Future: CRM outreach messages |
| `placements` | Future: confirmed placements |
| `audit_log` | Future: action audit trail |

---

## Qdrant Collections

| Collection | Dimensions | Distance | Purpose |
|------------|-----------|----------|---------|
| `jd_vectors` | 384 | Cosine | One vector per JD; payload includes all structured fields + contextual preferences |
| `resume_vectors` | 384 | Cosine | One vector per candidate; payload includes skills, experience, company_types, avg_team_size, role_type |

Point IDs are `uuid5(NAMESPACE_DNS, jd_id/candidate_id)` — deterministic, so the same entity always maps to the same Qdrant point ID regardless of which service writes it.
