# TASK-022: Retention Clock & Finance
**Status:** DONE
**Priority:** Medium
**Phase:** Phase 5 — Invoicing, Analytics & Admin
**Sprint:** 10

## Description
Implement the retention clock for placed candidates and the automated triggers for retention invoices. This ensures that long-term placement value is captured.

## Deliverables
- [ ] Retention clock logic (start on joining date).
- [ ] Automated retention invoice trigger (180 days post-joining).
- [ ] 90-day guarantee period monitoring and auto-replacement search trigger.
- [ ] Celery Beat tasks for retention clock monitoring.

## PRD References
- Section 10.1 (Invoice Triggers)
- Section 10.3 (Payment Tracking)

## Verification Plan
- [ ] Verify retention clock starts correctly for a new hire.
- [ ] Simulate 180-day passage and verify retention invoice trigger.
- [ ] Confirm replacement search is flagged if candidate exits within 90 days.
