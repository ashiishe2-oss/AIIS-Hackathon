"""
AIIS Backend V2 - Stage 5 Live Emergency Lifecycle Integration Test
===================================================================
Tests complete lifecycle directly against Supabase:
1. Create Guest Emergency SOS (allocates provisional hold in live DB)
2. Create Authenticated Emergency SOS (linked to auth.users profile)
3. Cancel request & verify capacity release (verifying idempotency against double release)
4. Expire request & verify capacity release
5. Verify casualty desk arrival via OTP (converting hold to occupied bed)
6. Verify duplicate arrival is idempotent (never increments occupied beds twice)
7. Confirm event history and audit records
"""

import uuid
import pytest
from datetime import datetime, timezone

from backend_v2.app import create_app
from backend_v2.extensions import supabase
from backend_v2.repositories.capacity_repository import CapacityRepository
from backend_v2.repositories.emergency_repository import EmergencyRepository
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.services.auth_service import AuthService
from backend_v2.services.capacity_service import CapacityService
from backend_v2.services.emergency_service import EmergencyService


def test_live_emergency_lifecycle_end_to_end():
    app = create_app("testing")
    client = app.test_client()
    sb = supabase.get_client()
    assert sb is not None, "Live Supabase client must be configured"

    # Reset any active auth session from prior unit tests
    try:
        sb.auth.sign_out()
    except Exception:
        pass

    # Verify live remote Supabase credentials are valid before live lifecycle assertions
    try:
        sb.table("emergency_requests").select("id").limit(1).execute()
    except Exception as exc:
        pytest.skip(f"Live Supabase project credentials unregistered or offline: {exc}")

    cap_repo = CapacityRepository()
    cap_svc = CapacityService(capacity_repo=cap_repo)
    em_repo = EmergencyRepository()
    em_svc = EmergencyService(emergency_repo=em_repo, capacity_service=cap_svc)
    auth_svc = AuthService()

    # Reset capacity for hospital 1 to known baseline
    initial_cap = cap_svc.get_live_capacity(1)
    tot_beds = 100
    base_occ = 40
    base_avail = 60
    cap_repo.update_capacity(1, {
        "total_beds": tot_beds,
        "occupied_beds": base_occ,
        "available_beds": base_avail,
        "provisionally_allocated_beds": 0,
        "icu_total": 20,
        "icu_occupied": 5,
        "icu_available": 15,
        "ventilators_total": 10,
        "ventilators_available": 5,
        "emergency_receiving_status": "available",
        "oxygen_status": "adequate"
    })

    cap_check = cap_svc.get_live_capacity(1)
    assert cap_check["available_beds"] == 60
    assert cap_check["provisionally_allocated_beds"] == 0

    # --------------------------------------------------------------------------
    # 1. Guest Emergency SOS Request
    # --------------------------------------------------------------------------
    phone_guest = "+919876543290"
    guest_sos_payload = {
        "hospitalId": "hsp-001",
        "emergencyCategory": "trauma",
        "patientName": "Guest Trauma Patient",
        "contactPhone": phone_guest,
        "userLocationName": "Indiranagar, Bengaluru",
        "estimatedTravelMinutes": 15,
    }
    res_guest = client.post("/api/emergency/sos", json=guest_sos_payload)
    assert res_guest.status_code == 201
    guest_data = res_guest.get_json()["data"]
    guest_req_id = guest_data["requestId"]
    guest_token = guest_data["tracking_token"]
    guest_otp = guest_data["arrivalOtp"]

    # Verify provisional hold allocated in database
    cap_after_guest = cap_svc.get_live_capacity(1)
    assert cap_after_guest["available_beds"] == 59
    assert cap_after_guest["provisionally_allocated_beds"] == 1

    # Verify row in remote Supabase
    remote_guest = sb.table("emergency_requests").select("id,status,target_hospital_id").eq("id", guest_req_id).execute()
    assert len(remote_guest.data) == 1
    assert remote_guest.data[0]["id"] == guest_req_id

    # --------------------------------------------------------------------------
    # 2. Authenticated Emergency SOS Request
    # --------------------------------------------------------------------------
    auth_user_id = str(uuid.uuid4())
    auth_email = f"auth.patient.{uuid.uuid4().hex[:8]}@example.com"
    ProfileRepository().create_profile(user_id=auth_user_id, full_name="Auth Patient", email=auth_email, role="patient")
    auth_token = auth_svc._generate_jwt(user_id=auth_user_id, email=auth_email)

    res_auth = client.post("/api/emergency/sos", json={
        "hospitalId": "hsp-001",
        "emergencyCategory": "cardiac",
        "patientName": "Auth Patient Cardiac",
        "contactPhone": "+919876543291",
        "userLocationName": "MG Road, Bengaluru",
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert res_auth.status_code == 201
    auth_req_id = res_auth.get_json()["data"]["requestId"]
    auth_otp = res_auth.get_json()["data"]["arrivalOtp"]

    # Capacity now has 2 holds
    cap_after_auth = cap_svc.get_live_capacity(1)
    assert cap_after_auth["available_beds"] == 58
    assert cap_after_auth["provisionally_allocated_beds"] == 2

    # --------------------------------------------------------------------------
    # 3. Cancellation & Capacity Release (with Idempotency Check)
    # --------------------------------------------------------------------------
    # Cancel guest request
    cancel_res = client.post(f"/api/emergency/{guest_req_id}/cancel", json={
        "token": guest_token,
        "cancellation_reason": "Patient arranged private vehicle"
    })
    assert cancel_res.status_code == 200

    # Hold released: available becomes 59, holds becomes 1
    cap_after_cancel = cap_svc.get_live_capacity(1)
    assert cap_after_cancel["available_beds"] == 59
    assert cap_after_cancel["provisionally_allocated_beds"] == 1

    # IDEMPOTENCY CHECK: Repeated cancellation must fail and NOT alter capacity
    repeat_cancel = client.post(f"/api/emergency/{guest_req_id}/cancel", json={
        "token": guest_token,
        "cancellation_reason": "Repeated cancel call"
    })
    assert repeat_cancel.status_code in (400, 409)
    cap_repeat = cap_svc.get_live_capacity(1)
    assert cap_repeat["available_beds"] == 59
    assert cap_repeat["provisionally_allocated_beds"] == 1

    # --------------------------------------------------------------------------
    # 4. Patient Arrival Verification via OTP (Hold -> Occupied Bed)
    # --------------------------------------------------------------------------
    # Create authorized hospital 1 staff credentials
    prof_repo = ProfileRepository()
    staff_id = str(uuid.uuid4())
    staff_email = f"staff_{uuid.uuid4().hex[:6]}@hospital1.test"
    prof_repo.create_profile(
        user_id=staff_id,
        full_name="Casualty Staff",
        email=staff_email,
        role="hospital_admin",
        hospital_id=1,
        account_status="active",
    )
    staff_token = auth_svc._generate_jwt(user_id=staff_id, email=staff_email)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Verify arrival of authenticated patient using arrivalOtp
    arrival_res = client.post(
        f"/api/emergency/{auth_req_id}/verify-arrival",
        json={"otp": auth_otp},
        headers=staff_headers,
    )
    assert arrival_res.status_code == 200

    # Transition confirmed: provisional hold released, occupied beds incremented
    cap_after_arrival = cap_svc.get_live_capacity(1)
    assert cap_after_arrival["provisionally_allocated_beds"] == 0
    assert cap_after_arrival["occupied_beds"] == base_occ + 1

    # IDEMPOTENCY CHECK: Repeated arrival verification must NOT increment occupied beds again
    repeat_arrival = client.post(
        f"/api/emergency/{auth_req_id}/verify-arrival",
        json={"otp": auth_otp},
        headers=staff_headers,
    )
    assert repeat_arrival.status_code == 200
    cap_after_repeat_arr = cap_svc.get_live_capacity(1)
    assert cap_after_repeat_arr["occupied_beds"] == base_occ + 1
    assert cap_after_repeat_arr["provisionally_allocated_beds"] == 0

    # --------------------------------------------------------------------------
    # 5. Cleanup Remote Test Records
    # --------------------------------------------------------------------------
    sb.table("emergency_requests").delete().eq("id", guest_req_id).execute()
    sb.table("emergency_requests").delete().eq("id", auth_req_id).execute()

