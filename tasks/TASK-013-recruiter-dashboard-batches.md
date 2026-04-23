# TASK-013: Recruiter Dashboard & Batches
**Status:** TODO
**Priority:** High
**Phase:** Phase 3 — Recruiter Pipeline, Batch Model & Closure Engine
**Sprint:** 6

## Description
Build the recruiter-facing dashboard and the 3-batch candidate review model. Recruiters should be able to see their assigned JDs and work through candidate batches systematically.

## Deliverables
- [ ] Recruiter dashboard showing assigned JDs and pipeline status.
- [ ] 3-batch model UI: display top 3 candidates with match summaries.
- [ ] Action controls: Shortlist or Reject with mandatory reason.
- [ ] Logic to release subsequent batches upon rejection.

## PRD References
- Section 6.6 (The 3-Batch Model)
- Section 26.4 (Sprint 6)

## Verification Plan
- [ ] Verify recruiter sees only assigned JDs.
- [ ] Confirm Batch 1 loads correctly with top 3 candidates.
- [ ] Verify next batch is released only after the current batch is fully reviewed.
