"""
AIIS Backend V2 - Frontend Contract & Emergency Integration Tests
=================================================================
Automated verification of the 12 contract requirements for frontend integration:
1. Frontend hospital ID mapping ('hsp-001' <-> 1, rejection of malformed IDs)
2. Emergency hospital search (POST /api/emergency/search & GET /api/emergency/hospitals)
3. Hospital profile details (GET /api/hospitals/1 & GET /api/hospitals/hsp-001)
4. Coordination SOS creation (POST /api/coordination/request with 'hsp-001')
5. Guest SOS tracking (GET /api/coordination/<id>?token=...)
6. Invalid tracking token rejection (401 Unauthorized)
7. Invalid arrival OTP rejection (400 Validation Error)
8. Emergency SOS cancellation (POST /api/coordination/<id>/cancel)
9. Patient arrival verification (POST /api/coordination/<id>/verify-arrival)
10. Unknown or unmapped hospital ID handling (400/404)
11. CORS preflight OPTIONS from frontend origins (http://localhost:5173, etc.)
12. Compatibility aliases and existing V2 routes regression
"""

import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    to_frontend_hospital_id,
    enrich_hospital_identifiers,
)
from backend_v2.utils.exceptions import ValidationException


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


# ── 1. Frontend Hospital ID Mapping ──────────────────────────────────────────

def test_frontend_hospital_id_mapping():
    """Verify deterministic bidirectional mapping between string and integer IDs."""
    # 1. String 'hsp-XXX' -> int
    assert to_canonical_hospital_id("hsp-001") == 1
    assert to_canonical_hospital_id("hsp-012") == 12
    assert to_canonical_hospital_id("HSP-036") == 36
    assert to_canonical_hospital_id("hsp-1") == 1

    # 2. String numeric -> int
    assert to_canonical_hospital_id("1") == 1
    assert to_canonical_hospital_id("36") == 36

    # 3. Direct int -> int
    assert to_canonical_hospital_id(1) == 1
    assert to_canonical_hospital_id(36) == 36

    # 4. Canonical int -> Frontend 'hsp-XXX'
    assert to_frontend_hospital_id(1) == "hsp-001"
    assert to_frontend_hospital_id(12) == "hsp-012"
    assert to_frontend_hospital_id(36) == "hsp-036"

    # 5. Malformed or negative IDs -> ValidationException
    invalid_ids = ["xyz", "hsp-abc", "hsp-", "", " ", -1, 0, None]
    for bad_id in invalid_ids:
        with pytest.raises(ValidationException):
            to_canonical_hospital_id(bad_id)

    # 6. Record enrichment
    raw_record = {
        "id": 1,
        "name": "Victoria Hospital",
        "lat": 12.9635,
        "lon": 77.5734,
    }
    enriched = enrich_hospital_identifiers(raw_record)
    assert enriched["code"] == "hsp-001"
    assert enriched["hospital_code"] == "hsp-001"
    assert enriched["frontend_id"] == "hsp-001"
    assert enriched["latitude"] == 12.9635
    assert enriched["longitude"] == 77.5734
    assert enriched["lng"] == 77.5734


# ── 2. Emergency Search ───────────────────────────────────────────────────────

def test_emergency_search(client):
    """Verify POST /api/emergency/search and GET /api/emergency/hospitals."""
    # POST with GPS coordinates and clinical category
    post_payload = {
        "latitude": 12.9635,
        "longitude": 77.5734,
        "category": "cardiac",
        "limit": 5,
    }
    res = client.post("/api/emergency/search", json=post_payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "results" in data
    assert len(data["results"]) > 0

    first_hosp = data["results"][0]
    assert "id" in first_hosp
    assert "code" in first_hosp
    assert first_hosp["code"].startswith("hsp-")
    assert "distance_km" in first_hosp
    assert "transit_minutes" in first_hosp
    assert "whyRanked" in first_hosp

    # Alias with lat / lng field names
    alias_payload = {
        "lat": 12.9635,
        "lng": 77.5734,
        "category": "trauma",
        "limit": 3,
    }
    alias_res = client.post("/api/emergency/search", json=alias_payload)
    assert alias_res.status_code == 200
    alias_data = alias_res.get_json()
    assert len(alias_data["results"]) > 0

    # GET query param format (patient_entry.html)
    get_res = client.get("/api/emergency/hospitals?lat=12.9635&lon=77.5734&emergency_type=stroke")
    assert get_res.status_code == 200
    get_data = get_res.get_json()
    assert len(get_data["results"]) > 0


# ── 3. Hospital Details ───────────────────────────────────────────────────────

def test_hospital_details(client):
    """Verify GET /api/hospitals/:id accepts both integer and 'hsp-XXX' string."""
    # Using canonical integer
    res_int = client.get("/api/hospitals/1")
    assert res_int.status_code == 200
    data_int = res_int.get_json()
    assert data_int["success"] is True
    assert data_int["data"]["id"] == 1
    assert data_int["data"]["code"] == "hsp-001"
    assert "Victoria Hospital" in data_int["data"]["name"]

    # Using frontend string identifier
    res_str = client.get("/api/hospitals/hsp-001")
    assert res_str.status_code == 200
    data_str = res_str.get_json()
    assert data_str["success"] is True
    assert data_str["data"]["id"] == 1
    assert data_str["data"]["code"] == "hsp-001"
    assert "Victoria Hospital" in data_str["data"]["name"]

    # Hospital 2 Bowring
    res_hsp2 = client.get("/api/hospitals/hsp-002")
    assert res_hsp2.status_code == 200
    assert res_hsp2.get_json()["data"]["id"] == 2

    # Departments endpoint with frontend string ID
    dept_res = client.get("/api/hospitals/hsp-001/departments")
    assert dept_res.status_code == 200
    assert dept_res.get_json()["success"] is True


# ── 4. Coordination Creation ──────────────────────────────────────────────────

def test_coordination_creation(client):
    """Verify POST /api/coordination/request with frontend payload and guest token generation."""
    payload = {
        "hospitalId": "hsp-001",
        "emergencyCategory": "cardiac",
        "patientName": "Ramesh Kumar",
        "companionName": "Suresh Kumar",
        "contactPhone": "+919876543210",
        "estimatedTravelMinutes": 15,
        "userLocationName": "Majestic Bus Station, Bengaluru",
        "latitude": 12.9767,
        "longitude": 77.5713,
        "notes": "Patient reports radiating chest pain and breathlessness.",
    }
    res = client.post("/api/coordination/request", json=payload)
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True

    record = body["data"]
    assert record["id"].startswith("REQ-")
    assert record["hospitalId"] == 1
    assert record["hospitalCode"] == "hsp-001"
    assert record["status"] == "REQUEST_SUBMITTED"
    assert len(record["otp"]) == 4
    assert record["otp"].isdigit()
    assert "holdExpiresAt" in record

    # Plaintext guest tracking token returned once at creation
    assert "tracking_token" in record
    assert len(record["tracking_token"]) >= 32
    # Internal token hashes must NEVER be exposed
    assert "guest_token_hash" not in record
    assert "tracking_token_hash" not in record


# ── 5. Guest Tracking ─────────────────────────────────────────────────────────

def test_guest_tracking(client):
    """Verify GET /api/coordination/:id?token=... succeeds with valid tracking token."""
    # Create SOS
    create_res = client.post("/api/coordination/request", json={"hospitalId": "hsp-001"})
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    token = sos_data["tracking_token"]

    # Poll status using valid query token
    track_res = client.get(f"/api/coordination/{req_id}?token={token}")
    assert track_res.status_code == 200
    track_data = track_res.get_json()
    assert track_data["success"] is True
    assert track_data["data"]["id"] == req_id
    assert track_data["data"]["status"] == "REQUEST_SUBMITTED"

    # Verify security: tracking token, internal hash, and arrival OTP must not leak in GET status response
    assert "guest_token_hash" not in track_data["data"]
    assert "tracking_token_hash" not in track_data["data"]
    assert "tracking_token" not in track_data["data"]
    assert "otp" not in track_data["data"]
    assert "arrivalOtp" not in track_data["data"]


# ── 6. Invalid Tracking Token ─────────────────────────────────────────────────

def test_invalid_tracking_token(client):
    """Verify GET /api/coordination/:id?token=... rejects tampered/invalid token with 401."""
    create_res = client.post("/api/coordination/request", json={"hospitalId": "hsp-001"})
    req_id = create_res.get_json()["data"]["id"]

    # Poll with bad token
    bad_res = client.get(f"/api/coordination/{req_id}?token=invalid_forged_token_12345")
    assert bad_res.status_code == 401
    bad_data = bad_res.get_json()
    assert bad_data["success"] is False
    assert bad_data["error"]["code"] == "UNAUTHORIZED"


def _get_staff_headers(hospital_id: int = 1):
    import uuid
    from backend_v2.repositories.profile_repository import ProfileRepository
    from backend_v2.services.auth_service import AuthService
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


# ── 7. Invalid OTP ────────────────────────────────────────────────────────────

def test_invalid_otp(client):
    """Verify arrival verification rejects incorrect or non-numeric OTP with 400."""
    create_res = client.post("/api/coordination/request", json={"hospitalId": "hsp-001"})
    req_id = create_res.get_json()["data"]["id"]
    headers = _get_staff_headers(1)

    # Wrong 4-digit code
    wrong_res = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": "0000"},
        headers=headers,
    )
    assert wrong_res.status_code == 400
    wrong_data = wrong_res.get_json()
    assert wrong_data["success"] is False
    assert wrong_data["error"]["code"] == "VALIDATION_ERROR"

    # Malformed non-4-digit OTP
    malformed_res = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": "abc"},
        headers=headers,
    )
    assert malformed_res.status_code == 400


# ── 8. Cancellation ───────────────────────────────────────────────────────────

def test_cancellation(client):
    """Verify POST /api/coordination/:id/cancel cancels request and sets status."""
    create_res = client.post("/api/coordination/request", json={"hospitalId": "hsp-001"})
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    token = sos_data["tracking_token"]

    cancel_res = client.post(
        f"/api/coordination/{req_id}/cancel",
        json={"token": token, "reason": "Patient diverted to nearby private hospital"},
    )
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.get_json()
    assert cancel_data["success"] is True
    assert cancel_data["data"]["status"] == "CANCELLED"

    # Repeated cancellation attempt should yield 409 Conflict
    repeat_res = client.post(
        f"/api/coordination/{req_id}/cancel",
        json={"token": token, "reason": "Another cancel"},
    )
    assert repeat_res.status_code == 409


# ── 9. Arrival Verification ───────────────────────────────────────────────────

def test_arrival_verification(client):
    """Verify POST /api/coordination/:id/verify-arrival with correct OTP."""
    create_res = client.post("/api/coordination/request", json={"hospitalId": "hsp-001"})
    sos_data = create_res.get_json()["data"]
    req_id = sos_data["id"]
    valid_otp = sos_data["otp"]
    headers = _get_staff_headers(1)

    verify_res = client.post(
        f"/api/coordination/{req_id}/verify-arrival",
        json={"otp": valid_otp},
        headers=headers,
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.get_json()
    assert verify_data["success"] is True
    assert verify_data["data"]["status"] == "PATIENT_ARRIVED"

    # Cannot cancel an arrived patient
    cancel_after_res = client.post(
        f"/api/coordination/{req_id}/cancel",
        json={"reason": "Cancel after arrival"},
    )
    assert cancel_after_res.status_code == 409


# ── 10. Unknown Hospital ID ───────────────────────────────────────────────────

def test_unknown_hospital_id(client):
    """Verify that unmapped, out-of-range, or malformed hospital IDs fail gracefully."""
    # Malformed string format in coordination request
    res_malformed = client.post("/api/coordination/request", json={"hospitalId": "hsp-xyz"})
    assert res_malformed.status_code == 400
    assert res_malformed.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Out of range hospital ID in coordination request
    res_not_found = client.post("/api/coordination/request", json={"hospitalId": "hsp-999"})
    assert res_not_found.status_code == 404
    assert res_not_found.get_json()["error"]["code"] == "NOT_FOUND"

    # Malformed / unknown route in GET /api/hospitals/:id
    res_bad_get = client.get("/api/hospitals/not-a-valid-id")
    assert res_bad_get.status_code == 404
    assert res_bad_get.get_json()["error"]["code"] == "NOT_FOUND"

    # Non-existent ID in GET /api/hospitals/:id
    res_missing_get = client.get("/api/hospitals/999")
    assert res_missing_get.status_code == 404


# ── 11. CORS Preflight from Frontend Origin ───────────────────────────────────

def test_cors_preflight_from_frontend_origin(client):
    """Verify CORS OPTIONS preflight returns allow headers for frontend origins."""
    allowed_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5000",
        "https://aiis-livid.vercel.app",
    ]

    for origin in allowed_origins:
        res = client.open(
            "/api/coordination/request",
            method="OPTIONS",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,Authorization",
            },
        )
        assert res.status_code in (200, 204)
        assert res.headers.get("Access-Control-Allow-Origin") == origin
        assert "POST" in res.headers.get("Access-Control-Allow-Methods", "")


# ── 12. Compatibility Aliases & V2 Routes ─────────────────────────────────────

def test_compatibility_aliases_and_v2_routes(client):
    """Verify that both legacy/frontend paths and native Backend V2 paths work identically."""
    # 1. Locations directory
    res_locs = client.get("/api/locations")
    assert res_locs.status_code == 200
    assert "locations" in res_locs.get_json()
    assert len(res_locs.get_json()["locations"]) > 0

    # Singular alias /api/location
    res_loc = client.get("/api/location")
    assert res_loc.status_code == 200
    assert "locations" in res_loc.get_json()

    # 2. Coordination alias routes match emergency routes
    # Create via POST /api/emergency/sos
    sos_res = client.post("/api/emergency/sos", json={"hospitalId": 1})
    assert sos_res.status_code == 201
    sos_id = sos_res.get_json()["data"]["id"]

    # Status via GET /api/emergency/:id
    get_emergency = client.get(f"/api/emergency/{sos_id}")
    assert get_emergency.status_code == 200
    assert get_emergency.get_json()["data"]["id"] == sos_id

    # Verify arrival via POST /api/emergency/:id/verify-arrival
    otp = sos_res.get_json()["data"]["otp"]
    arr_res = client.post(
        f"/api/emergency/{sos_id}/verify-arrival",
        json={"otp": otp},
        headers=_get_staff_headers(1),
    )
    assert arr_res.status_code == 200
    assert arr_res.get_json()["data"]["status"] == "PATIENT_ARRIVED"

    # Health check remains operational
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    health_data = health_res.get_json()
    assert health_data["data"]["status"] == "healthy" or health_data.get("status") == "healthy"
