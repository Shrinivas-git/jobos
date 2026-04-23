# TASK-002: Data Model Bootstrap
**Status:** TODO
**Priority:** High
**Phase:** Phase 0 — Infrastructure & Foundation
**Sprint:** 0

## Description
Initialize the primary data stores. This involves creating the necessary MongoDB collections and Qdrant collections with correct schemas and vector dimensions for JobOS.

## Deliverables
- [x] MongoDB collections initialized (`users`, `clients`, `job_descriptions`, `candidates`, `candidate_pools`, `pipeline_stages`, `batches`, `rejections`, `invoices`, `tasks`, `documents`, `notifications`, `calls`, `audit_log`, etc.).
- [x] Qdrant collection `resume_vectors` created (768-dim for Gemini `text-embedding-004`).
- [x] Qdrant collection `jd_vectors` created (768-dim).
- [x] Database seeding script for development environment.

## PRD References
- Section 14 (Data Model)
- Section 26.1 (Phase 0)

## Verification Plan
- [ ] Verify all MongoDB collections are visible via MongoDB Compass or shell.
- [ ] Verify Qdrant collections are created with correct vector parameters.
- [ ] Run seed script and verify initial data presence.
