"""
AIIS Backend V2 - Emergency SOS & Triage Test Suite
===================================================
Comprehensive tests for:
- Hospital proximity search (GPS & City)
- Template compatibility (/api/emergency/hospitals)
- Emergency SOS broadcast and 4-digit OTP generation
- Real-time status tracking
- Patient arrival verification with OTP
- Cancellation flow
- Locations directory
"""

import uuid
import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.services.auth_service import AuthService


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


def _get_staff_headers(hospital_id: int = 1):
    profile_repo = ProfileRepository()
    user_id = str(uuid.uuid4())
    email = f"staff_{uuid.uuid4().hex[:6]}@hospital{hospital_id}.test"
    profile_repo.create_profile(
        user_id=user_id,
        full_name="Casualty Staff",
        email=email,
        role="hospital_admin",
        hospital_id=hospital_id,
        account_status="active",
    )
    auth_svc = AuthService(profile_repo=profile_repo)
    token = auth_svc._generate_jwt(user_id=user_id, email=email)
    return {"Authorization": f"Bearer {token}"}


# ── 1. Search Tests ───────────────────────────────────────────────────────────

def test_emergency_search_gps_success(client):
    """Verify GPS-based emergency hospital search returns ranked proximity results."""
    payload = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "category": "cardiac",
        "limit": 5,
    }
    response = client.post("/api/emergency/search", json=payload)
    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert data["meta"]["match_basis"] == "straight_line_distance"

    first = data["results"][0]
    assert "id" in first
    assert "name" in first
    assert "distanceKm" in first
    assert first["distanceKm"] >= 0.0
    assert "transitMins" in first
    assert "whyRanked" in first
    assert len(first["whyRanked"]) > 0


def test_emergency_search_city_success(client):
    """Verify city-based fallback search returns facilities matching the city."""
    payload = {
        "city": "Bengaluru",
        "category": "general",
    }
    response = client.post("/api/emergency/search", json=payload)
    assert response.status_code == 200

    data = response.get_json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert data["meta"]["match_basis"] == "city_directory"

    for h in data["results"]:
        assert "Bengaluru" in h["city"]


def test_emergency_search_validation_failure(client):
    """Verify search without GPS coordinates or city returns 400 validation error."""
    response = client.post("/api/emergency/search", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_emergency_hospitals_template_get_success(client):
    """Verify GET /api/emergency/hospitals contract for patient_entry.html."""
    response = client.get("/api/emergency/hospitals?lat=12.9635&lon=77.5734&emergency_type=trauma")
    assert response.status_code == 200
    data = response.get_json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert data["meta"]["category"] == "trauma"


# ── 2. SOS Request & Coordination Lifecycle Tests ─────────────────────────────

def test_emergency_sos_create_and_lifecycle(client):
    """
    Test complete citizen SOS user journey:
    1. Submit SOS -> receive ID & 4-digit OTP.
    2. Poll status -> verify details.
    3. Verify arrival with OTP -> status changes to PATIENT_ARRIVED.
    """
    # Step 1: Submit SOS
    create_payload = {
        "hospitalId": 1,
        "emergencyCategory": "cardiac",
        "patientName": "Arogya Test Patient",
        "contactPhone": "+919876543210",
        "estimatedTravelMinutes": 12,
        "notes": "Severe chest tightness, conscious",
    }
    create_res = client.post("/api/coordination/request", json=create_payload)
    assert create_res.status_code == 201
    created_data = create_res.get_json()
    assert created_data["success"] is True

    req = created_data["request"]
    req_id = req["id"]
    otp = req["otp"]

    assert req_id.startswith("REQ-")
    assert len(otp) == 4
    assert otp.isdigit()
    assert req["status"] == "REQUEST_SUBMITTED"
    assert "holdExpiresAt" in req

    # Step 2: Poll status - ensure OTP is NOT leaked in status response
    status_res = client.get(f"/api/coordination/{req_id}")
    assert status_res.status_code == 200
    status_data = status_res.get_json()
    assert status_data["request"]["id"] == req_id
    assert status_data["request"]["patientName"] == "Arogya Test Patient"
    assert "otp" not in status_data["request"]
    assert "arrivalOtp" not in status_data["request"]

    # Step 3: Verify arrival with valid OTP and authorized hospital staff credentials
    headers = _get_staff_headers(1)
    verify_res = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": otp},
        headers=headers,
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.get_json()
    assert verify_data["request"]["status"] == "PATIENT_ARRIVED"


def test_emergency_sos_invalid_phone(client):
    """Verify phone with fewer than 10 digits triggers 400 validation error."""
    payload = {
        "hospitalId": 1,
        "contactPhone": "12345",  # Too short
    }
    response = client.post("/api/coordination/request", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_emergency_sos_missing_hospital(client):
    """Verify missing hospital ID triggers 400 validation error."""
    payload = {
        "patientName": "No Hospital Given",
    }
    response = client.post("/api/coordination/request", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_emergency_sos_cancellation(client):
    """Verify cancellation of an active emergency request."""
    # Create request
    create_res = client.post("/api/coordination/request", json={"hospitalId": 1})
    req_id = create_res.get_json()["request"]["id"]

    # Cancel request
    cancel_res = client.post(
        f"/api/coordination/{req_id}/cancel",
        json={"reason": "Patient taken by family to alternate clinic"},
    )
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.get_json()
    assert cancel_data["request"]["status"] == "CANCELLED"
    assert cancel_data["request"]["cancellation_reason"] == "Patient taken by family to alternate clinic"


def test_emergency_sos_verify_wrong_otp(client):
    """Verify arrival verification with incorrect OTP fails with 400."""
    create_res = client.post("/api/coordination/request", json={"hospitalId": 1})
    req_id = create_res.get_json()["request"]["id"]
    headers = _get_staff_headers(1)

    verify_res = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": "0000"},
        headers=headers,
    )
    assert verify_res.status_code == 400
    data = verify_res.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


# ── 3. Locations Directory Test ───────────────────────────────────────────────

def test_locations_endpoint(client):
    """Verify GET /api/locations returns available cities with coordinates."""
    response = client.get("/api/locations")
    assert response.status_code == 200
    data = response.get_json()
    assert "locations" in data
    assert len(data["locations"]) > 0

    first = data["locations"][0]
    assert "name" in first
    assert "lat" in first
    assert "lng" in first
