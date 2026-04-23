# TASK-004: JD Intake Engine
**Status:** COMPLETED
**Priority:** High
**Phase:** Phase 1 — JD Intake, Resume Pool & Semantic Matching
**Sprint:** 1

## Description
Implement the dual ingestion engine for Job Descriptions (JDs). This includes the Email Watcher service for IMAP polling and the Recruiter Web Form for manual submission.

## Deliverables
- [x] Email Watcher service (Python) implemented with real IMAP polling.
- [x] Recruiter web form in `Jobs.tsx` with dual mode (Upload & Structured Form).
- [x] Logic to identify/create client (domain-based) and assign `JD-ID`.
- [x] Automated folder structure creation for new JDs (`/data/clients/<slug>/<jd_id>/raw`).
- [x] Storage of raw JD files, structured `jd.json`, and metadata in MongoDB.

## PRD References
- Section 4 (JD Intake — Dual Ingestion Engine)
- Section 15.1 (JD-to-Candidate-Pool Flow)
- Section 26.2 (Sprint 1)

## Verification Plan
- [x] Send email with attachment and verify folder/record creation.
- [x] Submit form via UI and verify identical output structure.
- [x] Verify client mapping logic works for known/unknown senders.
