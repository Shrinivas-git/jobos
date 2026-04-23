# TASK-008: Matching Engine Pass 2
**Status:** TODO
**Priority:** High
**Phase:** Phase 1 — JD Intake, Resume Pool & Semantic Matching
**Sprint:** 3

## Description
Implement the "Intelligence Layer" using Gemini 2.5 Pro. This pass performs deep reasoning on the candidates shortlisted in Pass 1, generating fitment scores, strengths, weaknesses, and a final stack rank.

## Deliverables
- [ ] Gemini 2.5 Pro reasoning logic for candidate evaluation.
- [ ] Fitment score (0-100) generation with reasoning text.
- [ ] Strengths and gaps extraction relative to the JD.
- [ ] `match_score.json` and `pointer.json` generation in JD folders.
- [ ] Composite match score calculation (Gemini + cosine + completeness).

## PRD References
- Section 6.1 (Pass 2 — Intelligence Layer)
- Section 26.2 (Sprint 3)

## Verification Plan
- [ ] Verify `match_score.json` contains detailed reasoning and scores.
- [ ] Confirm stack rank order reflects Gemini's evaluation.
- [ ] Validate composite score weighting against `config.yaml`.
