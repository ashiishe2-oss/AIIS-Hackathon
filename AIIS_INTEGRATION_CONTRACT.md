# AIIS — Frontend-to-Backend Integration Contract

**Document Version**: 2.0 (Hackathon Final Round Integration)  
**Target Architecture**: Single-Origin Vanilla JS SPA served by Flask Backend V2  
**Database**: Supabase `romwnlabuhsnxuomhevb` (`aiis2`)  

---

## 1. Overview & Architecture Strategy

The supplied AIIS frontend (`AIIS_FRONTEND_HANDOFF.zip`) is a zero-dependency vanilla HTML/CSS/JavaScript Single Page Application (SPA). It uses hash-based client routing (`#/`, `#/emergency`, `#/planned`, `#/me`, `#/hospital`, `#/sri`, `#/login`, `#/register`, `#/authority`) and issues relative `/api/...` HTTP requests via a centralized `api(path, body, headers)` helper.

### Hosting & Origin Architecture
- **Canonical Port**: `5001` (served by Flask via `backend_v2.app`)
- **Root Assets**: `/` serves `public/index.html`. `/styles.css`, `/app.js`, `/vendor/qrcode.js`, `/manifest.json`, and icons are served from root paths.
- **API Prefix**: All API calls are mapped under `/api/...`.
- **CORS**: Redundant when served from same origin; fully enabled with permissive headers (`Authorization`, `Content-Type`, `X-Tracking-Token`, `X-AIIS-Staff-Code`) for development proxy support (`PORT=8080 AIIS_API_BASE=http://127.0.0.1:5001 npm start`).

---

## 2. API Compatibility Mapping (All 13 Endpoints + Extensions)

### 1. Emergency Hospital Search
- **Frontend Endpoint**: `POST /api/emergency/search`
- **Caller**: `loadEmergency()` in `public/app.js`
- **Request Body**:
  ```json
  {
    "latitude": 12.9716,
    "longitude": 77.5946,
    "category": "general",
    "locationName": "Bengaluru Central"
  }
  ```
- **Backend Route**: `emergency_bp.route("/search", methods=["POST"])` in `backend_v2/routes/emergency.py`
- **Responsible Service**: `EmergencyService.search_emergency_hospitals()`
- **Auth Requirement**: Public (No authentication required)
- **Response Format**:
  ```json
  {
    "success": true,
    "results": [
      {
        "id": 1,
        "name": "Victoria Hospital",
        "partner": true,
        "distanceKm": 2.4,
        "transitMins": 12,
        "emergencyPhone": "+91-800-000-8787",
        "capacity": {
          "emergencyBeds": { "total": 1000, "available": 250 },
          "icuBeds": { "total": 120, "available": 36 }
        },
        "whyRanked": ["Closest public facility (2.4 km straight-line)", "Estimated transit: ~12 mins"]
      }
    ]
  }
  ```
- **Contract Notes**: Returns `results`, `rankedHospitals`, and `hospitals` keys. Each facility record is enriched with `partner: true`, `emergencyBeds`, `icuBeds`, and deterministic identifiers (`hsp-001` / `1`).

---

### 2. Locations Catalog
- **Frontend Endpoint**: `GET /api/locations`
- **Caller**: `loadLocations()` in `public/app.js`
- **Request Body**: None
- **Backend Route**: `locations_bp.route("", methods=["GET"])` in `backend_v2/routes/emergency.py`
- **Responsible Service**: `EmergencyService.get_locations()`
- **Auth Requirement**: Public
- **Response Format**:
  ```json
  {
    "success": true,
    "locations": [
      { "name": "Bengaluru Central", "lat": 12.9716, "lon": 77.5946 },
      { "name": "Mumbai Central", "lat": 18.9696, "lon": 72.8193 }
    ]
  }
  ```

---

### 3. Hospital Facility Details
- **Frontend Endpoint**: `GET /api/hospitals/:id`
- **Caller**: `openDetails(id)` and `loadStaff()` in `public/app.js`
- **Request Params**: `:id` (e.g. `1` or `hsp-001`)
- **Backend Route**: `hospitals_bp.route("/<hospital_id>", methods=["GET"])` in `backend_v2/routes/hospitals.py`
- **Responsible Service**: `HospitalRepository.get_by_id()`
- **Auth Requirement**: Public
- **Response Format**:
  ```json
  {
    "success": true,
    "hospital": {
      "id": 1,
      "name": "Victoria Hospital",
      "address": "Victoria Hospital, Bengaluru",
      "phone": "+91-800-000-8787",
      "partner": true,
      "capacity": {
        "emergencyBeds": { "total": 1000, "available": 250 },
        "icuBeds": { "total": 120, "available": 36 }
      },
      "departments": [
        { "name": "Emergency & Trauma", "status": "Ready" },
        { "name": "Cardiology", "status": "Ready" }
      ],
      "equipment": [
        { "name": "CT Scanner", "status": "Available" },
        { "name": "Ventilator", "status": "Available" }
      ]
    }
  }
  ```

---

### 4. Planned Healthcare Search
- **Frontend Endpoint**: `POST /api/planned/search`
- **Caller**: `planSearch()` and `loadStaff()` in `public/app.js`
- **Request Body**:
  ```json
  {
    "latitude": 12.9716,
    "longitude": 77.5946,
    "specialty": "cardiology",
    "query": ""
  }
  ```
- **Backend Route**: `planned_bp.route("/search", methods=["POST"])` in `backend_v2/routes/planned.py`
- **Responsible Service**: `HospitalRepository.search_by_specialty()`
- **Auth Requirement**: Public
- **Response Format**:
  ```json
  {
    "success": true,
    "results": [
      {
        "id": 1,
        "name": "Victoria Hospital",
        "specialty": "Cardiology",
        "partner": true,
        "matchedServices": [
          { "specialty": "Cardiology", "consultants": 8, "waitDays": 1 }
        ]
      }
    ]
  }
  ```

---

### 5. Emergency Coordination Request ("Tell them I'm coming")
- **Frontend Endpoint**: `POST /api/coordination/request`
- **Caller**: `sendCoordinate(btn)` in `public/app.js`
- **Request Body**:
  ```json
  {
    "hospitalId": "hsp-001",
    "emergencyCategory": "general",
    "estimatedTravelMinutes": 15,
    "userLocationName": "Bengaluru Central"
  }
  ```
- **Backend Route**: `coordination_bp.route("/request", methods=["POST"])` in `backend_v2/routes/emergency.py`
- **Responsible Service**: `EmergencyService.create_sos()`
- **Auth Requirement**: Public (Guest/Anonymous)
- **Response Format (HTTP 201)**:
  ```json
  {
    "success": true,
    "id": "REQ-ABC123",
    "requestId": "REQ-ABC123",
    "tracking_token": "gt_sec_789xyz...",
    "otp": "4821",
    "arrivalOtp": "4821",
    "status": "REQUEST_SUBMITTED",
    "holdExpiresAt": "2026-11-14T06:05:00Z",
    "hospitalName": "Victoria Hospital"
  }
  ```
- **Security Rule**: The 4-digit arrival OTP is returned **strictly once** in this response. The client caches the `tracking_token` in `sessionStorage` and injects `X-Tracking-Token` on subsequent tracking calls.

---

### 6. Emergency Request Status & Polling
- **Frontend Endpoint**: `GET /api/coordination/:id`
- **Caller**: `pollRequest(id)` in `public/app.js` (polled every 3 seconds)
- **Request Headers**: `X-Tracking-Token: <guest_tracking_token>`
- **Backend Route**: `coordination_bp.route("/<request_id>", methods=["GET"])` & `/<request_id>/track` in `backend_v2/routes/emergency.py`
- **Responsible Service**: `EmergencyService.get_sos()`
- **Auth Requirement**: Guest Tracking Token via `X-Tracking-Token` or `Authorization: Bearer <token>`
- **Response Format**:
  ```json
  {
    "success": true,
    "request": {
      "id": "REQ-ABC123",
      "status": "REQUEST_SUBMITTED",
      "hospitalId": "hsp-001",
      "hospitalName": "Victoria Hospital",
      "holdExpiresAt": "2026-11-14T06:05:00Z"
    }
  }
  ```
- **Security Rule**: The response **never** contains the OTP or token hashes.

---

### 7. Emergency Request Cancellation
- **Frontend Endpoint**: `POST /api/coordination/:id/cancel`
- **Caller**: Action `confirm-cancel` in `public/app.js`
- **Request Headers**: `X-Tracking-Token: <token>`
- **Request Body**: `{"reason": "Cancelled by patient"}`
- **Backend Route**: `coordination_bp.route("/<request_id>/cancel", methods=["POST"])` in `backend_v2/routes/emergency.py`
- **Responsible Service**: `EmergencyService.cancel_sos()`
- **Auth Requirement**: Guest Tracking Token
- **Response Format**:
  ```json
  {
    "success": true,
    "request": {
      "id": "REQ-ABC123",
      "status": "CANCELLED"
    }
  }
  ```

---

### 8. Patient Arrival Verification
- **Frontend Endpoint**: `POST /api/coordination/:id/verify-arrival`
- **Caller**: Form `verify` submit in `public/app.js`
- **Request Headers**: `Authorization: Bearer <staff_jwt>`
- **Request Body**: `{"otp": "4821"}`
- **Backend Route**: `coordination_bp.route("/<request_id>/verify-arrival", methods=["POST"])` in `backend_v2/routes/emergency.py`
- **Responsible Service**: `EmergencyService.verify_arrival()`
- **Auth Requirement**: Authenticated Hospital Staff (matching target hospital)
- **Response Format**:
  ```json
  {
    "success": true,
    "request": {
      "id": "REQ-ABC123",
      "status": "PATIENT_ARRIVED"
    },
    "message": "Patient arrival verified successfully."
  }
  ```
- **Security Rule**: Guest tracking tokens are strictly rejected with HTTP 403. Idempotent transitions ensure repeated arrival checks do not alter capacity counts twice.

---

### 9. Appointment Booking Request
- **Frontend Endpoint**: `POST /api/appointments/request`
- **Caller**: `submitBook(form)` in `public/app.js`
- **Request Body**:
  ```json
  {
    "hospitalId": "hsp-001",
    "specialty": "cardiology",
    "preferredDate": "2026-11-20",
    "preferredTimeSlot": "Morning",
    "patientName": "Rohan Verma",
    "patientPhone": "9876543210"
  }
  ```
- **Backend Route**: `appointments_bp.route("/request", methods=["POST"])` in `backend_v2/routes/appointments.py`
- **Responsible Service**: `AppointmentService.create_appointment()`
- **Auth Requirement**: Optional; associates with authenticated patient when logged in.
- **Response Format (HTTP 201)**:
  ```json
  {
    "success": true,
    "data": {
      "id": "apt-998877",
      "hospitalId": "hsp-001",
      "hospitalName": "Victoria Hospital",
      "specialty": "Cardiology",
      "preferredDate": "2026-11-20",
      "preferredTimeSlot": "Morning",
      "status": "REQUESTED"
    }
  }
  ```

---

### 10. Patient Appointment History
- **Frontend Endpoint**: `GET /api/appointments/me` (and legacy alias `GET /api/appointments?phone=...`)
- **Caller**: `refreshAppts()` in `public/app.js`
- **Request Headers**: `Authorization: Bearer <patient_jwt>`
- **Backend Route**: `appointments_bp.route("/me", methods=["GET"])` in `backend_v2/routes/appointments.py`
- **Responsible Service**: `AppointmentService.list_my_appointments()`
- **Auth Requirement**: Authenticated Patient
- **Response Format**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "apt-998877",
        "hospitalId": "hsp-001",
        "hospitalName": "Victoria Hospital",
        "specialty": "Cardiology",
        "preferredDate": "2026-11-20",
        "preferredTimeSlot": "Morning",
        "status": "REQUESTED"
      }
    ]
  }
  ```

---

### 11. Appointment Cancellation
- **Frontend Endpoint**: `POST /api/appointments/:id/cancel`
- **Caller**: Action `cancel-appt` in `public/app.js`
- **Request Headers**: `Authorization: Bearer <patient_jwt>`
- **Request Body**: `{"reason": "Cancelled by patient"}`
- **Backend Route**: `appointments_bp.route("/<appointment_id>/cancel", methods=["POST"])` in `backend_v2/routes/appointments.py`
- **Responsible Service**: `AppointmentService.cancel_appointment()`
- **Auth Requirement**: Owning patient or assigned hospital administrator
- **Response Format**:
  ```json
  {
    "success": true,
    "data": {
      "id": "apt-998877",
      "status": "CANCELLED"
    }
  }
  ```

---

### 12. Hospital Capacity Telemetry Update
- **Frontend Endpoint**: `POST /api/hospitals/:id/capacity`
- **Caller**: `staffPublish(btn)` in `public/app.js`
- **Request Headers**: `Authorization: Bearer <staff_jwt>` (or `X-AIIS-Staff-Code: <code>`)
- **Request Body**:
  ```json
  {
    "emergencyBeds": { "available": 15 },
    "icuBeds": { "available": 4 },
    "departments": [{ "name": "Emergency & Trauma", "status": "Ready" }],
    "equipment": [{ "name": "CT Scanner", "status": "Available" }]
  }
  ```
- **Backend Route**: `capacity_bp.route("/<hospital_id>/capacity", methods=["POST", "PUT"])` in `backend_v2/routes/capacity.py`
- **Responsible Service**: `CapacityService.update_hospital_capacity()`
- **Auth Requirement**: Authenticated Hospital Administrator
- **Response Format**:
  ```json
  {
    "success": true,
    "data": {
      "hospital_id": 1,
      "total_beds": 1000,
      "available_beds": 15,
      "occupied_beds": 735,
      "icu_total": 120,
      "icu_available": 4,
      "icu_occupied": 116,
      "updated_at": "2026-11-14T05:20:00Z"
    }
  }
  ```

---

### 13. Regional SRI (Strain Risk Index)
- **Frontend Endpoint**: `GET /api/sri/regional`
- **Caller**: `loadSri()` in `public/app.js`
- **Request Body**: None
- **Backend Route**: `sri_bp.route("/regional", methods=["GET"])` in `backend_v2/routes/sri.py`
- **Responsible Service**: `SriService.calculate_regional_sri()`
- **Auth Requirement**: Public
- **Response Format**:
  ```json
  {
    "success": true,
    "region": "Karnataka State Health Network",
    "avg_sri": 52.4,
    "risk_band": "Medium",
    "zones": [
      { "zone": "Bengaluru Urban", "sri": 58.2, "level": "Medium" },
      { "zone": "Mysuru", "sri": 42.1, "level": "Medium" },
      { "zone": "Belagavi", "sri": 34.0, "level": "Low" }
    ],
    "hospital_count": 36,
    "generatedAt": "2026-11-14T05:20:00Z"
  }
  ```

---

### 14. User Authentication & Profile Endpoints
- **Register**: `POST /api/auth/register`
  - Body: `{"full_name", "email", "password", "phone", "requested_role", "hospital_id"}`
  - Role rules: Self-registration as `patient` activates immediately. Requesting `hospital_admin` defaults to `pending_approval` unless approved. Self-registration as `authority` is strictly blocked (HTTP 403).
- **Login**: `POST /api/auth/login`
  - Body: `{"email", "password"}`
  - Response: `{"access_token", "user": {"id", "email", "role", "hospital_id"}}`
- **Profile**: `GET /api/auth/me`
  - Header: `Authorization: Bearer <token>`
  - Response: Authenticated user profile, role, hospital assignment.

---

### 15. Hospital Casualty Inbound Requests
- **Endpoint**: `GET /api/hospital/:id/requests` (and `/api/emergency/hospital/:id/requests`)
- **Caller**: Casualty Intake Desk on `#/hospital`
- **Header**: `Authorization: Bearer <staff_jwt>`
- **Response**: List of incoming and active emergency requests targeted at this hospital, with OTP and token hashes sanitized.
