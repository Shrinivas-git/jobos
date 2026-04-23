# TASK-012: Inbound Resume Routing
**Status:** TODO
**Priority:** Medium
**Phase:** Phase 2 — External Sourcing & Obfuscated Posting
**Sprint:** 5

## Description
Develop the logic to automatically route inbound resumes received via email to the correct JD candidate pools. The system should identify the target JD-ID or match the resume against all open JDs.

## Deliverables
- [ ] Email Watcher extension for resume intake polling.
- [ ] JD-ID extraction logic from email subject/body.
- [ ] Auto-matching logic for inbound resumes against open JDs.
- [ ] Logic to update candidate pools and notify managers of new matches.

## PRD References
- Section 15.2 (Inbound Resume Auto-Routing Flow)
- Section 26.3 (Sprint 5)

## Verification Plan
- [ ] Send resume to intake address with JD-ID and verify routing.
- [ ] Send resume without JD-ID and verify matching against all open JDs.
- [ ] Confirm Manager receives notification for new high-scoring matches.
