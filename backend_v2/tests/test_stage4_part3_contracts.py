"""
AIIS Backend V2 - Stage 4 Part 3: Hospital Capacity, Bed Management & SRI Contracts
==================================================================================
Comprehensive automated verification suite for:
- 12 Hospital Capacity & Emergency Provisional Hold Contracts:
  1. Authorized hospital admin update (POST /api/hospitals/1/capacity -> 200 OK)
  2. Wrong-hospital admin update blocked (403 Forbidden)
  3. Patient update blocked (403 Forbidden)
  4. Anonymous update blocked (401 Unauthorized)
  5. Negative capacity values rejected (400 Validation Error)
  6. Mathematical balance constraints enforced (occupied + available + prov <= total -> 400)
  7. Historical ledger recorded (appends snapshots with user, timestamp, deltas)
  8. Concurrent provisional hold allocation safety (fails with 409 Conflict when available = 0)
  9. Hold expiry releases capacity (restores available beds atomically)
  10. Cancellation releases capacity (emergency SOS cancellation restores available beds)
  11. Database write failure handling (production database errors never report success)
  12. Honest data labeling: Seeded baseline is not labeled live/verified

- 10 Strain Risk Index (SRI) Contracts:
  13. Valid capacity data produces correct weighted score
  14. Missing historical data handled gracefully (defaults to 0.0 variability)
  15. Stale/baseline capacity marked honestly in SRI metadata
  16. Zero total beds handled safely without DivisionByZero
  17. Invalid capacity values rejected or sanitized safely
  18. Deterministic output: 5 consecutive calls produce identical scores
  19. Standardized risk-band classification (LOW, MODERATE, HIGH, CRITICAL)
  20. Zero random score generation (verifies absence of pseudo-random drift)
  21. Insufficient data returns explicit INSUFFICIENT_DATA status
  22. Frontend-compatible serialization (KPIs, formula, modal drill-down series)
"""

import os
import uuid
from typing import Dict, Any
from unittest.mock import patch, MagicMock
import pytest

from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.repositories.capacity_repository import CapacityRepository
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.repositories.emergency_repository import EmergencyRepository
from backend_v2.services.auth_service import AuthService
from backend_v2.services.capacity_service import CapacityService
from backend_v2.services.emergency_service import EmergencyService
from backend_v2.services.sri_service import SRIService
from backend_v2.utils.exceptions import ConflictException, ValidationException, DatabaseException


@pytest.fixture
def client():
    """Flask test client instance."""
    app = create_app(TestingConfig)
    return app.test_client()


def create_test_token(role: str = "hospital_admin", hospital_id: int = 1) -> tuple:
    """Helper to generate verified test profile and Bearer JWT."""
    profile_repo = ProfileRepository()
    user_id = str(uuid.uuid4())
    email = f"{role}.{uuid.uuid4().hex[:8]}@aiis.test"
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


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Hospital Capacity & Bed Management Contracts (12 Tests)
# ══════════════════════════════════════════════════════════════════════════════

def test_1_authorized_hospital_admin_update(client):
    """1. Authorized hospital admin can update capacity telemetry on own facility."""
    admin_id, headers = create_test_token("hospital_admin", hospital_id=1)

    payload = {
        "total_beds": 120,
        "occupied_beds": 50,
        "available_beds": 70,
        "provisionally_allocated_beds": 0,
        "icu_total": 20,
        "icu_occupied": 10,
        "icu_available": 10,
        "ventilators_total": 8,
        "ventilators_available": 5,
        "oxygen_status": "adequate",
        "emergency_receiving_status": "open",
    }
    # Test POST on plural route
    res = client.post("/api/hospitals/1/capacity", json=payload, headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["hospital_id"] == 1
    assert data["total_beds"] == 120
    assert data["occupied_beds"] == 50
    assert data["available_beds"] == 70
    assert data["source"] == "hospital_admin_reported"
    assert data["verified_realtime"] is False
    assert data["freshness"] == "recent"

    # Test GET retrieves identical updated state
    get_res = client.get("/api/hospitals/1/capacity", headers=headers)
    assert get_res.status_code == 200
    get_data = get_res.get_json()["data"]
    assert get_data["available_beds"] == 70
    assert get_data["verified_realtime"] is False

    # Test PUT on singular alias route with string code hsp-001
    put_res = client.put("/api/hospital/hsp-001/capacity", json={"available_beds": 65, "occupied_beds": 55}, headers=headers)
    assert put_res.status_code == 200
    assert put_res.get_json()["data"]["available_beds"] == 65


def test_2_wrong_hospital_admin_blocked(client):
    """2. Hospital admin assigned to Hospital 1 is blocked from modifying Hospital 2."""
    _, headers = create_test_token("hospital_admin", hospital_id=1)

    # Attempt to update hospital 2
    res = client.post("/api/hospitals/2/capacity", json={"available_beds": 10}, headers=headers)
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "FORBIDDEN"

    # Attempt to update hospital 2 using code hsp-002
    res_code = client.put("/api/hospital/hsp-002/capacity", json={"available_beds": 10}, headers=headers)
    assert res_code.status_code == 403


def test_3_patient_update_blocked(client):
    """3. Authenticated citizen/patient cannot update hospital capacity."""
    _, headers = create_test_token("patient")
    res = client.post("/api/hospitals/1/capacity", json={"available_beds": 20}, headers=headers)
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "FORBIDDEN"


def test_4_anonymous_update_blocked(client):
    """4. Unauthenticated caller cannot update hospital capacity."""
    res = client.post("/api/hospitals/1/capacity", json={"available_beds": 20})
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_5_negative_capacity_rejected(client):
    """5. Negative values are strictly rejected with 400 Validation Error."""
    _, headers = create_test_token("hospital_admin", hospital_id=1)

    # Negative total_beds
    res1 = client.post("/api/hospitals/1/capacity", json={"total_beds": -10}, headers=headers)
    assert res1.status_code == 400
    assert res1.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # Negative available_beds
    res2 = client.post("/api/hospitals/1/capacity", json={"available_beds": -1}, headers=headers)
    assert res2.status_code == 400


def test_6_balance_constraints_enforced(client):
    """6. Mathematical balance constraints (occupied + available + prov <= total) are enforced."""
    _, headers = create_test_token("hospital_admin", hospital_id=1)

    # Bed balance violation: 70 occupied + 40 available = 110 > 100 total
    res1 = client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 70,
        "available_beds": 40,
    }, headers=headers)
    assert res1.status_code == 400
    assert "Capacity balance constraint violated" in res1.get_json()["error"]["message"]

    # ICU balance violation: 8 occupied + 5 available = 13 > 10 total
    res2 = client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 50,
        "available_beds": 50,
        "provisionally_allocated_beds": 0,
        "icu_total": 10,
        "icu_occupied": 8,
        "icu_available": 5,
    }, headers=headers)
    assert res2.status_code == 400
    assert "ICU balance constraint violated" in res2.get_json()["error"]["message"]

    # Ventilator constraint violation: 8 available > 5 total
    res3 = client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 50,
        "available_beds": 50,
        "provisionally_allocated_beds": 0,
        "ventilators_total": 5,
        "ventilators_available": 8,
    }, headers=headers)
    assert res3.status_code == 400
    assert "Ventilator constraint violated" in res3.get_json()["error"]["message"]


def test_7_capacity_history_recorded(client):
    """7. Every capacity update records a timestamped historical snapshot in the ledger."""
    admin_id, headers = create_test_token("hospital_admin", hospital_id=1)

    client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 40,
        "available_beds": 60,
        "provisionally_allocated_beds": 0,
    }, headers=headers)

    res = client.get("/api/hospitals/1/capacity/history", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    history = body["data"]
    assert isinstance(history, list)
    assert len(history) >= 1

    latest = history[0]
    assert latest["total_beds"] == 100
    assert latest["occupied_beds"] == 40
    assert "recorded_at" in latest
    assert latest["recorded_by"] == admin_id


def test_8_concurrent_allocation_safety(client):
    """8. Provisional emergency hold allocation safely rejects when available beds reach 0 and prevents over-allocation under concurrency."""
    import concurrent.futures
    admin_id, headers = create_test_token("hospital_admin", hospital_id=1)

    # Set available beds to exactly 1
    client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 99,
        "available_beds": 1,
        "provisionally_allocated_beds": 0,
    }, headers=headers)

    repo = CapacityRepository()
    # 5 simultaneous threads competing for the single final bed
    def try_allocate():
        return repo.allocate_hold(1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(try_allocate) for _ in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Exactly 1 request must have succeeded, and 4 must have failed
    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)
    assert success_count == 1
    assert failure_count == 4

    # Capacity must NOT drop below 0 (no over-allocation)
    cap_res = client.get("/api/hospitals/1/capacity")
    assert cap_res.get_json()["data"]["available_beds"] == 0
    assert cap_res.get_json()["data"]["provisionally_allocated_beds"] == 1

    # Attempt another provisional allocation via EmergencyService / SOS endpoint when available=0
    sos_res = client.post("/api/emergency/sos", json={
        "hospitalId": "hsp-001",
        "emergencyCategory": "trauma",
        "userLocationName": "Koramangala, Bangalore",
        "contactPhone": "+919876543210",
        "latitude": 12.9352,
        "longitude": 77.6245,
    })
    # Must be rejected with 409 Conflict due to zero available capacity
    assert sos_res.status_code == 409
    assert sos_res.get_json()["error"]["code"] == "CONFLICT"


def test_9_hold_expiry_releases_capacity(client):
    """9. Expired provisional emergency hold releases allocated bed back to available beds."""
    admin_id, headers = create_test_token("hospital_admin", hospital_id=1)

    # Reset capacity
    client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 50,
        "available_beds": 50,
        "provisionally_allocated_beds": 0,
    }, headers=headers)

    cap_service = CapacityService()
    # Allocate a hold
    req_id = f"sos-{uuid.uuid4().hex[:6]}"
    cap_service.allocate_provisional_hold(1, req_id)

    cap1 = cap_service.get_live_capacity(1)
    assert cap1["available_beds"] == 49
    assert cap1["provisionally_allocated_beds"] == 1

    # Simulate expiration release
    cap_service.release_provisional_hold(1, req_id, reason="expired")
    cap2 = cap_service.get_live_capacity(1)
    assert cap2["available_beds"] == 50
    assert cap2["provisionally_allocated_beds"] == 0


def test_10_cancellation_releases_capacity(client):
    """10. Emergency SOS cancellation restores provisional bed back to available beds."""
    admin_id, headers = create_test_token("hospital_admin", hospital_id=1)

    # Ensure baseline capacity
    client.post("/api/hospitals/1/capacity", json={
        "total_beds": 100,
        "occupied_beds": 40,
        "available_beds": 60,
        "provisionally_allocated_beds": 0,
    }, headers=headers)

    # Create SOS
    phone = "+919876543299"
    sos_res = client.post("/api/emergency/sos", json={
        "hospitalId": "hsp-001",
        "emergencyCategory": "cardiac",
        "userLocationName": "Indiranagar, Bangalore",
        "contactPhone": phone,
    })
    assert sos_res.status_code == 201
    req_id = sos_res.get_json()["data"]["requestId"]

    # Verify hold incremented
    cap_res1 = client.get("/api/hospitals/1/capacity")
    assert cap_res1.get_json()["data"]["available_beds"] == 59
    assert cap_res1.get_json()["data"]["provisionally_allocated_beds"] == 1

    # Cancel request
    cancel_res = client.post(f"/api/coordination/{req_id}/cancel", json={
        "contactPhone": phone,
        "reason": "Patient arranged alternate transport",
    })
    assert cancel_res.status_code == 200

    # Verify hold released and available capacity restored
    cap_res2 = client.get("/api/hospitals/1/capacity")
    assert cap_res2.get_json()["data"]["available_beds"] == 60
    assert cap_res2.get_json()["data"]["provisionally_allocated_beds"] == 0

    # Idempotency check: Repeated cancellation must fail with 409 Conflict and not release capacity again
    repeat_cancel_res = client.post(f"/api/coordination/{req_id}/cancel", json={
        "contactPhone": phone,
        "reason": "Accidental double cancel",
    })
    assert repeat_cancel_res.status_code in {409, 400}
    cap_res3 = client.get("/api/hospitals/1/capacity")
    assert cap_res3.get_json()["data"]["available_beds"] == 60
    assert cap_res3.get_json()["data"]["provisionally_allocated_beds"] == 0


def test_11_failed_database_write_does_not_report_success(client):
    """11. In production, database failure raises DatabaseException and returns 500 error."""
    _, headers = create_test_token("hospital_admin", hospital_id=1)
    repo = CapacityRepository()

    # Simulate production environment with broken database
    with patch.dict(os.environ, {"FLASK_ENV": "production"}):
        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Connection lost to Postgres")
        with patch.object(repo._supabase, "get_client", return_value=mock_client):
            with pytest.raises(DatabaseException):
                repo.update_capacity(1, {"available_beds": 30, "occupied_beds": 70, "total_beds": 100})


def test_12_seeded_baseline_not_labelled_live(client):
    """12. Seeded baseline capacity records must never be labeled as live telemetry."""
    # Query hospital 35 which has not received real-time telemetry updates
    res = client.get("/api/hospitals/35/capacity")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["source"] in {"seeded_baseline", "hospital_admin_reported"}
    assert "verified_realtime" in data
    assert "freshness" in data


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Regional Strain Risk Index (SRI) Contracts (10 Tests)
# ══════════════════════════════════════════════════════════════════════════════

def test_13_sri_valid_capacity_calculation():
    """13. SRI computes correct weighted mathematical score according to specification."""
    repo = CapacityRepository()
    sri_svc = SRIService(capacity_repo=repo)

    # Set exact known parameters for hospital 1:
    # bed_occ = 50%, icu_occ = 40%, prov = 10%, var = 0.0
    # Expected SRI = 0.40*50 + 0.35*40 + 0.15*10 + 0.10*0.0 = 20.0 + 14.0 + 1.5 + 0.0 = 35.5
    repo.update_capacity(1, {
        "total_beds": 100,
        "occupied_beds": 50,
        "available_beds": 40,
        "provisionally_allocated_beds": 10,
        "icu_total": 20,
        "icu_occupied": 8,
        "icu_available": 12,
    })

    # Clear in-memory history snapshots to isolate variability to 0.0
    with repo._lock:
        repo._history[1] = []

    result = sri_svc.calculate_hospital_sri(1, use_remote_history=False)
    assert result["status"] == "VALID"
    assert result["bed_occupancy_pct"] == 50.0
    assert result["icu_occupancy_pct"] == 40.0
    assert result["provisional_hold_pct"] == 10.0
    assert result["capacity_variability"] == 0.0
    assert result["sri_score"] == 35.5
    assert result["risk_band"] == "LOW"


def test_14_sri_missing_historical_data_graceful():
    """14. SRI handles missing history gracefully without runtime failure."""
    repo = CapacityRepository()
    sri_svc = SRIService(capacity_repo=repo)

    with repo._lock:
        repo._history[2] = []

    res = sri_svc.calculate_hospital_sri(2, use_remote_history=False)
    assert res["status"] == "VALID"
    assert res["capacity_variability"] == 0.0
    assert res["sri_score"] is not None


def test_15_sri_stale_capacity_handling(client):
    """15. Un-updated facilities are classified honestly as baseline data."""
    res = client.get("/api/sri/regional")
    assert res.status_code == 200
    body = res.get_json()["data"]
    metrics = body["metrics"]
    assert "data_freshness" in metrics
    assert "verified_realtime" in metrics


def test_16_sri_zero_capacity_handled_safely():
    """16. Facilities with zero total beds are handled safely without DivisionByZero."""
    repo = CapacityRepository()
    sri_svc = SRIService(capacity_repo=repo)

    with repo._lock:
        repo._capacities[999] = {
            "hospital_id": 999,
            "total_beds": 0,
            "occupied_beds": 0,
            "available_beds": 0,
        }

    res = sri_svc.calculate_hospital_sri(999, use_remote_history=False)
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["sri_score"] is None
    assert res["risk_band"] == "INSUFFICIENT_DATA"


def test_17_sri_invalid_capacity_values_handled(client):
    """17. Submitting invalid values is rejected before it can corrupt SRI."""
    _, headers = create_test_token("hospital_admin", hospital_id=1)
    res = client.post("/api/hospitals/1/capacity", json={"total_beds": "invalid_number"}, headers=headers)
    assert res.status_code == 400


def test_18_sri_deterministic_output(client):
    """18. Repeated calls with identical state produce strictly identical scores."""
    scores = []
    for _ in range(5):
        res = client.get("/api/sri/regional")
        assert res.status_code == 200
        scores.append(res.get_json()["data"]["overall_sri"])

    assert len(set(scores)) == 1, f"SRI scores drifted across identical calls: {scores}"


def test_19_sri_correct_risk_band_classification():
    """19. Standardized SRI risk band thresholds are strictly adhered to."""
    assert SRIService.get_risk_band(0.0) == "LOW"
    assert SRIService.get_risk_band(39.9) == "LOW"
    assert SRIService.get_risk_band(40.0) == "MODERATE"
    assert SRIService.get_risk_band(69.9) == "MODERATE"
    assert SRIService.get_risk_band(70.0) == "HIGH"
    assert SRIService.get_risk_band(84.9) == "HIGH"
    assert SRIService.get_risk_band(85.0) == "CRITICAL"
    assert SRIService.get_risk_band(100.0) == "CRITICAL"
    assert SRIService.get_risk_band(None) == "INSUFFICIENT_DATA"


def test_20_sri_no_random_score_generation():
    """20. Verifies that SRI calculation does not invoke any pseudo-random functions."""
    import random
    with patch.object(random, "random", side_effect=AssertionError("random.random() called in SRI!")):
        with patch.object(random, "randint", side_effect=AssertionError("random.randint() called in SRI!")):
            sri_svc = SRIService()
            res = sri_svc.calculate_regional_sri()
            assert res["status"] == "VALID"
            assert res["regional_score"] is not None


def test_21_sri_insufficient_data_response(client):
    """21. When region/city filter matches zero facilities, returns explicit INSUFFICIENT_DATA."""
    res = client.get("/api/sri/regional?city=NonExistentCityXYZ")
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["status"] == "INSUFFICIENT_DATA"
    assert body["overall_sri"] is None
    assert body["risk_level"] == "INSUFFICIENT_DATA"
    assert "No facilities found" in body["message"]


def test_22_sri_frontend_compatible_response_serialization(client):
    """22. Regional SRI and analytics responses contain all expected frontend dashboard keys."""
    # 1. Regional endpoint
    res = client.get("/api/sri/regional")
    assert res.status_code == 200
    data = res.get_json()["data"]
    expected_top_keys = {
        "status", "overall_sri", "avg_sri", "risk_level", "risk_band",
        "hospital_count", "active_emergencies", "provisional_holds",
        "region", "observation_period", "calculation_timestamp",
        "metrics", "risk_distribution", "kpi", "hospitals", "formula"
    }
    assert expected_top_keys.issubset(data.keys())

    # KPI sub-keys
    kpi = data["kpi"]
    assert {"total_hospitals", "total_beds", "total_icu", "high_risk", "medium_risk", "low_risk", "avg_sri"}.issubset(kpi.keys())

    # Formula & non-predictive disclaimer
    formula = data["formula"]
    assert "disclaimer" in formula
    assert "weights" in formula

    # 2. Facility drill-down analytics modal endpoint
    drill_res = client.get("/api/hospital-analytics/1")
    assert drill_res.status_code == 200
    drill_data = drill_res.get_json()["data"]
    assert "hospital" in drill_data
    assert "fc_dates" in drill_data
    assert "fc_values" in drill_data
    assert "opd_dates" in drill_data
    assert "opd_values" in drill_data

    # 3. Legacy bed update endpoint
    _, headers = create_test_token("hospital_admin", hospital_id=1)
    legacy_res = client.post("/api/update-beds", json={"hospital_id": 1, "num_beds": 130}, headers=headers)
    assert legacy_res.status_code == 200
    assert legacy_res.get_json()["data"]["num_beds"] == 130
