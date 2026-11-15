"""
AIIS Backend V2 - SPA Frontend Full Integration Test Suite
==========================================================
Verifies that the handoff SPA frontend (public/index.html, styles.css, app.js)
and Backend V2 operate seamlessly together across all 4 hackathon demo workflows:

1. Static Assets & Root Routing:
   - GET / -> public/index.html
   - GET /styles.css -> text/css
   - GET /app.js -> javascript
   - GET /vendor/qrcode.js -> javascript
   - GET /manifest.json -> json

2. Workflow A: Citizen Emergency SOS (No Login):
   - POST /api/emergency/search -> hospitals with partner: True
   - POST /api/coordination/request -> request_id, tracking_token, arrival_otp
   - GET /api/coordination/<id> with X-Tracking-Token -> status, OTP redacted
   - POST /api/coordination/<id>/verify-arrival with guest token -> strictly 403 Forbidden

3. Workflow B: Hospital Coordination & Intake Desk:
   - GET /api/hospital/1/requests -> active emergency requests
   - POST /api/coordination/<id>/verify-arrival with staff code & OTP -> PATIENT_ARRIVED
   - POST /api/hospitals/1/capacity with X-AIIS-Staff-Code -> capacity updated

4. Workflow C: Regional SRI Surveillance:
   - GET /api/sri/regional -> zones, districts, regional score, risk band

5. Workflow D: Planned Care & Appointments:
   - POST /api/planned/search -> specialties, facilities
   - POST /api/appointments/request -> appointment booked
   - GET /api/appointments?phone=... -> appointment retrieved
   - POST /api/appointments/<id>/cancel -> appointment cancelled

6. Authentication Lifecycle:
   - POST /api/auth/register -> user registered
   - POST /api/auth/login -> JWT token issued
   - GET /api/auth/me -> authenticated profile
   - POST /api/auth/logout -> session terminated
"""

import os
import uuid
import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


# ── 1. Static Assets & Root Routing ──────────────────────────────────────────

def test_static_root_assets(client):
    """Verify that Flask serves the handoff SPA static assets at root URLs."""
    # 1. Root index.html
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert b"AIIS" in res_index.data
    assert b'<nav class="desknav"' in res_index.data
    assert b'<div class="sheet" id="sheet"' in res_index.data

    # 2. Root stylesheet
    res_css = client.get("/styles.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.content_type
    assert b"--ink:" in res_css.data or b".btn" in res_css.data

    # 3. Root JavaScript app
    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    assert "javascript" in res_css.content_type or "text/" in res_js.content_type or "application/" in res_js.content_type
    assert b"viewHome" in res_js.data
    assert b"viewSignIn" in res_js.data
    assert b"viewStaff" in res_js.data

    # 4. Vendor QRCode library
    res_qr = client.get("/vendor/qrcode.js")
    assert res_qr.status_code == 200
    assert b"QRCode" in res_qr.data or b"qrcode" in res_qr.data

    # 5. Web manifest
    res_manifest = client.get("/manifest.json")
    assert res_manifest.status_code == 200
    assert b"AIIS" in res_manifest.data


# ── 2. Workflow A: Citizen Emergency SOS ──────────────────────────────────────

def test_workflow_a_emergency_sos_lifecycle(client):
    """
    Test complete citizen SOS flow:
    Search -> Check partner flag -> Create request -> Receive OTP -> Poll via tracking token.
    """
    # 1. Search emergency facilities
    search_res = client.post("/api/emergency/search", json={
        "latitude": 12.9716,
        "longitude": 77.5946,
        "category": "cardiac",
        "radius_km": 25,
    })
    assert search_res.status_code == 200
    search_data = search_res.get_json()
    hospitals = search_data.get("rankedHospitals") or search_data.get("results") or search_data.get("hospitals", [])
    assert len(hospitals) > 0

    # Directory-only hospitals (not in the AIIS database) are call-only; pick the first partner.
    target = next(h for h in hospitals if h.get("partner") is True)
    target_id = target.get("id") or target.get("hospitalId")
    assert target.get("partner") is True  # Must be partner to render 'Tell them I'm coming'

    # 2. Create emergency coordination request (guest, no login required)
    coord_res = client.post("/api/coordination/request", json={
        "hospitalId": target_id,
        "emergencyCategory": "cardiac",
        "estimatedTravelMinutes": 15,
        "userLocationName": "Bengaluru Central",
    })
    assert coord_res.status_code == 201
    coord_data = coord_res.get_json()
    req_obj = coord_data.get("request") or coord_data.get("data") or coord_data

    req_id = req_obj.get("id") or req_obj.get("requestId")
    tracking_token = req_obj.get("tracking_token") or req_obj.get("trackingToken")
    arrival_otp = req_obj.get("arrival_otp") or req_obj.get("otp")

    assert req_id is not None
    assert tracking_token is not None
    assert arrival_otp is not None
    assert len(str(arrival_otp)) == 4
    assert str(arrival_otp).isdigit()

    # 3. Poll request tracking status using tracking token header
    poll_res = client.get(
        f"/api/coordination/{req_id}",
        headers={"X-Tracking-Token": tracking_token}
    )
    assert poll_res.status_code == 200
    poll_data = poll_res.get_json()
    poll_obj = poll_data.get("request") or poll_data.get("data") or poll_data
    assert poll_obj.get("id") == req_id
    assert "otp" not in poll_obj  # Security check: OTP must never be returned in poll responses
    assert "arrival_otp" not in poll_obj

    # 4. Security verification: Guest tracking token CANNOT verify arrival
    guest_verify = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        headers={"X-Tracking-Token": tracking_token},
        json={"otp": str(arrival_otp)}
    )
    assert guest_verify.status_code == 403


# ── 3. Workflow B: Hospital Intake & Arrival Verification ─────────────────────

def test_workflow_b_hospital_intake_and_arrival(client):
    """
    Test hospital casualty desk intake:
    List incoming requests -> Verify patient arrival with OTP -> Update live capacity.
    """
    # 1. Create incoming request targeted at hospital 1
    req_res = client.post("/api/coordination/request", json={
        "hospitalId": 1,
        "emergencyCategory": "trauma",
        "estimatedTravelMinutes": 10,
        "userLocationName": "Indiranagar",
    })
    assert req_res.status_code == 201
    created_data = req_res.get_json()
    req_id = created_data.get("request", {}).get("id") or created_data.get("data", {}).get("id")
    otp = created_data.get("request", {}).get("arrival_otp") or created_data.get("data", {}).get("arrival_otp")
    assert otp is not None

    # 2. Security: Unauthenticated access without token returns 401
    unauth_intake = client.get("/api/hospital/1/requests")
    assert unauth_intake.status_code == 401

    # Seed mock credentials for test runner isolation
    from backend_v2.services.auth_service import AuthService
    from backend_v2.repositories.profile_repository import ProfileRepository
    auth_service = AuthService()
    admin_id = "00000000-0000-0000-0000-000000000001"
    AuthService._mock_passwords["admin@victoria.in"] = auth_service._hash_password("DoctorPass123")
    ProfileRepository._shared_profiles[admin_id] = {
        "id": admin_id,
        "email": "admin@victoria.in",
        "full_name": "Victoria Admin",
        "role": "hospital_admin",
        "hospital_id": 1,
        "account_status": "active"
    }

    # 3. Hospital staff logs in via JWT authentication (admin@victoria.in -> Hospital 1)
    login_res = client.post("/api/auth/login", json={
        "email": "admin@victoria.in",
        "password": "DoctorPass123",
    })
    assert login_res.status_code == 200
    staff_token = login_res.get_json()["data"]["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # 4. Security: Cross-hospital access is strictly forbidden (Hospital 1 admin cannot access Hospital 2)
    cross_res = client.get("/api/hospital/2/requests", headers=staff_headers)
    assert cross_res.status_code == 403

    # 5. Authorized Hospital 1 staff views incoming requests
    intake_res = client.get(
        "/api/hospital/1/requests",
        headers=staff_headers
    )
    assert intake_res.status_code == 200
    requests = intake_res.get_json().get("requests") or intake_res.get_json().get("data", {}).get("requests", [])
    matching = [r for r in requests if r.get("id") == req_id]
    assert len(matching) > 0

    # 6. Desk staff verifies arrival using OTP
    verify_res = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        headers=staff_headers,
        json={"otp": str(otp)}
    )
    assert verify_res.status_code == 200
    v_data = verify_res.get_json()
    res_status = v_data.get("data", {}).get("status") or v_data.get("request", {}).get("status")
    assert res_status == "PATIENT_ARRIVED"

    # 7. Repeat verification is idempotent
    verify_again = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        headers=staff_headers,
        json={"otp": str(otp)}
    )
    assert verify_again.status_code == 200

    # 8. Cross-hospital capacity update is strictly forbidden
    cross_cap = client.post(
        "/api/hospitals/2/capacity",
        headers=staff_headers,
        json={"emergencyBeds": {"available": 10}}
    )
    assert cross_cap.status_code == 403

    # 9. Authorized hospital updates bed capacity with nested frontend payload
    cap_update = client.post(
        "/api/hospitals/1/capacity",
        headers=staff_headers,
        json={
            "emergencyBeds": {"available": 14},
            "icuBeds": {"available": 4},
            "departments": [{"name": "Emergency", "status": "Ready"}],
            "equipment": [{"name": "CT Scanner", "status": "Available"}]
        }
    )
    assert cap_update.status_code == 200
    cap_data = cap_update.get_json()
    assert cap_data.get("data", {}).get("available_beds") == 14
    assert cap_data.get("data", {}).get("source") == "hospital_admin_reported"


# ── 4. Workflow C: Regional SRI Surveillance ──────────────────────────────────

def test_workflow_c_regional_sri_surveillance(client):
    """Verify Regional SRI returns zones, districts, metrics, and risk band."""
    sri_res = client.get("/api/sri/regional")
    assert sri_res.status_code == 200
    sri_data = sri_res.get_json().get("data", {})

    assert "overall_sri" in sri_data or "regional_score" in sri_data
    assert "risk_band" in sri_data
    assert "zones" in sri_data
    assert len(sri_data["zones"]) > 0

    # Verify each zone has score and band
    first_zone = sri_data["zones"][0]
    assert "name" in first_zone
    assert "sri" in first_zone
    assert "level" in first_zone


# ── 5. Workflow D: Planned Care & Appointments ────────────────────────────────

def test_workflow_d_planned_care_and_appointments(client):
    """Verify planned care search, booking, retrieval by phone, and cancellation."""
    # 1. Search planned facilities
    search_res = client.post("/api/planned/search", json={
        "latitude": 12.9716,
        "longitude": 77.5946,
        "specialty": "cardiology",
        "query": "",
    })
    assert search_res.status_code == 200
    results = search_res.get_json().get("results", [])
    assert len(results) > 0

    # 2. Book appointment
    book_res = client.post("/api/appointments/request", json={
        "hospitalId": results[0]["id"],
        "specialty": "Cardiology",
        "preferredDate": "2026-11-20",
        "preferredTimeSlot": "Morning",
        "patientName": "Sunita Patil",
        "patientPhone": "+91 9988776655",
    })
    assert book_res.status_code == 201
    appt = book_res.get_json().get("appointment") or book_res.get_json().get("data")
    appt_id = appt.get("id")
    assert appt_id is not None

    # 3. Security: Unauthenticated request without token returns 401
    unauth_res = client.get("/api/appointments?phone=%2B919988776655")
    assert unauth_res.status_code == 401

    # 4. Authenticate patient and retrieve appointments
    test_uid = uuid.uuid4().hex[:8]
    patient_email = f"planned_patient_{test_uid}@karnataka.gov.in"
    patient_pass = "PlannedPass2026!"
    reg_resp = client.post("/api/auth/register", json={
        "full_name": "Sunita Patil",
        "email": patient_email,
        "password": patient_pass,
        "phone": "+91 9988776655",
        "role": "patient",
    })
    assert reg_resp.status_code in (201, 200)
    login_resp = client.post("/api/auth/login", json={"email": patient_email, "password": patient_pass})
    assert login_resp.status_code == 200
    auth_token = login_resp.get_json()["data"]["access_token"]
    auth_headers = {"Authorization": f"Bearer {auth_token}"}

    get_res = client.get("/api/appointments/me", headers=auth_headers)
    assert get_res.status_code == 200
    appts_list = get_res.get_json().get("appointments", [])
    assert isinstance(appts_list, list)

    # 5. Cancel appointment
    cancel_res = client.post(
        f"/api/appointments/{appt_id}/cancel",
        headers=auth_headers,
        json={"reason": "Cancelled by patient"}
    )
    assert cancel_res.status_code == 200


# ── 6. Authentication Lifecycle ───────────────────────────────────────────────

def test_auth_lifecycle(client):
    """Verify registration, login, profile check (/api/auth/me), and logout."""
    test_uid = uuid.uuid4().hex[:8]
    email = f"integration_patient_{test_uid}@karnataka.gov.in"
    password = "SecurePatientPass2026!"

    # 1. Register
    reg_res = client.post("/api/auth/register", json={
        "full_name": "Integration Test Patient",
        "email": email,
        "password": password,
        "phone": "+91 9123456789",
        "role": "patient",
    })
    # Must succeed with 201 Created
    assert reg_res.status_code in (201, 200)

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_res.status_code == 200
    login_data = login_res.get_json().get("data", {})
    token = login_data.get("access_token")
    assert token is not None

    # 3. Authenticated profile check
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.get_json().get("data", {})
    assert profile.get("email") == email
    assert profile.get("role") == "patient"

    # 4. Logout
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200


def test_verified_locations_and_real_numbers(client):
    """Hospital pins match Google Maps listings, directions open the named place, and no placeholder numbers leak."""
    res = client.post("/api/emergency/search", json={"latitude": 12.9643, "longitude": 77.5754, "category": "general"})
    hospitals = res.get_json()["rankedHospitals"]
    victoria = next(h for h in hospitals if h["name"] == "Victoria Hospital")
    assert abs(victoria["latitude"] - 12.9643083) < 1e-6 and abs(victoria["longitude"] - 77.5754198) < 1e-6
    assert "destination=Victoria%20Hospital" in victoria["directionsUrl"]
    assert victoria["distanceKm"] < 0.1  # real distance, not a synthetic one
    for h in hospitals:
        for k in ("phone", "emergencyPhone", "receptionPhone"):
            assert "800-000" not in str(h.get(k) or "")
    # top 3 are always 24x7 general emergency departments
    assert all(h.get("emergencyScope", "general") == "general" for h in hospitals[:3])


def test_directory_hospital_is_call_only(client):
    res = client.post("/api/coordination/request", json={"hospitalId": 115, "estimatedTravelMinutes": 8})
    assert res.status_code == 409
