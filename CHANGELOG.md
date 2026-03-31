# Changelog

All notable changes to this project are documented in this file.

## [0.5.0] - 2026-03-31

R6 closure release focused on explainability hardening, historical operational snapshots, resolution workflows, and AI-ready export stability.

### Added
- R6 operational explainability and catalog governance:
  - `operational_reason_catalog` seeded and versioned for stable reason codes.
  - `operational_explanation` in order reads with `reason_category`, `severity`, `rule_version`, `timezone_used`, and `catalog_status`.
- R6 historical traceability:
  - append-only `order_operational_snapshots` with guardrails against updates/deletes.
  - timeline reads and batch snapshot generation endpoint with observable idempotency.
- R6 operational prioritization and analytics surface:
  - `operational-resolution-queue` endpoint with deterministic ordering and strict filters.
  - `exports/operational-dataset` endpoint (JSON/CSV), tenant-safe pagination, and optional anonymization.
- R6 frontend operational coverage:
  - operational explanation signal in orders table.
  - dedicated cards for Pending Queue, Operational Queue, and Operational Resolution Queue.
  - order snapshot timeline card in operational UI.

### Changed
- Timezone hardening (`R6-DB-003`) across DB and API:
  - DB function `is_valid_iana_timezone` plus constraints on `tenants.default_timezone` and `zones.timezone`.
  - invalid existing timezone data normalized during migration before enforcing constraints.
  - `/admin/zones` now rejects invalid timezone writes with `422 INVALID_TIMEZONE`.
- CI/OpenAPI gate aligned to R6 critical contract surface:
  - protects resolution queue, snapshot run, export dataset, and explanation schemas.

### QA / CI
- Temporal QA matrix completed for same-day/cross-midnight/DST behavior.
- Snapshot consistency and batch idempotency tests completed.
- Required checks in green for release commit:
  - `backend-tests`
  - `openapi-check`
  - `frontend-smoke`

### Notes
- This release closes R6 scope and establishes the baseline before opening R7.

## [0.4.0] - 2026-03-31

R5 closure release focused on customer operational governance (profiles, operational exceptions, derived operational signals/queues, and plan customer consolidation), with QA/CI hardening.

### Added
- R5 data model and migrations:
  - `customer_operational_profiles`
  - `customer_operational_exceptions`
  - operational evaluation indexes for efficient derived reads
- R5 backend APIs:
  - Customer operational profile (`GET/PUT`) with explicit timezone/window semantics
  - Customer operational exceptions (`GET/POST/DELETE`) with conflict-safe constraints
  - Derived operational state/reason in order reads
  - Operational queue endpoint with deterministic ordering and explicit filter contract
  - Plan customer consolidation endpoint (read-only derived aggregation)
- R5 frontend operational/admin coverage:
  - Admin customer operational profile panel
  - Admin customer operational exceptions panel
  - Operational signal in orders (`operational_state`/`operational_reason`)
  - Operational Queue view with contract-faithful filters
  - Plan customer consolidation view (read-only)
- CI hardening for R5:
  - `frontend-smoke` workflow (`npm run build`)
  - OpenAPI surface assertions for mandatory R5 paths/schemas

### Changed
- OpenAPI contract expanded and synchronized for all R5 endpoints/schemas.
- Frontend typed API client expanded for full R5 coverage.
- Error contract reinforced for R5 filter validation (`INVALID_OPERATIONAL_FILTER`).

### Notes
- This release closes R5 scope and establishes the baseline before opening R6.

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
