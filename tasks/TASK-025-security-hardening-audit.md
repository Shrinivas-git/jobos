# TASK-025: Security Hardening & Audit
**Status:** TODO
**Priority:** High
**Phase:** Phase 6 — Beta Hardening & AWS Deployment
**Sprint:** 11

## Description
Perform security hardening of the entire JobOS stack. This includes enforcing strict TLS, JWT expiry policies, rate limiting, and ensuring DPDP compliance for data handling and consent.

## Deliverables
- [ ] TLS 1.3 enforcement and HSTS headers.
- [ ] JWT expiry and refresh token rotation policies.
- [ ] Rate limiting (WAF and API layer).
- [ ] DPDP consent UI and right-to-erasure workflow.
- [ ] Comprehensive audit logging for all data access events.

## PRD References
- Section 19 (Security, Privacy & Compliance)
- Section 20 (Authentication, Authorisation & Session Management)
- Section 26.7 (Sprint 11)

## Verification Plan
- [ ] Run security scan and verify zero critical findings.
- [ ] Confirm consent is captured before document access.
- [ ] Verify audit log captures actor, action, and timestamp for all edits.
