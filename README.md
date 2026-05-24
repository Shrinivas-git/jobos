# JobOS

**Recruitment Operating System** — a fully containerised, AI-powered hiring platform that replaces keyword-based resume matching with semantic, intelligence-rich candidate evaluation.

> _"Get me a JobOS verified candidate."_ — the goal when hiring managers give this instruction as a matter of course.

---

## What it does

JobOS manages the full hiring lifecycle:

- **JD Intake** — ingest job descriptions via form, email, or API; auto-structure with AI
- **Resume Ingestion** — parse PDF/DOCX resumes, extract structured metadata, embed with sentence-transformers
- **Semantic Matching** — vector search (Qdrant) + configurable K/P threshold scoring to rank candidates
- **Pipeline Management** — move candidates through stages with structured decisions and mandatory closure
- **Sourcing Adapters** — pull candidates from Naukri, Unipile (LinkedIn), Indeed, PDL, GitHub, Coresignal
- **CRM & Notifications** — recruiter task tracking, manager shortlist emails, Telegram alerts
- **Invoicing** — generate and track placement invoices
- **Analytics** — dashboards for pipeline health, rejection taxonomy, time-to-hire
- **Assessments** — structured evaluation forms with scoring
- **Job Publishing** — post JDs to external portals (Indeed, LinkedIn, Internshala) via browser automation

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    nginx (port 80)                  │
│           reverse-proxy → api + frontend            │
└──────────────┬───────────────────────┬──────────────┘
               │                       │
    ┌──────────▼──────────┐  ┌─────────▼──────────┐
    │  FastAPI API        │  │  React Frontend     │
    │  (port 8000)        │  │  (port 5173, Vite)  │
    └──────────┬──────────┘  └────────────────────┘
               │
     ┌─────────┼──────────────────────┐
     │         │                      │
┌────▼────┐ ┌──▼──────┐ ┌────────────▼───────────┐
│ MongoDB │ │ Qdrant  │ │ Redis → Celery workers  │
│ (27017) │ │ (6333)  │ │         + beat          │
└─────────┘ └─────────┘ └────────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │  Flower (port 5555)  │
                    │  task monitor        │
                    └──────────────────────┘
┌─────────────────────┐  ┌──────────────────┐
│ Keycloak (port 8080)│  │  Email Watcher   │
│ + postgres-keycloak │  │  (IMAP listener) │
└─────────────────────┘  └──────────────────┘
```

**AI Models**

| Role | Provider | Model |
|------|----------|-------|
| Fast extraction & parsing | Groq | `llama-3.1-8b-instant` |
| Reasoning (assessments, CRM, notifications) | Groq | `llama-3.3-70b-versatile` |
| Deep fitment scoring & matching (Pass 2) | Claude API (Anthropic) | `claude-sonnet-4-6` |

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.109 + Python 3.13 |
| Task queue | Celery 5.3 + Redis 7.2 |
| Primary DB | MongoDB 6.0 |
| Vector DB | Qdrant 1.7 |
| Auth | Keycloak 23 + JWT |
| Frontend | React + TypeScript + Vite |
| AI | Groq (llama-3.1, llama-3.3) + Claude API (Anthropic) |
| Embeddings | sentence-transformers (CPU) |
| PDF/DOCX | pdfplumber + python-docx |
| Browser automation | Playwright |
| Container | Docker Compose |

---

## Quick start

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone and configure

```bash
git clone <repo-url>
cd jobos
cp .env.example .env   # fill in your keys (see below)
```

### 2. Required environment variables

```env
# AI
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...

# MongoDB
MONGO_URI=mongodb://root:example@mongodb:27017

# Keycloak / Postgres
POSTGRES_DB=keycloak
POSTGRES_USER=keycloak
POSTGRES_PASSWORD=<password>

# Sourcing (optional — only for sourcing adapters you use)
UNIPILE_API_KEY=...
UNIPILE_DSN=...
PDL_API_KEY=...
APIFY_TOKEN=...         # for Indeed / Naukri scrapers
CORESIGNAL_API_KEY=...

# Notifications (optional)
TELEGRAM_BOT_TOKEN=...
SMTP_HOST=...
SMTP_USER=...
SMTP_PASSWORD=...
```

### 3. Start all services

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Keycloak | http://localhost:8080 |
| Flower (tasks) | http://localhost:5555 |
| Qdrant UI | http://localhost:6333/dashboard |

---

## Project structure

```
jobos/
├── api/
│   ├── main.py              # FastAPI app, middleware
│   ├── celery_app.py        # Celery config
│   ├── auth.py              # JWT + Keycloak validation
│   ├── routers/             # API endpoints
│   │   ├── jd.py            # Job description intake
│   │   ├── candidates.py    # Resume ingestion
│   │   ├── matching.py      # Semantic matching
│   │   ├── pipeline.py      # Hiring pipeline stages
│   │   ├── crm.py           # Recruiter task management
│   │   ├── analytics.py     # Dashboards & reports
│   │   ├── invoices.py      # Invoice generation
│   │   ├── assessments.py   # Candidate assessments
│   │   ├── publish.py       # JD portal publishing
│   │   ├── indeed.py        # Indeed integration
│   │   └── linkedin.py      # LinkedIn via Unipile
│   ├── tasks/               # Celery async tasks
│   ├── utils/               # Shared utilities
│   ├── middleware/          # Audit, rate-limit, security
│   ├── email_watcher/       # IMAP resume listener
│   └── scripts/             # DB migrations, seeds
├── sourcing/
│   ├── fetch_all.py         # Master multi-source scraper
│   └── sources/             # naukri, unipile, pdl, indeed, github, coresignal
├── frontend/                # React + TypeScript (Vite)
├── naukri-sourcer/          # Standalone Naukri scraper service
├── tasks/                   # TASK-XXX implementation specs
├── docker-compose.yml
└── nginx/                   # Reverse proxy config
```

---

## Sourcing

The `sourcing/` module pulls candidate profiles from six sources:

```bash
cd sourcing
python fetch_all.py --jd path/to/jd.json
python fetch_all.py --jd path/to/jd.json --sources naukri pdl unipile
python fetch_all.py --jd path/to/jd.json --max-per-source 30
```

Output is written to `sourcing/output/<jd_id>/<source>/` as individual JSON files.

| Source | Requires |
|--------|---------|
| Naukri | `APIFY_TOKEN` |
| Unipile (LinkedIn) | `UNIPILE_API_KEY` + `UNIPILE_DSN` |
| PDL | `PDL_API_KEY` |
| Indeed | `APIFY_TOKEN` |
| GitHub | public API (rate-limited) |
| Coresignal | `CORESIGNAL_API_KEY` |

---

## API reference

Full interactive docs at `http://localhost:8000/docs` (Swagger UI).

Key route groups:

| Prefix | Description |
|--------|-------------|
| `/auth` | Login, token refresh |
| `/candidates` | Resume upload, profile management |
| `/jd` | Job description CRUD + AI structuring |
| `/matching` | Run match, get ranked candidates |
| `/pipeline` | Stage transitions, disposition |
| `/crm` | Recruiter tasks, message approval |
| `/analytics` | Pipeline stats, rejection data |
| `/invoices` | Generate, track, mark paid |
| `/assessments` | Create and score evaluations |
| `/publish` | Post JDs to external portals |
| `/admin` | User management, system config |

---

## Development

```bash
# API only (no Docker)
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend only
cd frontend
npm install
npm run dev

# Run Celery worker locally (needs Redis running)
cd api
celery -A main.celery worker --loglevel=info
```

### Git conventions

```
Branch:  feature/TASK-XXX-short-description
Commit:  [TASK-XXX] verb: what changed
```

Never commit directly to `main`.

---

## Completed milestones

| Task | Description |
|------|-------------|
| TASK-000 | Infrastructure foundation — Docker Compose, all services |
| TASK-001 | Auth — Keycloak + JWT |
| TASK-002 | Data model bootstrap — MongoDB schemas |
| TASK-003 | API skeleton + PWA shell |
| TASK-004 | JD intake engine |
| TASK-005 | JD structuring (AI) |
| TASK-006 | Resume ingestion pipeline |
| TASK-007 | Matching engine pass 1 |
| TASK-008 | Matching engine pass 2 + sourcing adapters |

---

## License

Private — Fidelitus Corp. All rights reserved.
