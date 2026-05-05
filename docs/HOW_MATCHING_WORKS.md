# How JobOS Matching Works
**Audience: HR, Recruiters, and Hiring Managers**

When you upload a Job Description, JobOS automatically finds and ranks the best-fit candidates from the talent pool. This happens in two back-to-back stages — a fast search that narrows the field, followed by a deep AI review of each shortlisted candidate.

---

## Stage 1 — Vector Search (The Speed Filter)

### What happens
Every resume and every JD in the system is converted into a numerical fingerprint called a **vector**. Think of it like a unique DNA profile for text — two pieces of text that talk about similar topics will have vectors that are close to each other. JobOS uses a model called **all-MiniLM-L6-v2** (a lightweight, offline AI model) to generate these fingerprints.

When you trigger matching for a JD, the system:
1. Takes the JD's vector and compares it against every resume vector in the database
2. Produces a **similarity score** between 0 and 1 for each candidate (1 = identical topic, 0 = completely unrelated)
3. Drops anyone whose score is below the minimum threshold

### The threshold
- **Minimum similarity score (p-threshold): 0.15**
- Any candidate scoring below 0.15 is eliminated immediately — they are too far off-topic to be worth deeper review
- The system searches the top 50 closest candidates and then applies this filter
- After filtering, **at most the top 20 candidates** are passed on to Stage 2

### The sourcing safety net (k-threshold)
- **Minimum acceptable candidates: 10**
- If fewer than 10 candidates survive the similarity filter, the system automatically flags the JD as needing **external sourcing** (e.g., posting to Naukri or LinkedIn)
- This tells the team: "Our internal pool does not have enough people for this role — go find more"

### What this stage does NOT do
Stage 1 does not read or understand the resume. It only compares the overall topic similarity of the two documents. A resume about Python development and a JD about Python development will score well together even if the candidate is missing specific skills — that nuance is handled in Stage 2.

---

## Stage 2 — Groq AI Reasoning (The Deep Review)

### What happens
Each candidate who passed Stage 1 is sent to a large language model — **Llama 3.3 70B** (running on Groq) — for a full human-like evaluation. This is the most important part of the scoring.

The AI receives two things:
1. The full structured JD (title, skills required, experience required, responsibilities, preferences, etc.)
2. The candidate's full resume text (up to 12,000 characters — roughly 6–8 pages)

### What the AI is asked to produce
The AI is given these exact instructions every time:

- **Fitment Score (0–100):** A base score representing how well the candidate fits the role, ignoring company background and team size context. This is the AI's core judgment.
- **Reasoning:** One concise paragraph explaining the overall assessment.
- **Strengths (exactly 5):** Five specific things the candidate brings that match the role — each backed by evidence from the resume. Not general praise; specific observations like "Led a team of 8 engineers at IBM for 3 years, directly relevant to the team lead requirement."
- **Gaps (exactly 5):** Five specific things the candidate is missing or weak on, and why each gap matters for this particular role.
- **Recommendation:** One of three outcomes — `shortlist`, `hold`, or `reject`.
- **Context Bonus (0–15 points):** Additional points based on cultural and structural fit (explained below).

### What "Strengths" and "Gaps" mean in practice
- **Strengths** are not just skill matches — the AI is instructed to cite specific evidence from the resume. A strength is only counted if the resume actually demonstrates it.
- **Gaps** are role-specific. A gap is something this JD specifically needs that the candidate cannot demonstrate. The same candidate might have no gaps for one role and three gaps for another.
- Use the 5 strengths and 5 gaps as your starting point for interview question design — the gaps are ready-made probing areas.

---

## The Composite Score Formula

After Stage 2 completes, a single **Composite Score** is calculated for each candidate. This is the number used to rank candidates on the matching results page.

```
Composite Score = (Fitment Score × 65%) + (Similarity Score × 20%) + (Profile Completeness × 10%) + (Context Bonus × 5%)
```

### What each component means

**Fitment Score — 65% of the total**
- The AI's direct judgment of how well the candidate fits the role
- Scored 0–100 by Groq's reasoning model
- This is the dominant factor — it carries the most weight because it reflects actual job-fit reasoning, not just topic overlap
- Example: An AI fitment score of 75 contributes 48.75 points to the final score

**Similarity Score — 20% of the total**
- The Stage 1 cosine similarity score, converted to a 0–100 scale
- Represents how closely the resume text overlaps with the JD text at a topic level
- Example: A similarity score of 0.45 (45 after conversion) contributes 9 points

**Profile Completeness — 10% of the total**
- Measures how filled-in the candidate's profile is in the system
- Six fields are checked: name, email, phone, skills list, years of experience, and location
- A fully complete profile (all 6 filled) scores 100; missing 2 fields scores 67
- Example: A completeness score of 80 contributes 8 points
- Practically, this slightly penalises candidates whose resumes were poorly parsed — it is not a reflection of their quality as candidates

**Context Bonus — 5% of the total**
- The raw context bonus points (0–15) at a 5% weight
- Example: A context bonus of 10 contributes 0.5 points
- This is intentionally a small tiebreaker, not a major ranking factor

### A worked example

Imagine a candidate with these scores:
- Groq AI fitment: 75 out of 100
- Stage 1 similarity: 0.45 (converted to 45)
- Profile completeness: 5 of 6 fields filled = 83
- Context bonus: 10 (company type + team size match)

```
Composite = (75 × 0.65) + (45 × 0.20) + (83 × 0.10) + (10 × 0.05)
          =  48.75       +  9.00        +  8.30        +  0.50
          =  66.55
```

This candidate would rank above anyone scoring below 66.55 and below anyone scoring higher.

---

## Contextual Bonus — The Cultural Fit Add-On

The context bonus (0–15 points) rewards candidates whose career background structurally matches what the client is looking for. It is calculated by the AI during Stage 2 using data extracted from the candidate's resume.

There are three components, each worth 5 points:

### Company Type Match (+5 points)
- The system knows what kinds of companies each candidate has worked at (e.g., Fintech, Startup, Large Enterprise, Product company, Services company)
- If the JD specifies a preferred company type and the candidate has worked at a matching type, they earn 5 points
- Example: JD prefers "Fintech" candidates. Candidate worked at Razorpay (Fintech) and Infosys (Services). They earn the 5 points because Fintech is present.
- If the JD has no company type preference (set to "Any"), this bonus is not applied — it would be unfair to score candidates down for something the client doesn't care about

### Team Size Match (+5 points)
- The system estimates what size of team the candidate typically worked in, based on their resume
- Team size bands: Small (1–15), Medium (16–50), Large (51–200), Enterprise (200+)
- If the JD specifies a preferred team size and the candidate's typical team size matches, they earn 5 points
- Example: JD prefers "Large (51–200)" teams. Candidate's resume indicates they led teams of ~100 people. They earn the 5 points.

### Role Type Match (+5 points)
- The system classifies each candidate's work style based on their history
- Categories: Individual Contributor, 50% IC + 50% Management, Team Lead
- If the JD specifies a role type and the candidate's classification matches, they earn 5 points
- Example: JD needs a "Team Lead". Candidate's resume shows they managed and mentored teams across multiple roles. They earn the 5 points.

**Important:** All three bonuses are optional. If the JD has no preference for a field (left as "Any"), that bonus is skipped entirely for all candidates. This keeps the comparison fair.

---

## What HR Should Consider Adding

The current model is a strong baseline. Below are four improvements that would meaningfully increase ranking accuracy, based on common friction points in recruitment.

### 1. Notice Period Weighting
**The problem today:** A candidate who can join in 15 days and one who needs 90 days rank identically. For urgent roles, this matters enormously.

**What to add:** A score penalty (or boost) based on the gap between the candidate's notice period and the JD's hiring timeline.
- Example: JD is marked "Immediate" or "Critical." Candidate has 90-day notice. Deduct 10–15 points from their composite score.
- Example: JD has no urgency preference. No penalty applied.
- The penalty should scale with urgency — Critical roles penalise long notice periods more than Low urgency roles.

### 2. Location Preference Scoring
**The problem today:** The system collects the candidate's location and the JD's location but does not use them in scoring. A Bangalore-based candidate and a Delhi-based candidate rank the same for a Bangalore In-office role.

**What to add:** A location match score based on city/region alignment.
- Exact city match → no penalty
- Same state, different city → small penalty (3–5 points)
- Different region entirely → larger penalty (8–12 points), especially for In-office or Hybrid roles
- Remote roles → no location penalty at all
- This would make location a meaningful tiebreaker for in-office mandates.

### 3. Salary Expectation Gap Penalty
**The problem today:** Compensation data is captured on the JD side (compensation range) but the candidate's current CTC and expected CTC are not extracted from resumes. Matching can surface a great candidate who is significantly over-budget.

**What to add:** Extract expected salary from resumes or ask candidates to self-report it during profile creation. Then apply a penalty when the gap exceeds a threshold.
- Example: JD budget is 15–20 LPA. Candidate expects 30 LPA. Deduct points or flag as "budget mismatch" even if fitment is high.
- This saves recruiters time spent on candidates who will decline anyway.

### 4. Experience Gap Penalty
**The problem today:** The AI considers experience qualitatively in its fitment score, but there is no hard numerical check. A candidate with 2 years of experience can score well on a role requiring 8 years if their resume reads well.

**What to add:** A structured experience gap calculation comparing the JD's required years against the candidate's actual years.
- Zero gap → no change
- Slight under (1–2 years short) → small penalty (3–5 points), flagged as "slightly under-experienced"
- Significant under (3+ years short) → larger penalty (10–15 points), flagged as "experience gap"
- Slight over (3–5 years excess) → no penalty; senior candidates can still be good fits
- Large over (8+ years excess) → small penalty, flagged as "potentially overqualified" for the recruiter to consider
- This adds a transparent, auditable rule on top of the AI's qualitative judgment.

---

## Quick Reference

| What | How | Weight |
|---|---|---|
| AI fit judgment | Groq Llama 3.3 70B reads full JD + resume | 65% |
| Topic overlap | all-MiniLM-L6-v2 vector similarity | 20% |
| Profile completeness | 6 basic fields filled in | 10% |
| Cultural/structural fit | Company type + team size + role type | 5% (max +0.75 pts) |

| Threshold | Value | Meaning |
|---|---|---|
| Minimum similarity to enter shortlist | 0.15 | Below this = automatically excluded |
| Minimum candidates before external sourcing | 10 | Below this = JD flagged for Naukri/LinkedIn |
| Maximum candidates sent to AI | 20 | Top 20 from Stage 1 go to Stage 2 |
| Context bonus maximum | 15 raw points | Company + team + role type all match |
