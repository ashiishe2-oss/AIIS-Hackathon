"""
AIIS Backend V2 - Stage 4 Part 2: Planned Healthcare & Appointment Integration Contracts
========================================================================================
Comprehensive verification of the 16 core integration contracts:
1. Planned search by specialty (POST /api/planned/search -> 200 OK, enriched facilities)
2. Planned search by location (POST /api/planned/search with city/coords -> 200 OK)
3. Empty search results (POST /api/planned/search with unmatched criteria -> 200 OK, data: [])
4. Invalid specialty (POST /api/planned/search with malformed specialty -> 400 Validation Error)
5. Appointment creation via frontend contract (POST /api/appointments/request -> 201 Created)
6. Hospital ID mapping in appointment creation ("hospitalId": "hsp-001" -> hospital_id: 1)
7. Authenticated appointment retrieval (GET /api/appointments/me and GET /api/appointments?phone=...)
8. Attempted retrieval using foreign phone (GET /api/appointments?phone=<foreign_phone> -> 403 Forbidden)
9. Cross-patient appointment access (GET /api/appointments/<apt_b_id> by patient A -> 403 Forbidden)
10. Cross-patient cancellation (POST /api/appointments/<apt_b_id>/cancel by patient A -> 403 Forbidden)
11. Invalid cancellation state conflict (cancelling an already cancelled appointment -> 409 Conflict)
12. Past appointment date rejection (preferred_date in the past -> 400 Validation Error)
13. Unauthenticated appointment access (GET/POST endpoints without token -> 401 Unauthorized)
14. Patient identity derived from JWT (patient_id matches token sub, client body ID ignored)
15. Hospital admin access restrictions (Admin for Hospital 1 blocked from Hospital 2 appointments -> 403)
16. Guest emergency access preserved (POST /api/emergency/sos & /api/coordination/request without auth -> 201)
"""

import uuid
from datetime import date, timedelta
import pytest

from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.services.auth_service import AuthService


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


def get_future_date_str(days_ahead: int = 5) -> str:
    """Helper to return an ISO date safely in the future."""
    return (date.today() + timedelta(days=days_ahead)).isoformat()


def register_and_login_patient(client, email_prefix: str = "patient", phone: str = "+919876543210") -> tuple:
    """Helper to register and login a test patient, returning (user_id, auth_headers, phone)."""
    unique_email = f"{email_prefix}.{uuid.uuid4().hex[:8]}@example.com"
    reg_res = client.post("/api/auth/register", json={
        "full_name": "Test Citizen",
        "email": unique_email,
        "password": "Password123",
        "role": "patient",
        "phone": phone,
    })
    assert reg_res.status_code == 201

    login_res = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "Password123",
    })
    assert login_res.status_code == 200
    token = login_res.get_json()["data"]["access_token"]
    user_id = login_res.get_json()["data"]["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}, phone


def create_hospital_admin_token(hospital_id: int = 1) -> tuple:
    """Helper to seed an active hospital admin and generate authorization headers."""
    profile_repo = ProfileRepository()
    admin_id = str(uuid.uuid4())
    admin_email = f"admin.{uuid.uuid4().hex[:8]}@hospital.in"
    profile_repo.create_profile(
        user_id=admin_id,
        full_name="Hospital Administrator",
        email=admin_email,
        role="hospital_admin",
        hospital_id=hospital_id,
        account_status="active",
    )
    auth_svc = AuthService(profile_repo=profile_repo)
    token = auth_svc._generate_jwt(user_id=admin_id, email=admin_email)
    return admin_id, {"Authorization": f"Bearer {token}"}


# ── 1. Planned Healthcare Discovery Tests ────────────────────────────────────

def test_1_planned_search_by_specialty(client):
    """1. Planned search by specialty returns 200 OK and enriched facilities with honest disclaimers."""
    res = client.post("/api/planned/search", json={
        "specialty": "Cardiology",
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0

    first = body["data"][0]
    # Verify enrichment and dual identifiers
    assert "id" in first
    assert "code" in first
    assert "hospital_code" in first
    assert "frontend_id" in first
    assert first["code"].startswith("hsp-")
    # Verify honest metadata disclosures
    assert first.get("consultant_availability") is False
    assert "waiting_time_disclaimer" in first
    assert "opd_schedule_notice" in first


def test_2_planned_search_by_location(client):
    """2. Planned search by location (city or coordinates) returns 200 OK."""
    # Search by city
    res_city = client.post("/api/planned/search", json={
        "city": "Bengaluru",
        "specialty": "General Medicine",
    })
    assert res_city.status_code == 200
    body_city = res_city.get_json()
    assert body_city["success"] is True
    assert len(body_city["data"]) > 0

    # Search by GPS coordinates
    res_coords = client.post("/api/planned/search", json={
        "latitude": 12.9716,
        "longitude": 77.5946,
        "radius_km": 15,
        "specialty": "General Medicine",
    })
    assert res_coords.status_code == 200
    body_coords = res_coords.get_json()
    assert body_coords["success"] is True
    assert len(body_coords["data"]) > 0


def test_3_planned_search_empty_results(client):
    """3. Planned search with criteria matching no facilities returns 200 OK with empty list."""
    res = client.post("/api/planned/search", json={
        "city": "NonExistentCityXYZ123",
        "specialty": "Cardiology",
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_4_planned_search_invalid_specialty(client):
    """4. Planned search with malformed or non-medical specialty returns 400 Validation Error."""
    malformed_specialties = [
        "<script>alert(1)</script>",
        "x",
        "drop table hospitals;",
        "12345",
    ]
    for bad_spec in malformed_specialties:
        res = client.post("/api/planned/search", json={
            "specialty": bad_spec,
        })
        assert res.status_code == 400
        body = res.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"


# ── 2. Appointment Booking & Mapping Tests ────────────────────────────────────

def test_5_appointment_creation_frontend_format(client):
    """5. Appointment creation via frontend contract (POST /api/appointments/request) returns 201 Created."""
    user_id, headers, _ = register_and_login_patient(client, "frontend.apt")
    payload = {
        "hospitalId": "hsp-001",
        "patientName": "Sunita Rao",
        "patientPhone": "+919876543210",
        "patientAge": "34",
        "specialty": "Cardiology",
        "preferredDate": get_future_date_str(4),
        "preferredTimeSlot": "10:00 AM - 12:00 PM",
        "notes": "Routine cardiovascular consultation",
    }
    res = client.post("/api/appointments/request", json=payload, headers=headers)
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    data = body["data"]

    # Verify ID structure and dual-key support
    assert data["id"].startswith("APT-")
    assert data["appointmentId"] == data["id"]
    assert data["hospital_id"] == 1
    assert data["hospitalId"] == "hsp-001"
    assert data["hospitalCode"] == "hsp-001"
    assert data["patientName"] == "Sunita Rao"
    assert data["preferredTimeSlot"] == "10:00 AM - 12:00 PM"
    assert data["status"] == "REQUESTED"
    assert data["booking_mode"] == "REQUESTED"
    assert "notice" in data


def test_6_appointment_hospital_id_mapping(client):
    """6. Hospital ID mapping correctly resolves 'hsp-003' to hospital_id 3 and stores canonical int."""
    payload = {
        "hospitalId": "hsp-003",
        "patientName": "Anand Verma",
        "patientPhone": "+919876543211",
        "specialty": "General Medicine",
        "preferredDate": get_future_date_str(3),
        "preferredTimeSlot": "02:00 PM - 04:00 PM",
    }
    res = client.post("/api/appointments/request", json=payload)
    assert res.status_code == 201
    data = res.get_json()["data"]
    assert data["hospital_id"] == 3
    assert data["hospitalCode"] == "hsp-003"
    assert data["hospitalId"] == "hsp-003"


# ── 3. Authenticated Retrieval & Privacy Isolation Tests ─────────────────────

def test_7_authenticated_appointment_retrieval(client):
    """7. Authenticated patient can retrieve their appointments via /me and ?phone=..."""
    patient_phone = "+919876509988"
    user_id, headers, _ = register_and_login_patient(client, "retrieve.apt", phone=patient_phone)

    # Book appointment
    create_res = client.post("/api/appointments/request", json={
        "hospitalId": "hsp-001",
        "patientName": "Auth Patient",
        "patientPhone": patient_phone,
        "specialty": "Cardiology",
        "preferredDate": get_future_date_str(4),
        "preferredTimeSlot": "09:00 AM - 11:00 AM",
    }, headers=headers)
    assert create_res.status_code == 201
    apt_id = create_res.get_json()["data"]["id"]

    # 1. Retrieval via /api/appointments/me
    res_me = client.get("/api/appointments/me", headers=headers)
    assert res_me.status_code == 200
    data_me = res_me.get_json()["data"]
    assert any(a["id"] == apt_id for a in data_me)

    # 2. Retrieval via /api/appointments?phone=... with caller's own phone
    res_phone = client.get(f"/api/appointments?phone={patient_phone}", headers=headers)
    assert res_phone.status_code == 200
    data_phone = res_phone.get_json()["data"]
    assert any(a["id"] == apt_id for a in data_phone)


def test_8_attempted_retrieval_foreign_phone_forbidden(client):
    """8. Querying ?phone=<other_phone> raises 403 Forbidden to prevent cross-patient snooping."""
    user_id, headers, _ = register_and_login_patient(client, "snooper.apt", phone="+919876501111")
    foreign_phone = "+919876509999"

    res = client.get(f"/api/appointments?phone={foreign_phone}", headers=headers)
    assert res.status_code == 403
    body = res.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_9_cross_patient_appointment_access_forbidden(client):
    """9. Patient A is strictly forbidden from viewing Patient B's appointment record."""
    _, headers_a, _ = register_and_login_patient(client, "citizen.a")
    _, headers_b, _ = register_and_login_patient(client, "citizen.b")

    # Patient B books an appointment
    create_res = client.post("/api/appointments/request", json={
        "hospitalId": "hsp-001",
        "patientName": "Patient B",
        "patientPhone": "+919876502222",
        "specialty": "Cardiology",
        "preferredDate": get_future_date_str(5),
        "preferredTimeSlot": "11:00 AM",
    }, headers=headers_b)
    apt_b_id = create_res.get_json()["data"]["id"]

    # Patient A attempts to view Patient B's appointment
    res = client.get(f"/api/appointments/{apt_b_id}", headers=headers_a)
    assert res.status_code == 403
    body = res.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_10_cross_patient_cancellation_forbidden(client):
    """10. Patient A is strictly forbidden from cancelling Patient B's appointment."""
    _, headers_a, _ = register_and_login_patient(client, "cancel.a")
    _, headers_b, _ = register_and_login_patient(client, "cancel.b")

    # Patient B books an appointment
    create_res = client.post("/api/appointments/request", json={
        "hospitalId": "hsp-001",
        "patientName": "Patient B",
        "patientPhone": "+919876502222",
        "specialty": "Cardiology",
        "preferredDate": get_future_date_str(5),
        "preferredTimeSlot": "11:00 AM",
    }, headers=headers_b)
    apt_b_id = create_res.get_json()["data"]["id"]

    # Patient A attempts to cancel Patient B's appointment
    res = client.post(f"/api/appointments/{apt_b_id}/cancel", json={
        "reason": "Malicious cancellation attempt"
    }, headers=headers_a)
    assert res.status_code == 403
    body = res.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_11_invalid_cancellation_state_conflict(client):
    """11. Cancelling an already cancelled appointment returns 409 Conflict."""
    _, headers, _ = register_and_login_patient(client, "conflict.apt")

    # Book appointment
    create_res = client.post("/api/appointments/request", json={
        "hospitalId": "hsp-001",
        "patientName": "Patient Conflict",
        "patientPhone": "+919876503333",
        "specialty": "General Medicine",
        "preferredDate": get_future_date_str(6),
        "preferredTimeSlot": "02:00 PM",
    }, headers=headers)
    apt_id = create_res.get_json()["data"]["id"]

    # First cancellation succeeds
    cancel_1 = client.post(f"/api/appointments/{apt_id}/cancel", json={
        "reason": "Change of plans"
    }, headers=headers)
    assert cancel_1.status_code == 200
    assert cancel_1.get_json()["data"]["status"] == "CANCELLED"

    # Second cancellation must fail with 409 Conflict
    cancel_2 = client.post(f"/api/appointments/{apt_id}/cancel", json={
        "reason": "Duplicate cancellation attempt"
    }, headers=headers)
    assert cancel_2.status_code == 409
    body = cancel_2.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFLICT"


def test_12_past_appointment_date_rejected(client):
    """12. Booking an appointment with a past date returns 400 Validation Error."""
    payload = {
        "hospitalId": "hsp-001",
        "patientName": "Past Booker",
        "patientPhone": "+919876504444",
        "specialty": "General Medicine",
        "preferredDate": "2020-01-15",
        "preferredTimeSlot": "10:00 AM",
    }
    res = client.post("/api/appointments/request", json=payload)
    assert res.status_code == 400
    body = res.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "past" in body["error"]["message"].lower()


# ── 4. RBAC, Token Enforcement & Guest Emergency Tests ───────────────────────

def test_13_unauthenticated_appointment_access_rejected(client):
    """13. Accessing protected appointment history or actions without token returns 401 Unauthorized."""
    # History endpoints
    assert client.get("/api/appointments").status_code == 401
    assert client.get("/api/appointments/me").status_code == 401
    assert client.get("/api/appointments?phone=+919876501234").status_code == 401

    # Single appointment retrieval & cancellation
    assert client.get("/api/appointments/APT-FAKE-123").status_code == 401
    assert client.post("/api/appointments/APT-FAKE-123/cancel").status_code == 401


def test_14_patient_identity_derived_from_jwt(client):
    """14. Authenticated booking strictly binds patient_id from JWT, ignoring forged client-supplied IDs."""
    user_id, headers, _ = register_and_login_patient(client, "tamper.patient")
    forged_user_id = str(uuid.uuid4())

    payload = {
        "hospitalId": "hsp-001",
        "patientName": "Tamper Attempt",
        "patientPhone": "+919876505555",
        "specialty": "Cardiology",
        "preferredDate": get_future_date_str(3),
        "preferredTimeSlot": "10:00 AM",
        "patient_id": forged_user_id,
        "patientId": forged_user_id,
    }
    res = client.post("/api/appointments/request", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.get_json()["data"]

    # Verify that the server bound the authentic user_id, NOT the forged ID
    assert data["patient_id"] == user_id
    assert data["patient_id"] != forged_user_id


def test_15_hospital_admin_access_restrictions(client):
    """15. Hospital 1 admin is forbidden from inspecting or cancelling Hospital 2 appointments."""
    _, admin_1_headers = create_hospital_admin_token(hospital_id=1)

    # Book an appointment at Hospital 2
    create_res = client.post("/api/appointments/request", json={
        "hospitalId": "hsp-002",
        "patientName": "Hospital 2 Patient",
        "patientPhone": "+919876506666",
        "specialty": "Emergency & Casualty",
        "preferredDate": get_future_date_str(4),
        "preferredTimeSlot": "11:00 AM",
    })
    assert create_res.status_code == 201
    apt_hosp2_id = create_res.get_json()["data"]["id"]

    # Admin 1 attempts to view Hospital 2 appointment
    view_res = client.get(f"/api/appointments/{apt_hosp2_id}", headers=admin_1_headers)
    assert view_res.status_code == 403
    assert view_res.get_json()["error"]["code"] == "FORBIDDEN"

    # Admin 1 attempts to cancel Hospital 2 appointment
    cancel_res = client.post(f"/api/appointments/{apt_hosp2_id}/cancel", json={
        "reason": "Unauthorized admin action"
    }, headers=admin_1_headers)
    assert cancel_res.status_code == 403
    assert cancel_res.get_json()["error"]["code"] == "FORBIDDEN"


def test_16_guest_emergency_access_preserved(client):
    """16. Emergency SOS endpoints remain 100% functional without authentication."""
    # 1. Emergency SOS
    sos_res = client.post("/api/emergency/sos", json={
        "hospitalId": "hsp-001",
        "latitude": 12.9635,
        "longitude": 77.5734,
        "emergency_category": "cardiac",
        "severity": "critical",
    })
    assert sos_res.status_code == 201
    body_sos = sos_res.get_json()
    assert body_sos["success"] is True
    assert "data" in body_sos
    assert "id" in body_sos["data"]
    assert "tracking_token" in body_sos["data"]

    # 2. Coordination Request (Frontend compatibility alias)
    coord_res = client.post("/api/coordination/request", json={
        "hospitalId": "hsp-001",
        "category": "cardiac",
        "severity": "critical",
        "location": {"lat": 12.9635, "lng": 77.5734},
    })
    assert coord_res.status_code == 201
    body_coord = coord_res.get_json()
    assert body_coord["success"] is True
    assert "id" in body_coord
    assert "trackingToken" in body_coord
