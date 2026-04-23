# TASK-001: Auth Keycloak Setup
**Status:** TODO
**Priority:** High
**Phase:** Phase 0 — Infrastructure & Foundation
**Sprint:** 0

## Description
Configure Keycloak as the central identity provider. Setup the `jobos` realm, define roles (Candidate, Recruiter, Manager, HOD, Admin), and integrate with the FastAPI backend using JWT middleware for RBAC enforcement.

## Deliverables
- [x] Keycloak realm `jobos` configured with OIDC.
- [x] Roles and groups created (candidates, recruiters, managers, hod, ops-admins).
- [x] FastAPI JWT middleware for token validation (RS256).
- [ ] Social login (Google OAuth) configured for Candidates. (Note: Realm and clients ready, Google Client ID/Secret needed for full config)
- [x] Initial Admin user and test users for each role.

## PRD References
- Section 13.3 (Authentication & Login)
- Section 20 (Authentication, Authorisation & Session Management)

## Verification Plan
- [x] Successful login via Keycloak UI and token issuance.
- [x] Verify API endpoints return 401 without token and 403 for unauthorized roles.
- [x] Confirm JWT claims correctly map to JobOS roles.
