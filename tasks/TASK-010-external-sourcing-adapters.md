# TASK-010: External Sourcing Adapters
**Status:** TODO
**Priority:** Medium
**Phase:** Phase 2 — External Sourcing & Obfuscated Posting
**Sprint:** 4

## Description
Build the external sourcing layer to fetch candidates when the internal pool does not meet the K-threshold. This includes adapters for Naukri (API/Scraping) and Unipile (LinkedIn).

## Deliverables
- [ ] Naukri sourcing adapter (Scraper or API).
- [ ] Unipile adapter for LinkedIn profile fetching.
- [ ] Fallback trigger logic linked to K-threshold status.
- [ ] Automatic ingestion of external resumes into the standard pipeline.

## PRD References
- Section 6.3 (Two-Tier Sourcing — Internal First, External Fallback)
- Section 26.3 (Sprint 4)

## Verification Plan
- [ ] Simulate internal pool deficiency and verify external sourcing triggers.
- [ ] Confirm external candidates are correctly vectorized and added to the JD pool.
- [ ] Verify deduplication logic prevents redundant record creation.
