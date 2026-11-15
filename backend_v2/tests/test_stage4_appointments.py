"""
AIIS Backend V2 - Stage 4: Outpatient Appointments Test Suite
=============================================================
Comprehensive test suite verifying:
1. Citizen appointment booking with schema and phone validation.
2. Rejection of past appointment dates.
3. Facility existence validation (404 for nonexistent facility).
4. Authenticated patient session binding to appointment records.
5. Patient history isolation via GET /api/appointments/me.
6. Cross-patient privacy protection (403 Forbidden for snooping).
7. Citizen self-cancellation via POST /api/appointments/<id>/cancel.
8. Hospital administrator appointment inspection (GET /api/hospital/<id>/appointments).
9. Hospital admin isolation (403 Forbidden for cross-facility access).
10. Hospital admin lifecycle status update (REQUESTED -> CONFIRMED -> COMPLETED).
11. Validation rejection of invalid status transitions.
"""

import uuid
from datetime import date, timedelta
import pytest

from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.repositories.profile_repository import ProfileRepository


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


def get_future_date_str(days_ahead: int = 3) -> str:
    """Helper to return an ISO date safely in the future."""
    return (date.today() + timedelta(days=days_ahead)).isoformat()


def register_and_login_patient(client, email_prefix: str = "patient") -> tuple:
    """Helper to register and login a test patient, returning (user_id, auth_headers)."""
    unique_email = f"{email_prefix}.{uuid.uuid4().hex[:8]}@example.com"
    reg_res = client.post("/api/auth/register", json={
        "full_name": "Test Citizen",
        "email": unique_email,
        "password": "Password123",
        "role": "patient",
        "phone": "+919876543210",
    })
    assert reg_res.status_code == 201

    login_res = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "Password123",
    })
    assert login_res.status_code == 200
    token = login_res.get_json()["data"]["access_token"]
    user_id = login_res.get_json()["data"]["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


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
    from backend_v2.services.auth_service import AuthService
    auth_svc = AuthService(profile_repo=profile_repo)
    token = auth_svc._generate_jwt(user_id=admin_id, email=admin_email)
    return admin_id, {"Authorization": f"Bearer {token}"}


# ── 1. Citizen Appointment Booking Tests ──────────────────────────────────────

def test_create_appointment_guest_success(client):
    """Verify citizen can book an appointment; status defaults to REQUESTED."""
    payload = {
        "hospital_id": 1,
        "patient_name": "Ramesh Kumar",
        "patient_phone": "+919876501234",
        "patient_age": "42",
        "specialty": "Cardiology",
        "preferred_date": get_future_date_str(5),
        "preferred_time_slot": "10:00 AM - 12:00 PM",
        "notes": "Follow-up consultation for blood pressure",
    }
    response = client.post("/api/appointments", json=payload)
    assert response.status_code == 201
    assert response.is_json

    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"].startswith("APT-")
    assert data["status"] == "REQUESTED"
    assert data["hospital_id"] == 1
    assert data["patient_name"] == "Ramesh Kumar"
    assert data["patient_id"] is None  # Unauthenticated guest


def test_create_appointment_authenticated_patient(client):
    """Verify authenticated citizen booking automatically associates patient_id."""
    user_id, headers = register_and_login_patient(client, "auth.book")
    payload = {
        "hospital_id": 1,
        "patient_name": "Authenticated Citizen",
        "patient_phone": "+919876509999",
        "specialty": "General Medicine",
        "preferred_date": get_future_date_str(2),
        "preferred_time_slot": "02:00 PM - 04:00 PM",
    }
    response = client.post("/api/appointments", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["patient_id"] == user_id


def test_create_appointment_reject_past_date(client):
    """Verify booking for a date in the past is rejected with 400 validation error."""
    payload = {
        "hospital_id": 1,
        "patient_name": "Late Booker",
        "patient_phone": "+919876501234",
        "specialty": "General Medicine",
        "preferred_date": "2020-01-01",  # Past date
        "preferred_time_slot": "10:00 AM",
    }
    response = client.post("/api/appointments", json=payload)
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert "past" in body["error"]["message"].lower()


def test_create_appointment_invalid_hospital(client):
    """Verify booking for non-existent facility returns 404 NOT_FOUND."""
    payload = {
        "hospital_id": 999999,
        "patient_name": "Lost Patient",
        "patient_phone": "+919876501234",
        "specialty": "General Medicine",
        "preferred_date": get_future_date_str(4),
        "preferred_time_slot": "10:00 AM",
    }
    response = client.post("/api/appointments", json=payload)
    assert response.status_code == 404
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_create_appointment_invalid_phone(client):
    """Verify phone with fewer than 8 digits is rejected with 400."""
    payload = {
        "hospital_id": 1,
        "patient_name": "Short Phone",
        "patient_phone": "123",
        "specialty": "General Medicine",
        "preferred_date": get_future_date_str(4),
        "preferred_time_slot": "10:00 AM",
    }
    response = client.post("/api/appointments", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


# ── 2. Patient History & Privacy Tests ─────────────────────────────────────────

def test_get_my_appointments(client):
    """Verify GET /api/appointments/me returns appointments for the logged-in patient."""
    user_id, headers = register_and_login_patient(client, "my.apt")

    # Book two appointments
    for spec in ["Cardiology", "Paediatrics"]:
        client.post("/api/appointments", json={
            "hospital_id": 1,
            "patient_name": "Citizen Multi",
            "patient_phone": "+919876501111",
            "specialty": spec,
            "preferred_date": get_future_date_str(3),
            "preferred_time_slot": "11:00 AM",
        }, headers=headers)

    response = client.get("/api/appointments/me", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["data"]) >= 2
    for apt in body["data"]:
        assert apt["patient_id"] == user_id


def test_patient_cannot_view_other_patient_appointment(client):
    """Verify Patient A is forbidden from viewing Patient B's appointment."""
    user_a, headers_a = register_and_login_patient(client, "patient.a")
    user_b, headers_b = register_and_login_patient(client, "patient.b")

    # Patient B books an appointment
    res_b = client.post("/api/appointments", json={
        "hospital_id": 1,
        "patient_name": "Patient B",
        "patient_phone": "+919876502222",
        "specialty": "Cardiology",
        "preferred_date": get_future_date_str(5),
        "preferred_time_slot": "09:00 AM",
    }, headers=headers_b)
    apt_b_id = res_b.get_json()["data"]["id"]

    # Patient A attempts to view Patient B's appointment
    response = client.get(f"/api/appointments/{apt_b_id}", headers=headers_a)
    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_patient_cancel_own_appointment(client):
    """Verify patient can cancel their own scheduled appointment."""
    user_id, headers = register_and_login_patient(client, "cancel.apt")

    res = client.post("/api/appointments", json={
        "hospital_id": 1,
        "patient_name": "Cancelling Citizen",
        "patient_phone": "+919876503333",
        "specialty": "Radiology",
        "preferred_date": get_future_date_str(7),
        "preferred_time_slot": "03:00 PM",
    }, headers=headers)
    apt_id = res.get_json()["data"]["id"]

    # Cancel
    cancel_res = client.post(
        f"/api/appointments/{apt_id}/cancel",
        json={"reason": "Schedule conflict"},
        headers=headers,
    )
    assert cancel_res.status_code == 200
    body = cancel_res.get_json()
    assert body["success"] is True
    assert body["data"]["status"] == "CANCELLED"


# ── 3. Hospital Administrator Appointment Management Tests ────────────────────

def test_hospital_admin_view_hospital_appointments(client):
    """Verify hospital admin can list appointments for their facility."""
    admin_id, admin_headers = create_hospital_admin_token(hospital_id=1)

    # Book an appointment for hospital 1
    client.post("/api/appointments", json={
        "hospital_id": 1,
        "patient_name": "Hosp 1 Patient",
        "patient_phone": "+919876504444",
        "specialty": "Emergency & Casualty",
        "preferred_date": get_future_date_str(3),
        "preferred_time_slot": "10:00 AM",
    })

    response = client.get("/api/hospital/1/appointments", headers=admin_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


def test_hospital_admin_cross_hospital_appointments_blocked(client):
    """Verify Hospital 1 admin cannot view Hospital 2's appointments."""
    admin_id, admin_headers = create_hospital_admin_token(hospital_id=1)

    # Admin 1 attempts to view Hospital 2 appointments
    response = client.get("/api/hospital/2/appointments", headers=admin_headers)
    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


def test_hospital_admin_update_appointment_status(client):
    """Verify hospital admin can confirm an appointment."""
    admin_id, admin_headers = create_hospital_admin_token(hospital_id=1)

    res = client.post("/api/appointments", json={
        "hospital_id": 1,
        "patient_name": "Confirm Me",
        "patient_phone": "+919876505555",
        "specialty": "General Medicine",
        "preferred_date": get_future_date_str(4),
        "preferred_time_slot": "11:00 AM",
    })
    apt_id = res.get_json()["data"]["id"]

    # Hospital admin confirms appointment
    update_res = client.put(
        f"/api/hospital/1/appointments/{apt_id}/status",
        json={"status": "CONFIRMED", "notes": "Doctor Sharma confirmed for Room 204"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    body = update_res.get_json()
    assert body["success"] is True
    assert body["data"]["status"] == "CONFIRMED"


def test_hospital_admin_update_invalid_status(client):
    """Verify updating to an illegal appointment status returns 400 validation error."""
    admin_id, admin_headers = create_hospital_admin_token(hospital_id=1)

    res = client.post("/api/appointments", json={
        "hospital_id": 1,
        "patient_name": "Invalid Status Target",
        "patient_phone": "+919876506666",
        "specialty": "General Medicine",
        "preferred_date": get_future_date_str(4),
        "preferred_time_slot": "11:00 AM",
    })
    apt_id = res.get_json()["data"]["id"]

    update_res = client.put(
        f"/api/hospital/1/appointments/{apt_id}/status",
        json={"status": "INVALID_STATUS"},
        headers=admin_headers,
    )
    assert update_res.status_code == 400
    body = update_res.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
