# TASK-019: CRM Message Approval
**Status:** TODO
**Priority:** Medium
**Phase:** Phase 4 — Interview, Follow-Up, Sync & Document Vault
**Sprint:** 9

## Description
Develop the CRM messaging system where all outbound communication is Gemini-drafted and human-approved. This includes the message approval queue for recruiters and account managers.

## Deliverables
- [ ] Gemini 2.5 Pro drafting logic for various message types (stage changes, digests).
- [ ] Message Approval Queue UI for recruiters/AMs.
- [ ] Integration with delivery channels (Email/WhatsApp).
- [ ] Logging of approver identity and timestamp for all sent messages.

## PRD References
- Section 11.2 (Gemini-Drafted Messaging & Human-in-Loop Approval)
- Section 26.5 (Sprint 9)

## Verification Plan
- [ ] Verify Gemini drafts correct context-aware messages.
- [ ] Confirm messages are not sent until approved in the queue.
- [ ] Check audit log for sender and approver details.
