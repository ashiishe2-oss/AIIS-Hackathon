"""
AIIS Backend V2 - Emergency OTP Security & Arrival Authorization Test Suite
=============================================================================
Verification of Stage 5.1 Emergency Security & OTP Protection requirements:
1. Initial creation returns the OTP (and arrivalOtp) to the client once.
2. Subsequent status polling (GET) never returns OTP or arrivalOtp.
3. A guest tracking token cannot verify arrival (strictly 403 Forbidden).
4. An unauthorized hospital administrator cannot verify another hospital's request (403 Forbidden).
5. Authorized hospital staff can verify arrival with valid OTP (200 OK, transitions hold -> occupied bed).
6. Repeated arrival verification is idempotent (does not alter bed counts twice).
"""

import uuid
import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.services.auth_service import AuthService
from backend_v2.services.capacity_service import CapacityService
from backend_v2.services.emergency_service import EmergencyService


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


def create_staff_token(role: str = "hospital_admin", hospital_id: int = 1) -> tuple:
    """Helper to generate verified test profile and Bearer JWT."""
    profile_repo = ProfileRepository()
    user_id = str(uuid.uuid4())
    email = f"{role}.{uuid.uuid4().hex[:8]}@hospital{hospital_id}.test"
    profile_repo.create_profile(
        user_id=user_id,
        full_name=f"Test {role.replace('_', ' ').title()}",
        email=email,
        role=role,
        hospital_id=hospital_id if role == "hospital_admin" else None,
        account_status="active",
    )
    auth_svc = AuthService(profile_repo=profile_repo)
    token = auth_svc._generate_jwt(user_id=user_id, email=email)
    return user_id, {"Authorization": f"Bearer {token}"}


# ── Test 1: Initial Creation Returns OTP ──────────────────────────────────────

def test_1_initial_creation_returns_otp(client):
    """1. Initial successful emergency creation returns arrival OTP and tracking token."""
    payload = {
        "hospitalId": "hsp-001",
        "emergencyCategory": "cardiac",
        "patientName": "Arogya Critical Patient",
        "contactPhone": "+919876543210",
        "userLocationName": "Indiranagar, Bangalore",
    }
    res = client.post("/api/emergency/sos", json=payload)
    assert res.status_code == 201
    data = res.get_json()

    # OTP must be present in creation response
    assert "otp" in data
    assert "arrivalOtp" in data
    assert len(str(data["otp"])) == 4
    assert str(data["otp"]).isdigit()
    assert data["otp"] == data["arrivalOtp"]

    # Plaintext tracking token returned for client storage
    assert "tracking_token" in data
    assert "trackingToken" in data
    assert len(data["tracking_token"]) >= 32

    # Internal hashes must never be exposed
    assert "guest_token_hash" not in data
    assert "tracking_token_hash" not in data
    assert "guest_token_hash" not in data["data"]
    assert "tracking_token_hash" not in data["data"]


# ── Test 2: Status Polling Does Not Return OTP ────────────────────────────────

def test_2_subsequent_status_polling_does_not_return_otp(client):
    """2. Subsequent status polling (GET) never returns OTP or arrivalOtp."""
    # Create SOS
    create_res = client.post("/api/coordination/request", json={
        "hospitalId": "hsp-001",
        "contactPhone": "+919876543211",
    })
    assert create_res.status_code == 201
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    token = sos_data["tracking_token"]

    # 1. Query via GET /api/emergency/<req_id> with query parameter token
    poll_res1 = client.get(f"/api/emergency/{req_id}?token={token}")
    assert poll_res1.status_code == 200
    poll_data1 = poll_res1.get_json()["data"]
    assert "otp" not in poll_data1
    assert "arrivalOtp" not in poll_data1
    assert "guest_token_hash" not in poll_data1
    assert "tracking_token_hash" not in poll_data1
    assert "tracking_token" not in poll_data1

    # 2. Query via GET /api/coordination/<req_id> with Authorization: Bearer
    poll_res2 = client.get(
        f"/api/coordination/{req_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert poll_res2.status_code == 200
    poll_data2 = poll_res2.get_json()["data"]
    assert "otp" not in poll_data2
    assert "arrivalOtp" not in poll_data2

    # 3. Query via GET /api/coordination/<req_id> with X-Tracking-Token
    poll_res3 = client.get(
        f"/api/coordination/{req_id}",
        headers={"X-Tracking-Token": token},
    )
    assert poll_res3.status_code == 200
    poll_data3 = poll_res3.get_json()["data"]
    assert "otp" not in poll_data3
    assert "arrivalOtp" not in poll_data3


# ── Test 3: Guest Tracking Token Cannot Verify Arrival ─────────────────────────

def test_3_guest_tracking_token_cannot_verify_arrival(client):
    """3. A guest tracking token alone must never authorize arrival verification."""
    create_res = client.post("/api/coordination/request", json={
        "hospitalId": "hsp-001",
        "contactPhone": "+919876543212",
    })
    assert create_res.status_code == 201
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    token = sos_data["tracking_token"]
    otp = sos_data["otp"]

    # Attempt 1: Using X-Tracking-Token header
    arr_attempt1 = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": otp},
        headers={"X-Tracking-Token": token},
    )
    assert arr_attempt1.status_code == 403
    assert "Guest tracking tokens cannot verify arrival" in arr_attempt1.get_json()["error"]["message"]

    # Attempt 2: Using tracking token as Authorization Bearer header
    arr_attempt2 = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": otp},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arr_attempt2.status_code in (401, 403)

    # Attempt 3: Supplying tracking token in request body
    arr_attempt3 = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": otp, "token": token},
    )
    assert arr_attempt3.status_code == 403

    # Attempt 4: No credentials at all
    arr_attempt4 = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": otp},
    )
    assert arr_attempt4.status_code == 401

    # Verify request status remains submitted and unverified
    status_check = client.get(f"/api/coordination/{req_id}?token={token}")
    assert status_check.get_json()["data"]["status"] == "REQUEST_SUBMITTED"


# ── Test 4: Unauthorized Hospital Admin Cannot Verify ─────────────────────────

def test_4_unauthorized_hospital_admin_cannot_verify_another_hospital(client):
    """4. An unauthorized hospital administrator cannot verify another hospital's request."""
    # Create request targeted at hospital 1
    create_res = client.post("/api/emergency/sos", json={
        "hospitalId": "hsp-001",
        "contactPhone": "+919876543213",
    })
    assert create_res.status_code == 201
    req_data = create_res.get_json()["data"]
    req_id = req_data["id"]
    otp = req_data["otp"]

    # Generate token for hospital admin of Hospital 2 (different hospital)
    _, hosp2_headers = create_staff_token(role="hospital_admin", hospital_id=2)

    # Attempt verification by hospital 2 admin
    unauth_res = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": otp},
        headers=hosp2_headers,
    )
    assert unauth_res.status_code == 403
    assert "You do not have permission to verify arrival for this hospital" in unauth_res.get_json()["error"]["message"]

    # Attempt verification by a patient user
    _, patient_headers = create_staff_token(role="patient")
    patient_res = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": otp},
        headers=patient_headers,
    )
    assert patient_res.status_code == 403
    assert "Only authorized hospital staff" in patient_res.get_json()["error"]["message"]


# ── Test 5: Authorized Staff Can Verify Arrival ───────────────────────────────

def test_5_authorized_staff_can_verify_arrival(client):
    """5. Authorized hospital staff can verify arrival (200 OK, converts hold to occupied bed)."""
    from backend_v2.repositories.capacity_repository import CapacityRepository
    cap_repo = CapacityRepository()
    cap_svc = CapacityService(capacity_repo=cap_repo)

    # Establish clean capacity baseline for test hospital 1
    cap_repo.update_capacity(1, {
        "total_beds": 100,
        "occupied_beds": 40,
        "available_beds": 60,
        "provisionally_allocated_beds": 0,
    })

    cap_before = cap_svc.get_live_capacity(1)
    base_avail = cap_before["available_beds"]
    base_occ = cap_before["occupied_beds"]

    # Create SOS targeted at Hospital 1
    create_res = client.post("/api/emergency/sos", json={
        "hospitalId": 1,
        "contactPhone": "+919876543214",
    })
    assert create_res.status_code == 201
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    otp = sos_data["otp"]

    # Verify provisional hold allocated
    cap_mid = cap_svc.get_live_capacity(1)
    assert cap_mid["available_beds"] == base_avail - 1
    assert cap_mid["provisionally_allocated_beds"] == 1

    # Generate token for Hospital 1 staff
    _, hosp1_headers = create_staff_token(role="hospital_admin", hospital_id=1)

    # Verify arrival
    verify_res = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": otp},
        headers=hosp1_headers,
    )
    assert verify_res.status_code == 200
    res_data = verify_res.get_json()
    assert res_data["success"] is True
    assert res_data["data"]["status"] == "PATIENT_ARRIVED"

    # Response must NOT leak arrival OTP
    assert "otp" not in res_data["data"]
    assert "arrivalOtp" not in res_data["data"]

    # Capacity transitioned: hold released, occupied beds incremented
    cap_after = cap_svc.get_live_capacity(1)
    assert cap_after["occupied_beds"] == base_occ + 1
    assert cap_after["provisionally_allocated_beds"] == 0


# ── Test 6: Arrival Verification Is Idempotent ────────────────────────────────

def test_6_arrival_verification_is_idempotent(client):
    """6. Repeated arrival verification is idempotent (does not alter bed counts twice)."""
    cap_svc = CapacityService()

    # Create SOS targeted at Hospital 1
    create_res = client.post("/api/emergency/sos", json={
        "hospitalId": 1,
        "contactPhone": "+919876543215",
    })
    assert create_res.status_code == 201
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    otp = sos_data["otp"]

    _, hosp1_headers = create_staff_token(role="hospital_admin", hospital_id=1)

    # First arrival verification
    arr1 = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": otp},
        headers=hosp1_headers,
    )
    assert arr1.status_code == 200
    assert arr1.get_json()["data"]["status"] == "PATIENT_ARRIVED"

    cap1 = cap_svc.get_live_capacity(1)
    occ1 = cap1["occupied_beds"]
    avail1 = cap1["available_beds"]

    # Second arrival verification (identical credentials & OTP)
    arr2 = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": otp},
        headers=hosp1_headers,
    )
    assert arr2.status_code == 200
    assert arr2.get_json()["data"]["status"] == "PATIENT_ARRIVED"

    cap2 = cap_svc.get_live_capacity(1)
    # Bed counts MUST remain identical (no double occupancy)
    assert cap2["occupied_beds"] == occ1
    assert cap2["available_beds"] == avail1
    assert cap2["provisionally_allocated_beds"] == cap1["provisionally_allocated_beds"]

    # Third arrival attempt with bad OTP should be rejected
    bad_arr = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": "0000"},
        headers=hosp1_headers,
    )
    assert bad_arr.status_code == 400
