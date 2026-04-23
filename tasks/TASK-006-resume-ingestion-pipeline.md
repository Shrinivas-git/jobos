# TASK-006: Resume Ingestion Pipeline
**Status:** COMPLETED
**Priority:** High
**Phase:** Phase 1 — JD Intake, Resume Pool & Semantic Matching
**Sprint:** 2

## Description
Develop the end-to-end pipeline for resume ingestion. This includes file storage, text extraction from PDF/DOCX, vector embedding via Gemini, and metadata storage in MongoDB and Qdrant.

## Deliverables
- [x] Resume file store logic with versioning support.
- [x] Text extraction service using `pdfplumber` and `python-docx`.
- [x] Gemini `text-embedding-004` integration for resume vectors.
- [x] Vector upsert into Qdrant `resume_vectors` with payload.
- [x] Bulk import UI for initial internal pool seeding.

## PRD References
- Section 5 (Resume Database & Vector Store)
- Section 26.2 (Sprint 2)

## Verification Plan
- [x] Upload multiple resumes and verify file store versioning.
- [x] Confirm successful vectorization and metadata storage in Qdrant.
- [x] Verify candidate record creation in MongoDB.
