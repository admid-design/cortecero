# Changelog

All notable changes to this project are documented in this file.

## [0.3.0] - 2026-03-30

R4 closure release, including the full R3 operational planning track and R4 weight/vehicle/capacity track.

### Added
- R3 operational planning capabilities:
  - `orders.intake_type` classification (`new_order` / `same_customer_addon`).
  - Pending Queue endpoint and UI with deterministic ordering and tenant isolation.
  - Source metrics endpoint and UI by `source_channel`.
  - Manual auto-lock run endpoint and UI action with idempotent behavior.
- R4 load and vehicle capabilities:
  - `orders.total_weight_kg` persistence and operational editing endpoint/UI.
  - Plan-level derived weight aggregation in backend and plans UI.
  - Tenant-safe vehicle assignment model (`vehicles` + `plans.vehicle_id`) and assignment endpoint/UI.
  - Derived capacity alerts endpoint/UI by `service_date` with `OVER_CAPACITY` and `NEAR_CAPACITY`.
- Automated test coverage for R3/R4 critical paths:
  - intake classification
  - pending queue
  - source metrics
  - auto-lock
  - order weight update
  - plan weight aggregation
  - vehicle schema/assignment
  - capacity alerts

### Changed
- OpenAPI contract expanded to include R3/R4 endpoints and schemas.
- Frontend typed API client expanded to cover all new R3/R4 operational flows.

### Notes
- This release closes R4 scope and is the final baseline before opening R5 work.

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
