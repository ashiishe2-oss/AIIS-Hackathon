# AIIS Backend V2 (Arogya Infrastructure Intelligence System)

Welcome to **AIIS Backend V2** — a production-grade, modular Flask architecture engineered for emergency healthcare operations, hospital capacity tracking, intelligent dispatch matching, and normal outpatient healthcare workflows.

---

## Architecture Overview

AIIS Backend V2 adheres to a strict layered design pattern separating HTTP transport, domain business logic, data access, schema validation, and cross-cutting concerns:

```
Request ──> Middleware (Auth / RBAC / Validation)
                 │
                 ▼
         Routes (Blueprints)
                 │
                 ▼
          Service Layer (Business Logic & Orchestration)
                 │
                 ▼
        Repositories Layer (Data Access & Persistence)
                 │
                 ▼
    Database (Supabase PostgreSQL / External APIs)
```

### Layer Responsibilities

- **`routes/`**: Handles HTTP endpoints, query parameter parsing, request dispatching, and response formatting. Contains minimal controller logic.
- **`services/`**: Encapsulates all domain business logic, workflow rules (e.g., patient SOS dispatching, hospital matching algorithms, appointment scheduling).
- **`repositories/`**: Isolates all database access code and Supabase queries. Decouples business logic from persistence implementation with thread-safe fallbacks.
- **`schemas/`**: Defines data structures, payload schemas, and validation contracts.
- **`middleware/`**: Cross-cutting HTTP filters including authentication, role-based authorization, and request body validation.
- **`utils/`**: Reusable utilities for standardized response envelopes, custom exception hierarchies, and coordinate/contact validators.
- **`tests/`**: Automated pytest test suite covering application initialization, health endpoints, emergency workflows, auth/RBAC, and Stage 4 APIs.

---

## Completed Development Stages

### Stage 1: Emergency SOS Foundation (Completed & Verified)
- Public emergency facility discovery (`GET /api/emergency/search` by GPS radius or city).
- Capability-based hospital ranking and emergency casualty contact details.
- Guest Emergency SOS broadcast (`POST /api/emergency/sos`) with cryptographic tracking token.
- Arrival verification (`POST /api/emergency/verify-arrival`) via 6-digit OTP desk verification.
- Emergency cancellation (`POST /api/emergency/cancel`) with audit event logging.
- Prominent 112 emergency helpline escalation indicators across all responses.

### Stage 2: Database Architecture (Completed & Verified)
- Comprehensive schema migrations (001–011) covering:
  - `profiles`, `hospitals`, `hospital_capabilities`, `hospital_capacity`, `hospital_capacity_history`,
  - `emergency_requests`, `emergency_request_events`, `hospital_request_responses`,
  - `hospital_departments`, `hospital_equipment`, `appointments`.
- Row-Level Security (RLS) policies and triggers (`trg_archive_capacity_history`, `updated_at`).
- Non-destructive additive migration `011_add_email_to_profiles.sql` with metadata fallback.

### Stage 3: Authentication and RBAC (Completed & Verified)
- Supabase Auth integration (`auth.admin.create_user`) with service role management.
- Dual token verification supporting asymmetric Supabase JWTs and HS256 local sessions.
- Strict Role-Based Access Control: `patient`, `hospital_admin`, `authority`, `platform_admin`.
- Self-escalation prevention on public registration (rejects authority/admin requests).
- Hospital administrator approval lifecycle (`pending_approval` until vetted).
- Cross-hospital tenant boundary enforcement (`@require_hospital_access`).

### Stage 4: Normal Healthcare APIs (Completed & Verified)
- **Hospital Discovery**: `GET /api/hospitals` (city, search, specialty, GPS proximity, pagination).
- **Facility Profile**: `GET /api/hospitals/<id>` (hydrates departments, equipment, verified capabilities).
- **Department Network**: `GET /api/departments` and `GET /api/hospitals/<id>/departments`.
- **Honest Capacity Classification**: Labeled as `"seeded_baseline"` with `"verified_realtime": false`.
- **Outpatient Appointment Booking**: `POST /api/appointments` (rejects past dates, binds patient ID).
- **Patient History**: `GET /api/appointments/me` (isolated strictly to authenticated patient).
- **Appointment Detail**: `GET /api/appointments/<id>` (ownership and hospital admin RBAC isolation).
- **Citizen Cancellation**: `POST /api/appointments/<id>/cancel`.
- **Hospital Admin Appointment Management**:
  - `GET /api/hospital/<id>/appointments` (filtered by status).
  - `GET /api/hospital/<id>/appointments/<id>` (isolated to assigned facility).
  - `PUT /api/hospital/<id>/appointments/<id>/status` (lifecycle: REQUESTED -> CONFIRMED -> COMPLETED).

---

## Active Blueprint Mount Points

| Domain | Blueprint Prefix | Key Endpoints | Description |
|---|---|---|---|
| Health Check | `/api/health` | `GET /api/health` | Operational health and readiness checks |
| Emergency | `/api/emergency` | `POST /search`, `POST /sos`, `GET /status/<token>`, `POST /verify-arrival`, `POST /cancel` | Citizen emergency SOS and tracking |
| Locations | `/api/locations` | `GET /api/locations` | Network city centers and coordinates |
| Hospitals | `/api/hospitals` | `GET /api/hospitals`, `GET /<id>`, `GET /<id>/departments` | Public facility discovery & details |
| Departments | `/api/departments` | `GET /api/departments` | Network-wide distinct departments |
| Appointments | `/api/appointments` | `POST /`, `GET /me`, `GET /<id>`, `POST /<id>/cancel` | Citizen OPD consultations |
| Hospital Admin | `/api/hospital` | `GET /<id>/requests`, `PUT /<id>/capacity`, `GET /<id>/appointments`, `PUT /<id>/appointments/<id>/status` | Hospital operational casualty management |
| Authentication | `/api/auth` | `POST /register`, `POST /login`, `GET /me`, `POST /logout` | Identity and RBAC access control |

---

## Running Tests

Execute the full suite of 70 automated integration and unit tests:

```bash
python -m pytest backend_v2/tests -v
```

All 70 tests pass with 0 failures across both workspaces:
1. `c:\Users\ashii\OneDrive\Desktop\baackendv2\backend_v2` (Authoritative)
2. `c:\Users\ashii\OneDrive\Desktop\HACKATHON\AROGYA- HACKATHON\backend_v2` (Synchronized Mirror)
