"""
End-to-End Frontend Integration Test Suite
==========================================
Validates the complete demo-critical workflows for the Hackathon Final Round:
1. Workflow A: Citizen Emergency SOS (No login, search, SOS dispatch, tracking token, arrival OTP)
2. Workflow B: Hospital Staff Coordination (Login, incoming requests, arrival verification with OTP, bed updates)
3. Workflow C: Regional Health Authority Dashboard (Auth, 36 facilities, regional SRI, alerts)
4. Workflow D: Public Directory & Planned Healthcare (Verified directory, filters, distance calculations)
"""

import pytest
from backend_v2.app import create_app


@pytest.fixture
def test_app():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "hackathon-demo-test-secret-32-chars-long"
    return app


@pytest.fixture
def client(test_app):
    return test_app.test_client()


def test_workflow_a_citizen_emergency_sos(client):
    """
    Workflow A:
    1. Citizen opens homepage / emergency portal without login.
    2. Searches for emergency facilities in Mumbai.
    3. Creates Emergency SOS request.
    4. Receives request ID, guest tracking token, and 4-digit arrival OTP.
    5. Polls status via tracking token (confirming OTP is never leaked).
    """
    # 1. Open homepage
    home_res = client.get("/")
    assert home_res.status_code == 200
    assert b"AIIS" in home_res.data
    assert b"Emergency" in home_res.data

    # 2. Get locations catalog
    loc_res = client.get("/api/locations")
    assert loc_res.status_code == 200
    loc_data = loc_res.get_json()["data"]
    assert len(loc_data) > 0
    mumbai_loc = next((l for l in loc_data if "mumbai" in l["city"].lower()), loc_data[0])

    # 3. Search facilities
    search_res = client.post("/api/emergency/search", json={
        "latitude": mumbai_loc["lat"],
        "longitude": mumbai_loc["lon"],
        "category": "cardiac",
        "radius_km": 25,
    })
    assert search_res.status_code == 200
    hospitals = search_res.get_json()["hospitals"]
    assert len(hospitals) > 0
    target_hospital = hospitals[0]
    hosp_id = target_hospital["id"]

    # 4. Dispatch Emergency SOS
    sos_res = client.post("/api/emergency/sos", json={
        "hospital_id": hosp_id,
        "category": "cardiac",
        "severity": "critical",
        "patient_name": "Rohan Verma",
        "contact_phone": "+919876543210",
        "user_lat": mumbai_loc["lat"],
        "user_lon": mumbai_loc["lon"],
    })
    assert sos_res.status_code == 201
    sos_data = sos_res.get_json()["data"]
    req_id = sos_data["id"]
    tracking_token = sos_data["tracking_token"]
    otp = sos_data["otp"]

    assert req_id is not None
    assert tracking_token is not None
    assert len(otp) == 4
    assert otp.isdigit()

    # 5. Live tracking polling (OTP must be redacted)
    track_res = client.get(
        f"/api/emergency/{req_id}/track",
        headers={"X-Tracking-Token": tracking_token}
    )
    assert track_res.status_code == 200
    track_data = track_res.get_json()["data"]
    assert track_data["id"] == req_id
    assert "otp" not in track_data
    assert track_data["status"] in ("REQUEST_SUBMITTED", "pending", "accepted")


def test_workflow_b_hospital_staff_coordination_and_intake(client):
    """
    Workflow B:
    1. Hospital admin logs in via /login.
    2. Session establishes authenticated hospital_admin role.
    3. Views /hospital_dashboard with KPI summary.
    4. Views incoming emergency requests on casualty intake desk.
    5. Verifies patient arrival with 4-digit OTP.
    6. Verifies bed capacity update.
    """
    # Create an SOS request first
    sos_res = client.post("/api/emergency/sos", json={
        "hospital_id": 1,
        "category": "cardiac",
        "severity": "critical",
        "patient_name": "Priya Nair",
        "contact_phone": "+919876543211",
        "user_lat": 18.9902,
        "user_lon": 72.8404,
    })
    assert sos_res.status_code == 201
    sos_payload = sos_res.get_json()["data"]
    req_id = sos_payload["id"]
    otp = sos_payload["otp"]

    # 1. Staff login
    login_res = client.post("/login", data={
        "role": "hospital_admin",
        "username": "admin@hospital.in",
        "password": "password123",
    }, follow_redirects=False)
    assert login_res.status_code == 302
    assert "/hospital_dashboard" in login_res.headers["Location"]

    # 2. View hospital dashboard
    dash_res = client.get("/hospital_dashboard")
    assert dash_res.status_code == 200
    assert b"Casualty Intake" in dash_res.data
    assert b"Total Beds" in dash_res.data

    # 3. Check casualty intake desk endpoint
    inbound_res = client.get("/api/emergency/hospital/1/requests")
    assert inbound_res.status_code == 200
    requests_list = inbound_res.get_json()["requests"]
    matching = [r for r in requests_list if r["id"] == req_id]
    assert len(matching) > 0

    # 4. Verify patient arrival at casualty desk with OTP
    verify_res = client.post(
        f"/api/emergency/{req_id}/verify-arrival",
        json={"otp": otp}
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.get_json()["data"]
    assert verify_data["status"] == "PATIENT_ARRIVED"

    # 5. Update bed capacity
    update_res = client.post("/api/update-beds", json={
        "hospital_id": 1,
        "num_beds": 1050,
    })
    assert update_res.status_code == 200
    assert update_res.get_json()["success"] is True

    # 6. Verify dashboard reflects updated capacity
    dash_res2 = client.get("/hospital_dashboard")
    assert dash_res2.status_code == 200
    assert b"1,050" in dash_res2.data or b"1050" in dash_res2.data

    # Restore baseline
    client.post("/api/update-beds", json={"hospital_id": 1, "num_beds": 1000})


def test_workflow_c_regional_authority_dashboard(client):
    """
    Workflow C:
    1. Regional Health Authority logs in.
    2. Opens /authority_dashboard.
    3. Verifies 36 facilities, regional SRI metric, alerts, and risk distribution.
    """
    # Login as authority
    login_res = client.post("/login", data={
        "role": "authority",
        "username": "authority@health.gov.in",
        "password": "password123",
    }, follow_redirects=False)
    assert login_res.status_code == 302
    assert "/authority_dashboard" in login_res.headers["Location"]

    # View authority dashboard
    auth_dash = client.get("/authority_dashboard")
    assert auth_dash.status_code == 200
    assert b"Arogya Infrastructure Intelligence System" in auth_dash.data or b"Ministry of Health" in auth_dash.data
    assert b"36" in auth_dash.data
    assert b"Avg SRI" in auth_dash.data
    assert b"Active Infrastructure Alerts" in auth_dash.data


def test_workflow_d_public_directory_and_planned_healthcare(client):
    """
    Workflow D:
    1. Public citizen opens /public.
    2. Verifies hospital directory with search filters and distance calculation.
    """
    pub_res = client.get("/public")
    assert pub_res.status_code == 200
    assert b"Citizen Health Portal" in pub_res.data or b"Find the Right Hospital" in pub_res.data

    # Filter with latitude and longitude for distance calculation
    dist_res = client.get("/public?lat=18.9902&lon=72.8404")
    assert dist_res.status_code == 200
    assert b"km" in dist_res.data
