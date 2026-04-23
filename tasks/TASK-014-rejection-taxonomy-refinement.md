# TASK-014: Rejection Taxonomy & Refinement
**Status:** TODO
**Priority:** Medium
**Phase:** Phase 3 — Recruiter Pipeline, Batch Model & Closure Engine
**Sprint:** 6

## Description
Implement the structured rejection reason taxonomy and the logic to refine future batches based on recruiter feedback. This creates a learning loop for the matching engine.

## Deliverables
- [ ] Rejection reason taxonomy (Skills gap, Salary, etc.) in the UI.
- [ ] Logic to capture and store structured rejection data in MongoDB.
- [ ] Batch refinement logic: adjust weights or filters for the next batch.
- [ ] Monitoring for "JD clarity issue" to flag ops intervention.

## PRD References
- Section 6.6 (Rejection reason taxonomy)
- Section 18.2 (Objective Decision Enforcement)
- Section 26.4 (Sprint 6)

## Verification Plan
- [ ] Verify mandatory reason field on rejection.
- [ ] Confirm next batch candidates differ based on previous rejection signals.
- [ ] Trigger "JD clarity" flag after 3 batches of such rejections.
