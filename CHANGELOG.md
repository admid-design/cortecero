# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] - 2026-03-30

R2 closure release, including post-merge P1 fix and auth/deprecations cleanup.

### Added
- Tenant-scoped admin APIs for zones, customers, users, and tenant settings.
- Frontend Admin section for zones, customers, users, and tenant settings using typed API client.
- CI required checks for pull requests: `backend-tests` and `openapi-check`.
- R1/R2 critical automated tests across auth, ingestion, plans, exceptions, audit, and admin flows.

### Changed
- R1 fixes merged into `main` as baseline for R2 closure.
- OpenAPI contract updated to keep backend/frontend behavior aligned.
- Login and auth stack hardened while preserving JWT/RBAC/API behavior.

### Fixed
- Migration bootstrap path resolution in backend startup flow.
- Ingestion semantics to preserve immutable order fields used for lateness decisions.
- Tenant-aware login behavior.
- Real IANA validation for `tenant.default_timezone` writes.

### Security
- Replaced deprecated auth dependencies:
  - removed `passlib[bcrypt]`
  - removed `python-jose[cryptography]`
  - adopted `bcrypt` + `PyJWT`

### Notes
- This release corresponds to the full R2 closure approved for merge and stabilized in `main`.

## [0.1.0] - 2026-03-28

Initial R1 scaffold and core domain foundations.

- Multi-tenant base model.
- Core entities: orders, plans, exceptions, audit logs.
- Initial OpenAPI and SQL migration baseline.
