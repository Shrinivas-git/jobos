# TASK-018: Candidate Live Sync
**Status:** TODO
**Priority:** High
**Phase:** Phase 4 — Interview, Follow-Up, Sync & Document Vault
**Sprint:** 8

## Description
Implement the live sync mechanism to update candidate profiles and vectors whenever new information is received. This ensures that all active JD pools are re-evaluated based on the latest signal.

## Deliverables
- [ ] Trigger logic for profile/vector updates on new resume upload.
- [ ] Automated re-embedding and Qdrant upsert for updated candidates.
- [ ] Re-evaluation logic for all active JD pools containing the updated candidate.
- [ ] Manager notification for significant stack-rank shifts.

## PRD References
- Section 5.4 (Live Sync — Profile & Vector Updates)
- Section 15.3 (Candidate Update Flow)

## Verification Plan
- [ ] Upload a new resume version and verify Qdrant vector updates.
- [ ] Confirm match scores are recalculated in active JD pools.
- [ ] Verify notification triggers if rank changes beyond the threshold.
