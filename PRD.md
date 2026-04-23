# PRD — JobOS
**Version:** 2.0 — Architecture & Intelligence Edition
**Date:** April 21, 2026
**Owner:** Srinivas / Fidelitus Corp
**Status:** Architecture-Grade Draft
**Audience:** Tech Team | Internal Operations | Gemini CLI Build Sessions

> **What changed in v2.0:** Full containerised multi-recruiter architecture, semantic-first matching (Qdrant vector DB), two-tier resume store, JD intake via email + form with auto-folder creation, configurable K/P thresholds, Unipile + Naukri fallback sourcing, obfuscated JD portal posting, inbound resume auto-routing, live profile & vector sync, manager notification with stack-ranked shortlist, invoicing & payment workflow, sprint-gated delivery model with client demos, and AWS production path. Resume builder and native video interviewing remain out of scope.

---

## 1. Vision & Mission

### Vision
JobOS is a **Recruitment Operating System** — not a job board. It replaces the unverified, unstructured resume with a verified, intelligence-rich candidate profile, and enforces closure, structured decisions, and continuous learning at every stage of the hiring process.

LinkedIn is no longer the gold standard. Naukri persists through inertia, not satisfaction. JobOS exists to make both models obsolete — by building a system that candidates trust, recruiters rely on, and companies request by name.

> *The goal: **"Get me a JobOS verified candidate."** When hiring managers across India, the GCC, Southeast Asia, and the US give this instruction as a matter of course — JobOS has become a verb.*

### Mission
To build the operating layer that makes talent acquisition intelligent, structured, and continuously improving — across every major hiring market in the world.

### Core Principles
- Every action must reach closure. No vague statuses, no open loops.
- Candidate identity is the **profile**, not the resume.
- Search and match is **semantic**, never keyword-only.
- The internal resume pool is always the first source; external portals are the fallback, governed by configurable thresholds.
- Every rejection is data. Every outcome improves the next match.
- Communication is structured, not conversational.
- Compliance is a design principle, not a feature.
- The system is **free-stack** — no paid software or APIs except resume sourcing (Unipile for LinkedIn access).
- All development is local Docker until beta; production is AWS.

---

## 2. Market & Geographic Scope

JobOS is built for a multi-market world from day one. Architecture must accommodate different labour laws, compliance regimes, hiring cultures, and document standards without requiring a separate product per market.

### Market Rollout Sequence

| Phase | Market | Entry Sectors | Primary Problem Solved |
|-------|--------|--------------|----------------------|
| 1 | India | Healthcare, BFSI | Resume noise, zero closure discipline, no feedback loop |
| 2 | GCC (UAE, KSA, Qatar) | Expat hiring across sectors | Document fraud, unverifiable credentials, high mis-hire cost |
| 3 | Southeast Asia | Singapore, Malaysia, Indonesia, Philippines | Credential inflation, fragmented job markets |
| 4 | United States | Tech, Healthcare, Finance | LinkedIn saturation, signal noise, unverified self-reported data |

> **Architecture requirement:** Every feature must be designed with multi-market configurability in mind. Compliance, language, and data residency are configuration layers — not re-engineering efforts.

---

## 3. Users & Roles

JobOS has five distinct user roles. Every role has defined permissions, responsibilities, and interaction boundaries. No role has open-ended access — every action is structured and logged.

### 3.1 Candidate
A candidate is any individual whose resume enters the system — whether sourced internally, submitted via portal, or sent via email. The candidate is a lifelong user, not a one-time applicant.

**Capabilities:** Receive structured feedback on non-selection; track profile strength, readiness score; view active application status; respond to recruiter outreach via structured platform interactions; accept or decline offers through the platform.

**Restrictions:** Cannot contact recruiters directly outside of structured platform interactions; cannot view other candidates' data; cannot modify verified data without re-verification.

### 3.2 Recruiter
A recruiter is a member of the JobOS internal team assigned to one or more JDs by a manager or HOD.

**Capabilities:** View candidate batches pre-matched to their assigned JDs; provide structured feedback on each candidate reviewed; schedule and conduct interviews; send structured decisions (shortlist, reject, offer) with mandatory reasons; update candidate records with new details or documents received during interaction; track pipeline status and closure metrics.

**Restrictions:** Cannot skip mandatory feedback fields when rejecting; cannot leave a candidate in an open status beyond the defined time window; cannot access documents beyond the permitted tier.

**Hierarchy:**
- Account Manager — owns client relationships, oversees pipeline, accountable for closure
- Senior Recruiter — manages multiple roles, reviews quality, escalates decisions
- Junior Recruiter — handles candidate outreach, data collection, and pipeline movement
- Intern — candidate sourcing and profile completion support only

### 3.3 Manager / Allocator
Receives the JD notification with the full stack-ranked candidate pool. Allocates the JD to one or more recruiters (for roles with multiple open positions). Reviews pipeline health and recruiter performance.

**Capabilities:** Receive and review full JD + candidate pool digest; allocate JD to one or more recruiters; approve stage extensions and exception requests; review recruiter performance dashboards; initiate or approve JD posting to external portals.

### 3.4 HOD (Head of Department / Client HR Admin)
The designated client-side lead. Interacts with the pipeline, not with candidates directly.

**Capabilities:** Receive JD + shortlist digest alongside the manager; submit hiring requirements via structured JD intake or email; view candidate batches assigned to open roles; provide structured feedback on each candidate reviewed; access verified candidate documents at the offer stage; view pipeline analytics for their open roles; manage their role repository (reusable JD library) and hiring templates.

### 3.5 Internal Operations Team (Admin)
The human intelligence layer. Operates behind the system.

**Responsibilities:** Validate and refine incoming JDs; quality-check candidate profiles before they enter the matching pool; review pipeline anomalies; handle relationship-sensitive communication; monitor and enforce closure rules where automation has not yet resolved them; train and calibrate the matching engine through structured feedback; manage system configuration (K, P thresholds, portal credentials, email accounts).

---

## 4. JD Intake — Dual Ingestion Engine

Every hiring requirement enters the system via one of two paths. Both paths result in an identical data structure and folder layout.

### 4.1 Path A — Email Ingestion

A well-known, configurable email address (e.g., `jd-intake@jobos.internal`, configurable in `config.yaml`) is monitored continuously by an **Email Watcher Service**.

**Flow:**
1. Client or internal team sends an email to the intake address. Attachment may be a PDF, DOCX, or plain-text body. Subject line may contain a JD-ID if assigned by the client.
2. Email Watcher Service (Python, IMAP/SMTP via `imaplib`/`smtplib`, running in its own Docker container) polls the inbox at a configurable interval (default: 5 minutes).
3. Service extracts: sender identity → maps to existing client, or creates a new client record; attachment or email body → raw JD text; JD-ID from subject if present, else system-generates one (`JD-<YYYYMMDD>-<UUID4[:8]>`).
4. **Folder structure created:**
   ```
   /data/clients/<client_slug>/
     <JD_ID>/
       raw/          ← original email attachment or text file stored as-is
       jd.json       ← structured JSON: title, skills, experience, location, salary_range, etc.
       candidates/   ← matched candidate records (created by Matching Engine)
   ```
5. JD structured JSON is generated by Gemini 2.5 Pro from the raw text (prompt-engineered extraction).
6. JD JSON is also embedded and stored in Qdrant (`jd_vectors` collection) for semantic retrieval.
7. Matching Engine is triggered automatically (see Section 6).
8. Manager + HOD are notified once the candidate pool is assembled (see Section 6.5).

### 4.2 Path B — Recruiter Web Form

Any recruiter or HOD can submit a JD via the web UI. The form captures structured fields directly, eliminating the need for AI extraction.

**Form Fields:** Role title and level; key responsibilities (structured, not narrative); KPIs; required skills (mapped to standardised taxonomy); experience range; compensation range (min/max/structure); work structure (in-office / hybrid / remote) and location; hiring timeline and urgency; number of positions to fill; client name and account; obfuscation preference for external portal posting.

**On Submit:** Same folder structure and Qdrant embedding as Path A. Matching Engine triggered automatically.

### 4.3 JD Output Formats — Auto-Generated

From every JD (regardless of intake path), three formats are auto-generated:

| Format | Audience | Contents |
|--------|----------|----------|
| Internal JD | Matching engine + internal ops | Full detail including salary range, hiring timeline, internal notes |
| Short JD | Recruiter-facing | Summary for pipeline management — title, key skills, level, location |
| Candidate JD | Candidate-facing | Role description excluding sensitive compensation data until offer stage |

> **If a JD is flagged as unrealistic** (requirements too broad, salary too low, role definition unclear) by the internal ops team or by the AI validation layer, the client is contacted before the role goes live. This conversation is always human-led.

---

## 5. Resume Database & Vector Store

### 5.1 Architecture Overview

The resume database operates as a two-tier system:

| Tier | Technology | Contents | Purpose |
|------|-----------|----------|---------|
| File Store | Local filesystem (Docker volume, S3 on AWS) | Original resume files (PDF, DOCX) | Source of truth; retrieved when a match is confirmed |
| Vector Store | Qdrant (self-hosted Docker container) | Dense vector embeddings via Gemini `text-embedding-004` | Semantic search and match against JDs (Pass 1) |

### 5.2 Resume Ingestion — Internal Pool

Resumes enter the internal pool via multiple channels:
- **Direct upload** by recruiter or ops team via the web UI
- **Email inbound** — resumes sent to a configurable intake address (same watcher service as JD intake, differentiated by folder/label)
- **Extracted from candidate interactions** — if a recruiter receives a new or updated resume during follow-up, the system updates both the file store and vector store (see Section 5.4)
- **Sourced from portals** (Naukri, Unipile) when K-threshold is not met (see Section 6.3)

**On ingestion:**
1. Resume file stored in `/data/resumes/<candidate_id>/` with filename `<candidate_id>_<version>.pdf` (versioned; older versions retained)
2. Text extracted using `pdfplumber` (PDF) or `python-docx` (DOCX)
3. Embedding generated using **Gemini `text-embedding-004`** API (Google's SOTA embedding model; free within Gemini API quota; 768-dimensional dense vectors)
4. Vector upserted into Qdrant collection `resume_vectors` with payload: `{ candidate_id, name, email, phone, skills[], experience_years, location, source, ingested_at, file_path }`
5. Candidate record created or updated in MongoDB (`candidates` collection)

### 5.3 Resume File Store Layout

```
/data/
  resumes/
    <candidate_id>/
      <candidate_id>_v1.pdf     ← original
      <candidate_id>_v2.pdf     ← updated (if received later)
      metadata.json             ← name, email, phone, source, versions[]
  clients/
    <client_slug>/
      <JD_ID>/
        raw/
        jd.json
        candidates/
          <candidate_id>/
            match_score.json    ← fitment %, strengths, weaknesses, rank
            pointer.json        ← { candidate_id, vector_id, file_path }
            status.json         ← pipeline stage, recruiter assigned, timestamps
```

### 5.4 Live Sync — Profile & Vector Updates

Whenever new information about a candidate is received (new resume version, updated details from recruiter interaction, candidate-provided corrections):
1. New file saved to file store (versioned)
2. Text re-extracted and re-embedded
3. Qdrant vector updated (upsert by candidate_id)
4. MongoDB candidate record updated
5. All active JD candidate pools that contain this candidate are re-evaluated — match scores recalculated; position in stack rank updated; manager notified if rank changes significantly (configurable threshold)

> **This ensures the system is always working with the freshest candidate signal, not a stale snapshot.**

---

## 6. Matching & Intelligence Engine

The matching engine is the core intelligence layer of JobOS. It takes a JD as input and returns a semantically ranked, pre-evaluated candidate pool. It learns from every recruiter decision, every rejection reason, and every hiring outcome.

### 6.1 Semantic Match — Two-Pass Gemini Architecture

All matching is semantic. No keyword filters, no boolean matching. The engine operates in two passes:

**Pass 1 — Speed Layer (Gemini `text-embedding-004` + Qdrant)**
- JD text is embedded using Gemini `text-embedding-004` API at intake time
- Qdrant queried for top-N resumes by cosine similarity against the JD embedding
- Fast pre-filter: eliminates unqualified candidates at scale before the expensive reasoning pass
- Candidates with cosine similarity ≥ P threshold proceed to Pass 2

**Pass 2 — Intelligence Layer (Gemini 2.5 Pro Generative)**
- Top-N candidates from Pass 1 are passed to Gemini 2.5 Pro with their full resume text and the JD
- Gemini generates for each candidate:
  - Fitment score (0–100) with reasoning
  - Top 3 strengths relative to the JD
  - Top 2 gaps / weaknesses relative to the JD
  - Stack rank position with justification
- This output populates `match_score.json` in each candidate's JD folder and drives the manager digest

**Composite match score** (used for final ranking) is a weighted combination of:
- Gemini 2.5 Pro fitment score (primary signal)
- Pass 1 cosine similarity (secondary signal)
- Profile completeness score (candidates below minimum threshold excluded)
- Historical outcome weight (similar candidates hired/rejected for similar roles adjusts weights)
- Candidate activity signal (recency of update, responsiveness)

### 6.2 Configurable Thresholds

All thresholds are stored in `config.yaml` (mounted into the matching engine container). Changes take effect without a redeploy.

```yaml
matching:
  internal_pool_first: true
  k_threshold: 10          # Minimum candidates required from internal pool before external sourcing
  p_threshold: 0.50        # Minimum match score (0.0–1.0) to qualify as a candidate
  batch_size: 3            # Candidates per batch presented to recruiter
  max_batches: 10          # Maximum batches before ops team intervention
  rerank_on_rejection: true

sourcing:
  fallback_order:
    - naukri
    - unipile_linkedin
  email_intake_address: "jd-intake@jobos.internal"
  resume_intake_address: "resumes@jobos.internal"
  poll_interval_minutes: 5

notifications:
  manager_notify_on_pool_ready: true
  hod_notify_on_pool_ready: true
  rank_change_threshold: 3  # Notify if candidate rank shifts by more than 3 positions
```

### 6.3 Two-Tier Sourcing — Internal First, External Fallback

**Tier 1 — Internal Pool (always first):**
1. JD is embedded; Qdrant queried for top-N candidates by cosine similarity
2. Candidates with match score ≥ P are included
3. If count of qualified candidates ≥ K → proceed to manager notification (no external sourcing needed)

**Tier 2 — External Fallback (only if K not met):**
If qualified internal candidates < K, the system triggers external sourcing in the order defined in `config.yaml`:

- **Naukri** — via Naukri's recruiter API (free tier available) or scraping layer (Beautiful Soup + Selenium in a dedicated container). Search query is derived from JD JSON (role title + top skills + location). Results are parsed, resumes downloaded where accessible, processed through the same ingestion pipeline as internal resumes.
- **Unipile (LinkedIn access)** — Unipile provides a LinkedIn integration API (not LinkedIn's own paid API). Profiles are fetched, converted to text, embedded, and matched. Only profiles scoring ≥ P are processed further. Unipile is used in preference to LinkedIn's native API for cost and terms-of-service reasons.
- Additional portals can be added to the `fallback_order` list without code changes.

> **All externally sourced candidates go through the same ingestion pipeline** — file stored, vectorised, MongoDB record created — so the internal pool grows with every external sourcing event.

### 6.4 Obfuscated JD Posting to Portals

A recruiter can optionally post a JD to external portals with client identity obfuscated. The recruiter selects this option in the form or triggers it manually from the JD dashboard.

**Flow:**
1. Recruiter selects portals to post to (Naukri, Indeed, etc.) and enables obfuscation toggle
2. System generates a "Candidate JD" version with client name replaced by a sector descriptor (e.g., "Leading BFSI Firm — Bengaluru")
3. JD posted to selected portals via their APIs or automated form submission
4. Responses (inbound resumes via email) are automatically routed to the configurable resume intake address
5. Email Watcher Service detects incoming resumes, extracts JD-ID from subject/body if mentioned, or routes to "open JD matching" queue
6. Each inbound resume is processed through the standard ingestion pipeline; matched against all open JDs (or the specific JD if identified); if score ≥ P, added to the relevant JD's candidate pool
7. Internal resume pool updated accordingly

### 6.5 Manager & HOD Notification — Stack-Ranked Pool

Once the candidate pool for a JD is assembled (K candidates found, all scoring ≥ P):

**Notification contains:**
- Full JD summary
- Number of candidates in pool (internal vs externally sourced breakdown)
- Stack-ranked candidate list with:
  - Rank position
  - Candidate name (anonymised at this stage if configured)
  - Fitment % (match score)
  - Top 3 strengths relative to the JD
  - Top 2 weaknesses / gaps relative to the JD
  - Source (internal pool / Naukri / Unipile)
  - Resume available (yes/no with retrieval link)

**Delivery:** In-app notification + email digest. Configurable to also send via WhatsApp (Twilio / free WhatsApp Business API for early phase).

**Allocation:** Manager OR HOD can then allocate the JD to one or more recruiters via the UI. For JDs with multiple open positions, the JD can be assigned to multiple recruiters simultaneously, each working a subset of the candidate pool.

### 6.6 The 3-Batch Model (Recruiter-Facing)

Once a JD is allocated to a recruiter, the recruiter interacts with candidates via the structured 3-batch model.

- Recruiter receives Batch 1: top 3 candidates from the stack-ranked pool, each with match summary, fit score, gap analysis, and profile preview
- Recruiter reviews each candidate: **shortlist** or **reject with mandatory structured reason**
- If all 3 rejected: system analyses rejection reasons, refines next batch, presents Batch 2
- Repeat until shortlist confirmed or max batches reached (ops team intervenes)

**Rejection reason taxonomy:** Skills gap | Experience level mismatch | Salary expectation mismatch | Location mismatch | JD clarity issue | Cultural fit concern | Other (free text required)

> *The first rejection batch is not a failure — it is a discovery mechanism. Every rejection closes the gap between what the client said they wanted and what they actually want.*

### 6.7 Why-Not-Selected Engine

Every candidate who is not selected receives structured feedback — not a generic rejection.

- Summary of why others were selected over them (framed as gap insight, not criticism)
- Top 2–3 specific improvement actions relative to this role type
- Delivered on a weekly cadence (not immediately after rejection)
- Drives candidates back into profile improvement loops

---

## 7. Recruitment Pipeline Engine

The pipeline engine is the operational backbone of JobOS. It enforces structure, closure, and accountability at every stage. No stage can be skipped. No status can remain open beyond its defined time window.

### 7.1 Pipeline Stages

| Stage | Description | Time Limit | Escalation |
|-------|-------------|-----------|-----------|
| JD Received | JD ingested (email or form); folder created; matching triggered | 24h to pool assembly | Ops team if matching stalls |
| Pool Ready | Candidate pool assembled; manager/HOD notified | 48h to allocation | Auto-escalate to ops if unallocated |
| Allocated | JD assigned to recruiter(s) | — | — |
| Batch Review | Recruiter reviewing candidate batches | 72h per batch | Warning at 60%, escalation at 100% |
| Shortlisted | Candidate confirmed for interview | 48h to interest confirmation | Auto-release if no response |
| Interest Confirmed | Candidate confirmed interest | 5 business days to interview schedule | Warning at 3 days |
| Interview Scheduled | Interview booked (client-led; via Meet/Zoom) | — | — |
| Interview Completed | Outcome must be logged | 24h post-interview | Escalation to AM |
| Offer Extended | Offer sent to candidate | 72h for accept/decline | Auto-flag to recruiter |
| Invoiced | Invoice raised to client | Per payment terms | Finance alert |
| Closed — Placed | Candidate joined; retention clock starts | — | 90-day guarantee clock |
| Closed — Rejected | No fit found or role withdrawn | Immediate | Mandatory closure reason |

### 7.2 Closure Enforcement Rules

- Warning alert at **75%** of the time window — sent to the record owner
- Escalation alert at **100%** — sent to owner and their manager
- Auto-escalation to ops team if no action within 24h of the 100% alert
- No stage can be manually extended without a logged reason and manager approval
- Roles exceeding 90 days without closure are automatically flagged for formal review
- Every pipeline exit requires a closure reason. The system does not accept blank closures

### 7.3 Candidate Follow-Up Workflow

During active pipeline stages, the system drives structured communication:
- Stage change notifications sent to candidate immediately on status change
- Automated follow-up prompts if candidate has not responded within the stage time window
- Recruiter prompted to call/message candidate with structured outcome logging required
- All interactions (calls, emails, WhatsApp messages) logged against the candidate and JD record
- If new resume or updated details are received during follow-up: file stored, vector updated, candidate pools re-evaluated (Section 5.4)

---

## 8. Assessment & Development Engine

Assessments add verifiable signal to the candidate profile and create a continuous improvement loop.

### 8.1 Assessment Types

- **Skill assessments** — role-specific tests validating claimed skills; results scored and stored on profile; visible to recruiters at the permitted access tier
- **Psychometric evaluations** — work style, communication preference, decision-making patterns, stress response; stored as signals, not scores; inform recruiters but do not filter candidates at this stage
- **AI-led screening interviews** — structured async sessions; results summarised as: key strengths, areas of concern, recommendation (proceed / hold / decline)

### 8.2 Assessment Rules

- Prompted based on target role — finance role prompts different assessments than a nursing role
- Psychometric assessments are not hard filters at any stage — they are recruiter context, not gates
- Results cannot be manually edited; platform-administered and tamper-proof
- Candidates who retake an assessment receive the higher score, with all attempt dates recorded

---

## 9. Interview Engine

### 9.1 Scope — v2.0
Native video interviewing is **out of scope**. Interviews are conducted by the client via Meet / Zoom / their preferred tool. The JobOS interview layer provides:
- Structured interview brief delivered to recruiter and client: JD summary, candidate profile preview, suggested question set
- Interview outcome logging: recruiter or ops team logs result (shortlisted for offer / hold / reject) with mandatory structured reason
- AI summarisation of logged outcomes fed into the Why-Not-Selected engine and matching intelligence layer

### 9.2 Freelance Interviewer Model (Post-MVP)
For roles requiring domain expertise, JobOS connects clients with vetted freelance subject-matter experts. This is a marketplace model — defined in Phase 2.

---

## 10. Invoicing & Payment Workflow

### 10.1 Invoice Triggers

| Event | Invoice Type | Amount | Timing |
|-------|-------------|--------|--------|
| Candidate joins (confirmed start date) | Placement invoice | 10% of CTC | Raised within 24h of joining confirmation |
| Candidate retained at 6 months | Retention invoice | 5% of CTC | Auto-triggered by retention clock |
| 90-day replacement (if applicable) | No charge | — | Free replacement search initiated |

### 10.2 Invoice Generation Flow

1. Recruiter or AM logs "Candidate Joined" event in the pipeline with confirmed CTC and start date
2. System auto-generates invoice (PDF) using client details, JD reference, candidate name (anonymised per client preference), CTC, and fee calculation
3. Invoice emailed to client's designated billing contact (configurable per client account)
4. Invoice status tracked in the system: Raised → Sent → Acknowledged → Paid → Overdue
5. Automated payment reminders at configurable intervals (default: 7 days, 14 days, 30 days overdue)
6. Retention invoice auto-triggered 180 days after joining date; same flow

### 10.3 Payment Tracking

- All invoices tracked in MongoDB (`invoices` collection)
- Finance dashboard visible to AM and admin: outstanding, paid, overdue by client
- Payment confirmation logged manually by finance team (or via Razorpay webhook if payment gateway integrated in Phase 2)
- 90-day guarantee clock starts on joining date; if candidate exits within 90 days, replacement search opened automatically and original invoice flagged

### 10.4 Business Model Summary

| Stream | Model | Phase |
|--------|-------|-------|
| Placement fee | 10% CTC at joining + 5% CTC at 6-month retention | Phase 1 |
| Retainer model | Monthly/quarterly retainer for high-volume clients | Phase 2 |
| Credit system | Credits to unlock additional candidate batches | Phase 2 |
| Freelance interview marketplace | Platform fee on facilitated interviews | Phase 2 |
| Data intelligence products | Salary benchmarking, attrition risk, skill gap reports | Phase 3 |

---

## 11. CRM & Engagement Engine

### 11.1 Communication Principles

- No open-ended chat — all communication is structured and action-driven
- Every communication is logged, timestamped, and associated with a pipeline stage
- Channels: WhatsApp (Twilio / free tier), email, in-app notifications
- All messages are **Gemini-drafted, human-approved** — no message fires autonomously
- Templates are standardised; personalisation fields are required

### 11.2 Gemini-Drafted Messaging & Human-in-Loop Approval

All outbound messages — to candidates, managers, HODs, and clients — are **drafted by Gemini 2.5 Pro**, contextualised to the specific candidate, JD, stage, and interaction history. No message is written manually by recruiters. No message fires autonomously. Every draft goes through a human approval step before delivery.

**What Gemini drafts:**
- Candidate stage-change notifications (shortlisted, rejected, offer extended, etc.)
- Manager / HOD digest emails with stack-ranked candidate pools and reasoning narratives
- Why-Not-Selected feedback explanations (gap insights, improvement actions, framed as career intelligence)
- Weekly feedback digests to candidates
- Interview briefs sent to recruiters and clients
- Follow-up prompts when a candidate has not responded within the stage time window
- Post-placement re-engagement messages (30-day check-in, 90-day survey, 6-month career signal)
- Invoice cover emails to client billing contacts
- Escalation alerts to ops team and account managers

**Human-in-Loop flow:**
1. Gemini drafts the message with full context (candidate name, JD title, stage history, rejection reasons, match score)
2. Draft appears in the **Message Approval Queue** on the recruiter / AM dashboard
3. Recruiter or AM reviews — can approve as-is, edit inline, or discard
4. On approval, message is sent via the configured channel (email / WhatsApp / in-app)
5. Sent message logged against candidate and JD record with approver's name and timestamp
6. If a draft is not actioned within a configurable window (default: 4 hours for time-sensitive, 24 hours for routine), an escalation alert is raised to the AM

**Rules:**
- No message of any kind reaches a candidate or client without explicit human approval
- Gemini drafts are never auto-sent, even for routine stage reminders
- The approver's identity is permanently logged against every sent message
- Recruiters can enable **bulk approve** for routine stage notifications within a single session — subject to AM-level permission only; this is the sole exception to one-by-one review

### 11.3 Candidate Re-engagement — Post-Placement

| Touchpoint | Timing | Content |
|-----------|--------|---------|
| Check-in | 30 days post-joining | "How is the new role going?" |
| Experience survey | 90 days | Role satisfaction, team fit, compensation satisfaction |
| Career signal | 6 months | "Are you open to hearing about new opportunities?" |
| Market intelligence | 12 months | How the market has moved in their role area |
| Ongoing | Always | Role match alerts for strong fits, even if not actively searching |

### 11.4 Calling System

All calls (AI-initiated and human) are logged, recorded, and outcome-tagged. AI calls handle: reminders, data collection, re-engagement. Human calls handle: offer discussions, candidate concerns, client conversations.

Every call generates an AI-summarised transcript attached to the candidate/client record.

### 11.5 Task Management

Tasks are auto-created by the system on any required action (follow-up call, document request, JD clarification, recruiter reminder). Every task has an owner, due date, priority, and linked record. Overdue tasks surface immediately in dashboards and cannot be hidden without a logged reason.

### 11.6 Gamification

- Profile completion progress bar with specific next actions
- Readiness badges on assessment completion and profile milestones
- Market visibility score — candidates see how recruiter visibility changes as they complete their profile
- Streak mechanics — consistent engagement triggers visibility boosts
- Achievement notifications on profile strength improvement

> *Gamification must never feel manipulative. Every mechanic must deliver a real benefit.*

---

## 12. Document Vault

### 12.1 Document Types

Identity documents; education certificates; experience documents (offer letters, relieving letters); salary documents (last 3 months salary slips, Form 16); professional licences (medical registration, CA certificate, SEBI registration, etc.)

### 12.2 Tiered Access Model

| Access Tier | What is Accessible | When Unlocked |
|-------------|-------------------|--------------|
| Tier 1 — Preview | Profile summary, skills, experience timeline, assessment results | Candidate enters matching pool |
| Tier 2 — Review | Full profile, education, certifications, photo | Recruiter shortlists candidate |
| Tier 3 — Verified | Professional licences, education certificates (view only) | Candidate reaches interview stage |
| Tier 4 — Offer | Salary documents, identity documents (download unlocked) | Offer formally extended via platform |

### 12.3 Access Rules

- Candidates notified in real time on every document access (company name, document type, timestamp)
- Documents are view-only until Tier 4
- Candidates can revoke access at any time, except during an active offer stage
- All document access is logged and auditable (DPDP and equivalent compliance)
- Explicit consent required before upload and again before access by a new employer

---

## 13. Technical Stack & Architecture

### 13.1 Stack — Free & SOTA

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | React.js + Tailwind CSS (PWA) | Mobile-first; low-bandwidth optimised |
| **Backend API** | FastAPI (Python 3.11) | Async, high-throughput; replaces Flask for production-grade concurrency |
| **Database** | MongoDB (self-hosted) | Primary data store for all entities |
| **Vector Store** | Qdrant (self-hosted Docker) | Semantic resume and JD embeddings; cosine similarity search |
| **Embedding Model** | Gemini `text-embedding-004` (Google API) | Pass 1: resume + JD embedding for Qdrant semantic search |
| **AI / Reasoning** | Google Gemini 2.5 Pro (via Gemini CLI) | Pass 2: fitment scoring, stack ranking, strengths/gaps, JD structuring, Why-Not-Selected, message drafting |
| **AI / Mechanical** | Google Gemini 2.0 Flash | Call summaries, JD formatting, routine email parsing |
| **Email Service** | Python `imaplib` / `smtplib` + Postfix | Self-hosted; no paid email API |
| **File Storage** | Local Docker volumes → AWS S3 (production) | Resume file store |
| **Containerisation** | Docker + Docker Compose | All services containerised; single `docker-compose.yml` |
| **Auth** | Keycloak (self-hosted) | SSO, RBAC, JWT; free open-source; handles all role-based login |
| **LinkedIn Sourcing** | Unipile API | LinkedIn access without LinkedIn's native paid API |
| **Naukri Sourcing** | Naukri Recruiter API / scraping layer | Beautiful Soup + Selenium in dedicated container |
| **Notifications** | WhatsApp Business API (free tier) + SMTP | Candidate and manager notifications |
| **Invoice PDF** | WeasyPrint (Python) | Free, no LibreOffice dependency |
| **Task Queue** | Celery + Redis | Async jobs: matching, email polling, notifications, vector sync |
| **Search / Admin** | Qdrant Dashboard + MongoDB Compass | Local dev admin; no paid tools |
| **Reverse Proxy** | Nginx | SSL termination, static file serving |
| **CI/CD (Beta+)** | GitHub Actions | Free tier; Docker image builds on push |
| **Production Cloud** | AWS (ECS Fargate or EC2 + RDS) | Post-beta; user login and testing phase |

### 13.2 Docker Services Architecture

```
docker-compose.yml
├── frontend          (React PWA — Nginx served)
├── api               (FastAPI application)
├── worker            (Celery worker — matching, email polling, vector sync)
├── scheduler         (Celery Beat — reminder cadences, retention clock triggers)
├── mongodb           (Primary data store)
├── qdrant            (Vector store)
├── redis             (Celery broker + cache)
├── keycloak          (Auth server + admin UI)
├── email-watcher     (IMAP poller — JD intake + resume intake)
├── naukri-sourcer    (Scraping / API sourcing container — isolated)
└── nginx             (Reverse proxy)
```

All services share a Docker network. All data volumes are named and persisted. A single `.env` file and `config.yaml` govern all configuration.

### 13.3 Authentication & Login

- **Keycloak** provides SSO login for all roles: Candidate, Recruiter, Manager, HOD, Admin/Ops
- JWT tokens issued by Keycloak; validated by FastAPI middleware
- RBAC enforced at the API layer — every endpoint checks role and scope
- Social login (Google OAuth) for candidates via Keycloak identity provider (free)
- Password reset, MFA (TOTP), and session management handled by Keycloak

### 13.4 Multi-Recruiter Concurrency

- FastAPI is async and handles multiple concurrent recruiters natively
- All matching and sourcing operations run as Celery tasks — they do not block the API
- Qdrant handles concurrent read queries efficiently (designed for high-throughput semantic search)
- Redis provides distributed locking for critical write operations (e.g., preventing duplicate candidate assignments)
- MongoDB connection pooling configured for concurrent access

---

## 14. Data Model

### Core Collections (MongoDB)

| Collection | Key Fields |
|-----------|-----------|
| `users` | id, role (candidate/recruiter/manager/hod/admin), name, email, keycloak_id, created_at |
| `clients` | id, slug, name, billing_contact, account_manager_id, created_at |
| `job_descriptions` | id, client_id, jd_id, title, structured_json, folder_path, vector_id, status, created_at, source (email/form) |
| `candidates` | id, name, email, phone, skills[], experience_years, location, source, file_paths[], vector_id, profile_completeness, created_at, updated_at |
| `candidate_pools` | jd_id, candidate_id, match_score, strengths[], weaknesses[], rank, source, status, recruiter_id, batch_number |
| `pipeline_stages` | id, jd_id, candidate_id, stage, entered_at, exited_at, exit_reason, recruiter_id |
| `batches` | id, jd_id, recruiter_id, batch_number, candidate_ids[], status, released_at, completed_at |
| `rejections` | id, batch_id, candidate_id, reason_code, reason_text, rejected_by, rejected_at |
| `invoices` | id, client_id, jd_id, candidate_id, type (placement/retention), amount, status, raised_at, paid_at |
| `tasks` | id, owner_id, linked_type, linked_id, description, due_at, priority, completed_at |
| `documents` | id, candidate_id, type, tier, file_path, uploaded_at, access_log[] |
| `notifications` | id, recipient_id, type, payload, sent_at, read_at |
| `calls` | id, candidate_id, recruiter_id, type (ai/human), outcome_code, recording_path, summary, timestamp |
| `audit_log` | id, actor_id, action, entity_type, entity_id, timestamp, ip |

### Qdrant Collections

| Collection | Vector Source | Payload |
|-----------|--------------|---------|
| `resume_vectors` | Resume text (all-MiniLM-L6-v2) | candidate_id, skills[], experience_years, location, source, file_path |
| `jd_vectors` | JD structured text (all-MiniLM-L6-v2) | jd_id, client_id, title, status |

---

## 15. Key User Flows

### 15.1 JD-to-Candidate-Pool Flow (Complete)

```
JD arrives (email or form)
  → Email Watcher / Form Submit
    → Client identified / created; JD-ID assigned
    → Folder created: /data/clients/<slug>/<JD_ID>/
    → Raw JD stored; jd.json generated (Gemini 2.5 Pro)
    → JD embedded → Qdrant (jd_vectors)
    → Celery task: run_matching(jd_id)
      → Qdrant query: top-N resumes by cosine similarity to JD
      → Filter: match_score ≥ P
      → Count qualified: ≥ K? → proceed
                          < K? → trigger external sourcing
        → [Naukri / Unipile] → resumes ingested → vectorised → re-queried
      → Stack rank assembled
      → Candidates/ subfolder populated with pointer.json + match_score.json
    → Manager + HOD notified (in-app + email) with full stack-ranked digest
      → Manager / HOD allocates JD to recruiter(s)
        → Recruiter receives JD + Batch 1 (top 3 candidates)
          → Review → shortlist / reject (with reason)
          → Next batch released on rejection
          → Shortlist confirmed → Interest confirmation sent to candidate
            → Pipeline progresses through stages
              → Interview (client-led, external tool)
              → Offer → Invoice raised
              → Joined → Retention clock started → Retention invoice at 6m
```

### 15.2 Inbound Resume Auto-Routing Flow

```
Resume received at resumes@jobos.internal
  → Email Watcher detects new email
    → JD-ID extracted from subject/body (if present)
    → Resume extracted (PDF/DOCX attachment)
    → Ingestion pipeline:
      → File saved: /data/resumes/<candidate_id>/
      → Text extracted (pdfplumber / python-docx)
      → Embedding generated (all-MiniLM-L6-v2)
      → Qdrant upsert (resume_vectors)
      → MongoDB candidate record created/updated
    → If JD-ID known: match against that JD only
      If JD-ID unknown: match against all open JDs
    → For each JD where score ≥ P:
      → Candidate added to JD candidate pool
      → Manager notified if pool changes significantly
```

### 15.3 Candidate Update Flow

```
Recruiter receives updated resume / new details during follow-up
  → Recruiter uploads via UI or forwards to intake email
    → Ingestion pipeline runs (versioned file, re-embedded)
    → All active JD pools containing this candidate re-evaluated
    → Match scores recalculated; ranks updated
    → Manager notified if rank shift > threshold (config)
```

---

## 16. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Concurrent Recruiters** | 50+ simultaneous users (local Docker); 500+ (AWS production) |
| **Matching Latency** | Internal pool query < 5s; with external sourcing < 60s |
| **API Response Time** | < 2s for all UI-driven API calls |
| **Availability** | 99.5% uptime SLA (production AWS) |
| **Scale** | 1,000 DAU at launch; 100k API requests/day Year 1 |
| **Resume Pool** | Designed for 500k+ resume vectors in Qdrant (horizontal scaling via Qdrant collections) |
| **Accessibility** | Mobile-first; low-bandwidth optimised |
| **Data Residency** | All data stored in India region (AWS ap-south-1) for Phase 1 |
| **Backup** | Daily automated backup of MongoDB + Qdrant snapshots + file store to S3 |
| **Logging** | Structured JSON logs; ELK stack (optional) or CloudWatch (AWS) |

---

## 17. Analytics & Telemetry

### 17.1 Internal Operations Analytics

- Pipeline health — active roles by stage, average time in stage, at-risk roles
- Account health — closure rate per client, offer acceptance rate, repeat engagement rate
- Recruiter performance — decisions per period, rejection reason quality, closure rate, time-to-decision
- Candidate pool health — completeness distribution, match rate by role category
- Sourcing analytics — internal vs external sourcing ratio, cost per sourced candidate
- Calling and task performance — call connection rate, task completion rate, overdue task count

### 17.2 Client Analytics

- Pipeline view — real-time status of all open roles and candidates at each stage
- Hiring performance — time-to-hire, batches-to-shortlist average, offer acceptance rate
- Placement outcomes — retention rate at 30 / 90 / 180 / 365 days
- Invoice and payment summary — outstanding, paid, overdue

### 17.3 Candidate Analytics

- Profile strength breakdown — completeness, readiness, visibility with specific improvement actions
- Match activity — appearances in recruiter batches, shortlist count
- Feedback history — all Why-Not-Selected feedback and improvement actions taken

### 17.4 System-Level Intelligence

- Matching accuracy trend — correlation between match score and recruiter acceptance rate
- Rejection pattern analysis — recurring rejection reasons across clients and roles
- Sourcing effectiveness — conversion rate per sourcing channel
- Vector drift monitoring — alert if embedding model is updated and re-embedding is required

---

## 18. Rules Engine

The rules engine is the enforcement layer. It operates silently across every part of the system.

### 18.1 Closure Enforcement

Every pipeline stage has a defined time window. The rules engine monitors all active records and triggers an escalating response when a window is at risk.

- Warning at 75% of time window → record owner
- Escalation at 100% → owner + manager
- Auto-escalation to ops team if no action within 24h of 100% alert
- No stage can be manually extended without logged reason + manager approval
- Roles > 90 days open require formal extension request

### 18.2 Objective Decision Enforcement

- Rejection requires a structured reason from the taxonomy (free text allowed as supplement, not substitute)
- Rejection reason patterns monitored — repeated "JD clarity issue" across 3 batches → ops team flagged to intervene with client
- Offer withdrawal requires mandatory reason; logged permanently against client account
- Stage skipping blocked by the system

### 18.3 Duplicate Prevention

- On profile creation: duplicate check by email, phone, name+employer
- Detected duplicates flagged for review before entering active pool — not auto-merged
- Candidate rejected for a specific role within 6 months cannot be re-submitted to the same client for the same role without ops team approval
- Multi-channel sourcing deduplicates by candidate_id — single record, multiple source channels noted

### 18.4 Recruiter Behaviour Control

- Recruiters cannot contact candidates outside of the platform's structured communication system
- Cannot access documents beyond permitted tier for the current pipeline stage
- Cannot close a role without mandatory closure reason and candidate notification confirmation
- Vague or consistently generic rejection reasons flagged to manager for review
- Recruiter performance tracked automatically and surfaced in manager dashboards

---

## 19. Security, Privacy & Compliance

| Requirement | Detail |
|-------------|--------|
| **Encryption at rest** | AES-256 (MongoDB encrypted storage, S3 server-side encryption) |
| **Encryption in transit** | TLS 1.3 (Nginx + all internal service communication) |
| **Access Control** | Keycloak RBAC; JWT with role-scoped claims; API-layer enforcement |
| **Document Vault** | 4-tier access model; view-only until Tier 4; candidate consent required |
| **DPDP Compliance (India)** | Tiered consent manager, right to erasure, immutable access logs, data localisation |
| **Audit Log** | Every data access, stage change, and document access is immutably logged |
| **Data Residency** | Phase 1: AWS ap-south-1 (Mumbai); per-market configuration for Phase 2+ |
| **Consent** | Collected at point of data submission; tiered; revocable; timestamped |
| **Right to Erasure** | Candidate data deletion triggers defined data handling process within legal window |
| **Breach Notification** | Automated alert to admin + legal contact within 24h of detected breach |

---

## 20. Authentication, Authorisation & Session Management

JobOS is a multi-tenant, multi-role production system. Authentication and authorisation are not afterthoughts — they are foundational. Every user, every API call, and every data access is governed by a single, auditable identity and access management layer.

### 20.1 Identity Provider — Keycloak

**Keycloak** (self-hosted, open-source) is the sole identity provider for all environments (local Docker, staging, production AWS). It is the single source of truth for user identity, roles, and session state.

| Capability | Configuration |
|-----------|--------------|
| Protocol | OpenID Connect (OIDC) + OAuth 2.0 |
| Token format | JWT (RS256 signed; asymmetric key pair) |
| Token expiry | Access token: 15 minutes; Refresh token: 8 hours |
| MFA | TOTP (Google Authenticator / Authy) — mandatory for Recruiter, Manager, HOD, Admin roles |
| Social login | Google OAuth 2.0 — available for Candidate role only |
| Password policy | Min 10 characters; uppercase + lowercase + number + symbol; no reuse of last 5 passwords; 90-day rotation prompt for internal roles |
| Brute force protection | Account locked after 5 failed attempts; 15-minute lockout; admin notified |
| Session management | Concurrent session limit per role (configurable); idle timeout 30 minutes for internal roles |
| Realm | Single Keycloak realm: `jobos`; separate client configurations for frontend (public) and backend API (confidential) |

### 20.2 Role-Based Access Control (RBAC)

Roles are defined in Keycloak and enforced at the FastAPI middleware layer on every API endpoint. No endpoint is accessible without a valid JWT containing the correct role claim.

| Role | Keycloak Group | Access Scope |
|------|---------------|-------------|
| `candidate` | `candidates` | Own profile, own application status, own feedback, own documents |
| `recruiter` | `recruiters` | Assigned JDs, allocated candidate batches, pipeline management, message approval queue |
| `senior_recruiter` | `senior-recruiters` | All recruiter permissions + cross-recruiter pipeline visibility within assigned accounts |
| `manager` | `managers` | Full pipeline across assigned accounts, JD allocation, recruiter performance dashboard, bulk approve permission |
| `hod` | `hod` | Client-side: own company JDs, candidate batches, offer stage documents, placement analytics |
| `account_manager` | `account-managers` | Full account visibility, exception approvals, client relationship tools, invoice management |
| `ops_admin` | `ops-admins` | Full system access including config UI, audit logs, all pipelines, all accounts |
| `system` | `system` | Internal service-to-service calls only; never issued to human users |

> *Principle: Least privilege at every layer. A recruiter cannot see what is not assigned to them. A candidate cannot see any other candidate. Every permission is explicit — nothing is implicit.*

### 20.3 API Authentication Flow

```
User logs in (React frontend)
  → Keycloak login page (hosted by Keycloak container)
    → Credentials validated → JWT issued (access + refresh tokens)
      → Frontend stores tokens in memory (never localStorage)
        → Every API request: Authorization: Bearer <access_token>
          → FastAPI middleware validates JWT signature (RS256 public key from Keycloak JWKS endpoint)
            → Role claim extracted → endpoint permission checked
              → Request proceeds or 403 returned
                → On token expiry: refresh token used silently to obtain new access token
                  → On refresh token expiry: user redirected to login
```

### 20.4 Service-to-Service Authentication

Internal Docker services (e.g., Celery worker calling FastAPI, Email Watcher triggering matching) use **Keycloak Client Credentials flow** — machine-to-machine OAuth 2.0. No human credentials are used in service communication. Each service has its own Keycloak client with scoped permissions.

### 20.5 Audit & Session Logging

- Every login, logout, failed attempt, token refresh, and permission denial is logged to the `audit_log` MongoDB collection with: actor_id, action, timestamp, IP address, user agent
- Keycloak admin events are separately logged and retained for 90 days
- Session revocation (admin-initiated logout) propagates immediately via Keycloak's backchannel logout
- All audit logs are immutable — no update or delete operations permitted on the audit collection

---

## 21. Cloud Architecture & Infrastructure

### 21.1 Environment Strategy

JobOS runs across four environments. Each is isolated — no environment shares infrastructure with another.

| Environment | Infrastructure | Purpose | Access |
|------------|---------------|---------|--------|
| **Local (Dev)** | Docker Compose on developer machine | Feature development, unit testing | Developer only |
| **Staging** | AWS (mirrors production; reduced capacity) | Integration testing, sprint demos, QA | Internal team only; VPN-gated |
| **Beta** | AWS (production infrastructure; limited user pool) | User acceptance testing; client onboarding | Invited beta users; full auth |
| **Production** | AWS (full capacity; hardened) | Live system | All authorised users |

> *No code goes to staging without passing local tests. No code goes to beta without passing staging. No code goes to production without explicit sign-off after beta validation.*

### 21.2 AWS Production Architecture

**Region:** `ap-south-1` (Mumbai) for Phase 1 — data residency compliance for India (DPDP).

```
Internet
  → Route 53 (DNS)
    → CloudFront (CDN — React frontend static assets)
    → Application Load Balancer (ALB)
      → ECS Fargate Cluster
          ├── frontend-service     (Nginx + React build; 2 tasks min)
          ├── api-service          (FastAPI; 2 tasks min; auto-scale to 10)
          ├── worker-service       (Celery worker; 2 tasks min; auto-scale to 8)
          ├── scheduler-service    (Celery Beat; 1 task; no auto-scale)
          ├── email-watcher        (1 task; no auto-scale)
          └── naukri-sourcer       (1 task; scheduled runs only)
      → Amazon DocumentDB (MongoDB-compatible; 3-node replica set; Multi-AZ)
      → Amazon ElastiCache (Redis; cluster mode; Multi-AZ)
      → Qdrant on EC2 (r6i.xlarge; EBS gp3 volume; 500GB; snapshots to S3)
      → Amazon S3 (resume file store; versioning enabled; lifecycle policy)
      → Keycloak on EC2 (t3.medium; dedicated; RDS PostgreSQL backend)
```

**Why EC2 for Qdrant and Keycloak, not Fargate?**
- Qdrant requires persistent, high-IOPS storage and benefits from predictable memory allocation — EC2 with EBS is more cost-effective and operationally simpler than a stateful Fargate task with EFS
- Keycloak with PostgreSQL backend requires stable networking and persistent session state — EC2 is standard for production Keycloak deployments

### 21.3 Networking & Security Groups

| Layer | Configuration |
|-------|-------------|
| VPC | Dedicated VPC; CIDR `10.0.0.0/16` |
| Subnets | Public subnets (ALB, NAT Gateway); Private subnets (ECS, RDS, ElastiCache, EC2) |
| Internet access | NAT Gateway for outbound (Gemini API, Unipile, Naukri, WhatsApp); no direct inbound to private subnets |
| Security groups | ALB: 443 inbound from internet; ECS services: inbound from ALB only; DB/Cache: inbound from ECS security group only |
| WAF | AWS WAF on ALB — OWASP Top 10 ruleset; rate limiting (1000 req/min per IP); bot detection |
| Secrets | AWS Secrets Manager for all credentials (DB passwords, Gemini API key, Unipile key, SMTP); never in environment variables or code |
| SSL/TLS | ACM certificates; TLS 1.3 enforced on ALB; HSTS header on all responses |

### 21.4 Auto-Scaling Policy

| Service | Min Tasks | Max Tasks | Scale-Out Trigger | Scale-In Trigger |
|---------|----------|----------|------------------|-----------------|
| `api-service` | 2 | 10 | CPU > 70% for 2 min | CPU < 30% for 5 min |
| `worker-service` | 2 | 8 | Celery queue depth > 50 jobs | Queue depth < 10 for 5 min |
| `frontend-service` | 2 | 4 | CPU > 80% for 2 min | CPU < 40% for 5 min |

Qdrant and Keycloak (EC2) are manually scaled — vertical scaling via instance type upgrade. Qdrant horizontal scaling via collection sharding is available if resume pool exceeds 1M vectors.

### 21.5 Data Storage Strategy

| Data Type | Storage | Backup | Retention |
|-----------|---------|--------|----------|
| Operational data (all MongoDB collections) | Amazon DocumentDB (Multi-AZ) | Automated daily snapshots; 30-day retention; point-in-time recovery (PITR) enabled | Indefinite (active records); 7 years (audit logs, invoices) |
| Vector embeddings | Qdrant on EC2 (EBS) | Daily Qdrant snapshots to S3; 14-day retention | As long as candidate record is active |
| Resume files | Amazon S3 (versioned) | S3 versioning + S3 Cross-Region Replication to `ap-southeast-1` | 7 years post-candidate-archival |
| Session / cache data | ElastiCache Redis | No backup required (ephemeral by design) | TTL-managed |
| Keycloak identity data | RDS PostgreSQL | Automated daily backup; 7-day retention | As long as user account is active |
| Invoice PDFs | Amazon S3 (separate bucket; versioned) | S3 Cross-Region Replication | 7 years (legal requirement) |

### 21.6 Disaster Recovery

| Metric | Target | Mechanism |
|--------|--------|-----------|
| **RPO** (Recovery Point Objective) | < 1 hour | DocumentDB PITR; Qdrant hourly snapshots to S3; S3 versioning |
| **RTO** (Recovery Time Objective) | < 4 hours | ECS tasks auto-restart; DocumentDB Multi-AZ automatic failover (< 30s); documented runbook for Qdrant + Keycloak EC2 recovery |
| Database failover | < 30 seconds | DocumentDB Multi-AZ automatic |
| Full region failure | 24-hour recovery target | S3 cross-region replication; AMI snapshots of Qdrant + Keycloak EC2; runbook for ap-southeast-1 (Singapore) failover region |

> *Every quarter, a disaster recovery drill is conducted — a simulated full-environment restore to staging from backups. Results are logged and reviewed.*

---

## 22. DevOps, Observability & Disaster Recovery

### 22.1 CI/CD Pipeline

All code changes flow through a gated pipeline. No direct deployments to any environment above local. Pipeline is implemented in **GitHub Actions** (free tier for private repos up to 2,000 minutes/month; Actions minutes are the only paid element).

```
Developer pushes to feature branch
  → GitHub Actions: CI Pipeline
      ├── Lint (Ruff for Python; ESLint for React)
      ├── Unit tests (pytest; Jest)
      ├── Docker image build (each affected service)
      └── Integration tests (Docker Compose test environment spun up)
  → PR raised → peer review required (min 1 approval)
    → Merge to `develop`
      → GitHub Actions: Staging Deploy Pipeline
          ├── Docker images built + tagged + pushed to Amazon ECR
          ├── ECS staging cluster updated (rolling deployment; zero-downtime)
          ├── Smoke tests run against staging
          └── Slack / email notification: staging deploy success / failure
        → Manual promotion gate (tech lead approval)
          → Merge to `main`
            → GitHub Actions: Production Deploy Pipeline
                ├── Docker images tagged as release (semver)
                ├── ECS production cluster updated (blue/green deployment via CodeDeploy)
                ├── Health checks validated before traffic shifted
                ├── Automatic rollback if health checks fail within 5 minutes
                └── Deploy notification to team
```

**Deployment strategy:** Blue/green on production — new task set spun up alongside existing; traffic shifted only after health checks pass; old task set kept for 10 minutes then terminated. Zero-downtime guaranteed.

### 22.2 Docker Image Management

- All service images built from pinned base images (e.g., `python:3.11.9-slim`, not `python:3.11-slim`)
- Images stored in **Amazon ECR** (Elastic Container Registry) — one repository per service
- Image scanning enabled on push (Amazon Inspector) — critical vulnerabilities block deployment
- Images tagged with: `git-sha` (every build) + `semver` (release builds) + `latest` (staging only; never used in production)
- Old images automatically purged from ECR after 30 days (lifecycle policy)

### 22.3 Observability Stack

**The three pillars — metrics, logs, traces — are all covered:**

| Pillar | Tool | What is Monitored |
|--------|------|------------------|
| **Metrics** | Amazon CloudWatch + custom dashboards | ECS CPU/memory per service; ALB request rate, latency, 4xx/5xx rate; DocumentDB connections, query latency; ElastiCache hit rate; Qdrant query latency; Celery queue depth |
| **Logs** | CloudWatch Logs (structured JSON) | All FastAPI request logs; Celery task logs; Email Watcher logs; Gemini API call logs (latency, token usage, cost); Keycloak event logs; Nginx access logs |
| **Traces** | AWS X-Ray | End-to-end request tracing across FastAPI → Celery → Qdrant → DocumentDB; identify bottlenecks in matching pipeline |
| **Error Tracking** | Sentry (free tier — 5,000 errors/month) | Python exceptions (FastAPI, Celery); React frontend errors; source-mapped stack traces |
| **Uptime Monitoring** | Better Uptime (free tier) | External health check on all public endpoints every 60 seconds; SMS + email alert on downtime |

### 22.4 Alerting Policy

All alerts are tiered. Not everything pages the on-call engineer.

| Severity | Condition | Action |
|----------|-----------|--------|
| **P1 — Critical** | API service down; database connection failure; Keycloak unreachable; error rate > 10% | Immediate PagerDuty alert (or SMS); 15-minute response SLA |
| **P2 — High** | Matching pipeline stalled > 15 min; Celery queue depth > 200; Qdrant latency > 5s; Gemini API errors > 5% | Slack alert; 1-hour response SLA |
| **P3 — Medium** | Individual task failures; staging deploy failure; ECR image scan critical finding | Slack alert; next business day response |
| **P4 — Low** | Slow queries (> 2s); approaching auto-scale limits; disk usage > 70% | Daily digest email |

### 22.5 Performance Baselines & SLOs

| SLO | Target | Measurement |
|-----|--------|------------|
| API availability | 99.5% monthly | CloudWatch ALB 5xx rate |
| API p95 latency | < 2 seconds | CloudWatch ALB TargetResponseTime |
| Matching pipeline (Pass 1 + Pass 2) | < 60 seconds end-to-end | Custom CloudWatch metric |
| Gemini embedding call latency | < 3 seconds per resume | Logged per call; CloudWatch custom metric |
| Message approval queue — draft generation | < 10 seconds | Custom metric |
| Qdrant query latency (Pass 1) | < 500ms for 500k vectors | Qdrant built-in metrics → CloudWatch |

### 22.6 Local Development — Docker Compose Standards

Every developer runs the full stack locally via a single command. No cloud dependencies for local development except Gemini API (which uses a shared dev API key with a monthly quota cap).

```bash
# Full local stack
docker-compose up -d

# Individual service restart
docker-compose restart api

# View logs
docker-compose logs -f api worker

# Run tests inside container
docker-compose exec api pytest

# Seed local DB with test data
docker-compose exec api python scripts/seed_dev_data.py
```

**Local environment rules:**
- `.env.local` file (gitignored) contains all local secrets — never committed
- `config.yaml` is committed with safe defaults (K=5, P=0.4 for dev)
- Qdrant and MongoDB data volumes are named and persist between restarts
- A `make` target (`make reset`) wipes all local data volumes for a clean slate
- Every developer must be able to reproduce the full stack from scratch in < 10 minutes using the setup runbook (`docs/LOCAL_SETUP.md`)

### 22.7 Release Management & Versioning

- **Semantic versioning:** `MAJOR.MINOR.PATCH` — e.g., `1.0.0` for beta launch
- **Changelog:** `CHANGELOG.md` maintained in the repository; every PR must include a changelog entry
- **Release notes:** Generated by GitHub Actions from changelog on every production deploy; sent to internal team
- **Hotfix policy:** Critical production bugs follow an expedited path — hotfix branch from `main`, peer review mandatory, same CI pipeline, immediate production deploy with post-mortem required within 24 hours
- **Feature flags:** New features shipped behind feature flags (environment variable in `config.yaml`) — allows production deployment without activation; ops admin enables per-tenant via admin UI

---

## 23. Edge Cases & Resilience

| Scenario | Handling |
|----------|---------|
| Gemini API unavailable (embedding or generative) | Pass 1 fallback: BM25 keyword pre-filter (local, via `rank_bm25` Python library) populates candidate shortlist; Pass 2 fallback: matching paused, ops team notified, queue retried automatically when API recovers; no degraded match results are presented to recruiters as final |
| Qdrant unavailable | Queue matching jobs in Redis; retry when Qdrant recovers; API returns graceful degraded response |
| No candidates found (K not met after all sources) | Ops team notified; manual sourcing triggered; JD flagged as "hard to fill" |
| Duplicate JD received (same client, same role) | Rules engine detects duplicate by JD embedding similarity; flags for human review before creating new record |
| Candidate unresponsive | Auto-escalating follow-up sequence; stage auto-closes after defined window with logged reason |
| Invoice dispute | Invoice flagged; finance team notified; replacement search not initiated until dispute resolved |
| Inbound resume with no JD match (score < P for all open JDs) | Resume ingested and stored in internal pool; not assigned to any JD; available for future matches |
| Unipile rate limit hit | Exponential backoff retry; ops team notified if sourcing incomplete after 3 attempts |
| Candidate visibility score decays (90-day inactivity) | Profile flagged; candidate prompted to update; archived after 365 days of inactivity |

---

## 24. Risks & Dependencies

| Risk | Mitigation |
|------|-----------|
| Low internal resume pool quality at launch | Structured ingestion pipeline with completeness scoring; external sourcing fallback operational from Day 1 |
| Unipile pricing / terms change | Architecture supports pluggable sourcing adapters; Unipile can be swapped for alternative without core changes |
| Gemini API cost at scale | Gemini 2.0 Flash for all mechanical tasks; 2.5 Pro only for Pass 2 reasoning on shortlisted candidates (not full pool); `text-embedding-004` called once per resume at ingestion and once per JD at intake — not per query |
| DPDP legal sign-off delay | Build consent infrastructure from Sprint 1; legal review is a go-live gate, not a post-launch item |
| Low JD quality from clients | AI validation layer flags unrealistic JDs before matching runs; ops team intervention mandated |
| Naukri scraping blocks | Rotating proxy + rate limiting in dedicated container; Unipile as primary fallback |
| Multi-recruiter data conflicts | Redis distributed locking on critical write paths; MongoDB optimistic concurrency |

---

## 25. Open Questions

| # | Question | Owner | Due |
|---|----------|-------|-----|
| 1 | Final Unipile plan and per-profile fetch pricing — confirm budget envelope | Srinivas | Sprint 1 |
| 2 | Naukri API access tier available (recruiter account) vs scraping fallback | Ops | Sprint 1 |
| 3 | Configurable email account credentials and domain for intake addresses | Infra | Sprint 0 |
| 4 | DPDP legal counsel engagement and consent framework sign-off | Srinivas | Week 3 |
| 5 | WhatsApp Business API — free tier limits vs Twilio for notification volume | Tech | Sprint 2 |
| 6 | AWS account setup, IAM roles, and S3 bucket naming for beta | Srinivas | Sprint 4 |
| 7 | Client-facing invoice format and payment terms (standard vs per-client) | Business | Sprint 3 |
| 8 | Obfuscated JD posting — which portals beyond Naukri (Indeed India, Shine, others)? | Business | Sprint 2 |

---

## 26. Phases & Sprint-Gated Delivery (Development Roadmap)

> **Development Context:** Built locally using Docker Compose. Gemini CLI with MCPs and skills as the primary coding environment. All sprints conclude with a working demo to the client on the local Docker environment. Beta launch deploys to AWS and opens for user login and testing. Production follows once beta is validated.

### Phase 0 — Infrastructure & Foundation (Sprint 0)

**Duration:** 1 week
**Goal:** Skeleton running; all containers up; auth working; data model seeded

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S0 | Week 1 | `docker-compose.yml` with all 11 services; Keycloak configured with all 5 roles; FastAPI skeleton with JWT middleware; MongoDB collections created; Qdrant initialised with `resume_vectors` and `jd_vectors`; Nginx configured; `config.yaml` with K, P, threshold parameters; React shell with login screen | Login with each role; role-based dashboard stub visible |

---

### Phase 1 — JD Intake, Resume Pool & Semantic Matching (Sprints 1–3)

**Duration:** 3 weeks
**Goal:** End-to-end JD intake → semantic match → manager notification working

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S1 | Week 2 | Email Watcher service (IMAP poll); JD form UI (recruiter/HOD); folder structure creation; Gemini 2.5 Pro JD structuring; `jd.json` generation; JD embedding + Qdrant upsert | Submit JD via form and email; JD folder created; `jd.json` visible |
| S2 | Week 3 | Resume ingestion pipeline (file store + pdfplumber/python-docx + MiniLM embedding + Qdrant upsert + MongoDB); resume intake email watcher; bulk import UI for internal pool seeding | Upload 10 resumes; confirm in Qdrant and MongoDB |
| S3 | Week 4 | Matching engine (Qdrant cosine query → filter by P → count vs K → stack rank); candidate pool assembly; `candidates/` folder population with `pointer.json` + `match_score.json`; manager + HOD notification (email + in-app) with stack-ranked digest | JD submitted → matching runs → manager receives digest with ranked candidates |

---

### Phase 2 — External Sourcing & Obfuscated Posting (Sprints 4–5)

**Duration:** 2 weeks
**Goal:** K-threshold fallback to Naukri + Unipile; obfuscated JD posting; inbound resume routing

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S4 | Week 5 | Naukri sourcing adapter (API or scraping container); Unipile adapter for LinkedIn; fallback trigger on K-threshold; external candidates ingested into same pipeline as internal | Force K-threshold failure; confirm Naukri/Unipile sourcing triggers and candidates appear in pool |
| S5 | Week 6 | Obfuscated JD posting UI (recruiter selects portals, enables obfuscation); portal submission layer; inbound resume auto-routing (JD-ID detection → match → pool update) | Post obfuscated JD; simulate inbound resume response; confirm auto-routing to correct JD pool |

---

### Phase 3 — Recruiter Pipeline, Batch Model & Closure Engine (Sprints 6–7)

**Duration:** 2 weeks
**Goal:** Recruiter can work JD from allocation to shortlist with full closure enforcement

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S6 | Week 7 | JD allocation UI (manager assigns to recruiter/s); recruiter dashboard; 3-batch model UI (batch display with match score, strengths, weaknesses); structured rejection with reason taxonomy; next-batch refinement on rejection | Full batch review cycle: allocate → Batch 1 → reject with reason → Batch 2 refined |
| S7 | Week 8 | Closure enforcement engine (Celery Beat time-window monitoring; 75%/100% alerts; auto-escalation); pipeline stage management UI; Why-Not-Selected engine (Gemini generates candidate feedback); weekly feedback digest | Simulate stage time breach; confirm escalation chain; candidate feedback digest generated |

---

### Phase 4 — Interview, Follow-Up, Sync & Document Vault (Sprints 8–9)

**Duration:** 2 weeks
**Goal:** Candidate follow-up, document vault, live sync, and interview outcome logging

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S8 | Week 9 | Document vault (upload, tiered access, candidate notifications, access log); interest confirmation flow; structured interview brief generation (Gemini); interview outcome logging; candidate live sync (new resume/details → re-embed → pool re-rank) | Upload document; confirm tier access control; submit interview outcome; update resume and confirm re-rank |
| S9 | Week 10 | CRM: call logging, task management, WhatsApp/email notifications; candidate stage change notifications; post-placement re-engagement cadence setup; gamification (progress bar, badges) | End-to-end candidate follow-up cycle; task auto-created on call; notification delivered |

---

### Phase 5 — Invoicing, Analytics & Admin (Sprint 10)

**Duration:** 1 week
**Goal:** Invoice generation, finance dashboard, analytics dashboards, admin config UI

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S10 | Week 11 | Invoice generation (WeasyPrint PDF, auto-triggered on joining event); invoice tracking (Raised/Sent/Paid/Overdue); retention clock + retention invoice trigger; finance dashboard; ops/AM/recruiter analytics dashboards; admin config UI (K, P, email accounts, portal credentials) | Log candidate joining → invoice generated → emailed; retention clock visible; analytics dashboards live |

---

### Phase 6 — Beta Hardening & AWS Deployment (Sprints 11–12)

**Duration:** 2 weeks
**Goal:** Production-ready, deployed to AWS, open for user login and testing

| Sprint | Duration | Deliverables | Demo |
|--------|----------|-------------|------|
| S11 | Week 12 | Security hardening (TLS, JWT expiry, rate limiting, DPDP consent UI, audit log); performance testing (50 concurrent users); bug fixes; data migration scripts; `.env.prod` and AWS configuration | Load test with 50 concurrent users; confirm all security controls active |
| S12 | Week 13 | AWS deployment (ECS Fargate or EC2 + S3 + RDS/DocumentDB option); CI/CD pipeline (GitHub Actions); DNS and SSL; user onboarding for beta testers; monitoring setup (CloudWatch or Grafana) | Beta URL live; all 5 roles login and perform core flows; client demo on production URL |

---

### Post-Beta — Version 2 Features (Phase 2 Product)

The following are explicitly deferred to v2 of the product (post-beta validation):

- Verified profile system (employment, education, credential, identity verification)
- Freelance interviewer marketplace
- Native video interview engine (replaces Meet/Zoom)
- Gamification credit system and additional batch credits
- Retainer billing model for high-volume clients
- GCC market entry (compliance, Arabic language, data residency)
- KPI dashboards for recruiters; client ratings (internal); recruiter ratings by client and HOD
- Data intelligence products (salary benchmarking, attrition risk, skill gap reports)

---

## 27. Success Metrics

### Candidate Metrics

| Metric | Target |
|--------|--------|
| Profile completion rate (internal pool) | > 70% reach minimum matching threshold |
| Time-to-first-match | < 48h from ingestion to first JD pool appearance |
| Feedback engagement rate | > 40% of candidates act on Why-Not-Selected feedback |
| Post-placement retention (6 months) | > 80% of placed candidates still in role |

### Recruiter & Client Metrics

| Metric | Target |
|--------|--------|
| Time-to-hire | < 21 days (Healthcare/BFSI beachhead) |
| Batches-to-shortlist | < 3 batches average |
| Closure rate (90-day window) | 100% of opened roles reach a closed status |
| Offer acceptance rate | > 70% |
| Rejection reason quality | > 90% structured (not free-text only) |
| 6-month placement retention | > 75% |

### System Metrics

| Metric | Target |
|--------|--------|
| Matching accuracy | > 60% of Batch 1 candidates shortlisted by Batch 2 |
| Internal pool hit rate | > 70% of JDs satisfied from internal pool (K met without external sourcing) |
| Pipeline velocity | Average time per stage trending down quarter-on-quarter |
| Compliance audit pass rate | 100% of data access events have logged consent |
| Invoice collection rate | > 90% invoices paid within 30 days |

---

## 28. The Destination

> **"Get me a JobOS verified candidate."**
>
> When hiring managers across India, the GCC, Southeast Asia, and the United States give this instruction as a matter of course — not as a request that needs explaining — the gold standard has shifted. JobOS has become a verb. The resume is legacy. The verified, structured, intelligence-rich profile is the new unit of hiring.

---

*JobOS — Recruitment Operating System  |  PRD Version 2.0  |  Confidential  |  Fidelitus Corp  |  April 21, 2026*

*This is a living document. Every update must be versioned and dated. Sections marked OUT OF SCOPE are explicitly excluded from the current build cycle and must not be re-introduced without a formal scope change.*
