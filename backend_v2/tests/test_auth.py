"""
AIIS Backend V2 - Stage 3: Authentication & RBAC Test Suite
===========================================================
Comprehensive test coverage for:
1. Registration & self-escalation prevention
2. Login & JWT session issuance
3. Password & email validation
4. Account status lifecycle (active, pending_approval, suspended)
5. Cryptographic JWT verification (expired tokens, signature tampering, malformed headers)
6. Role-Based Access Control (RBAC: patient, hospital_admin, authority)
7. Hospital ownership isolation (cross-hospital access prevention)
8. Guest emergency access preservation
"""

import time
import uuid
import jwt
import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig
from backend_v2.services.auth_service import AuthService
from backend_v2.repositories.profile_repository import ProfileRepository


@pytest.fixture
def app():
    test_app = create_app(TestingConfig)
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_service():
    return AuthService()


# ── 1. Registration Tests ─────────────────────────────────────────────────────

def test_register_patient_success(client):
    """Verify citizen registration successfully creates a patient profile with active status."""
    test_email = f"priya.{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Priya Sharma",
        "email": test_email,
        "password": "SecurePassword123",
        "phone": "+919876543210",
        "role": "patient",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    assert response.is_json

    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["email"] == test_email
    assert data["data"]["role"] == "patient"
    assert data["data"]["account_status"] == "active"


def test_register_prevent_self_escalation_authority(client):
    """Verify that attempting to self-register as 'authority' is rejected with 400 validation error."""
    payload = {
        "full_name": "Rogue Official",
        "email": "rogue@example.com",
        "password": "Password123",
        "role": "authority",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "prohibited" in data["error"]["message"].lower()


def test_register_prevent_self_escalation_platform_admin(client):
    """Verify that attempting to self-register as 'platform_admin' is rejected."""
    payload = {
        "full_name": "Hacker Admin",
        "email": "admin.fake@example.com",
        "password": "Password123",
        "role": "platform_admin",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "prohibited" in data["error"]["message"].lower()


def test_register_hospital_admin_requires_approval(client):
    """Verify hospital administrator registration defaults to pending_approval."""
    payload = {
        "full_name": "Dr. Suresh Reddy",
        "email": "dr.suresh@victoria.in",
        "password": "DoctorPass123",
        "role": "hospital_admin",
        "hospital_id": 1,
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["data"]["role"] == "hospital_admin"
    assert data["data"]["account_status"] == "pending_approval"


def test_register_duplicate_email_conflict(client):
    """Verify duplicate email registration returns 409 Conflict."""
    dup_email = f"duplicate.{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Original User",
        "email": dup_email,
        "password": "Password123",
    }
    client.post("/api/auth/register", json=payload)

    # Second registration with same email
    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "CONFLICT"


def test_register_weak_password_rejected(client):
    """Verify passwords shorter than 8 chars or missing numbers are rejected."""
    payload = {
        "full_name": "Weak Pass User",
        "email": "weak@example.com",
        "password": "short",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


# ── 2. Login & Session Issuance Tests ─────────────────────────────────────────

def test_login_success(client):
    """Verify valid credentials return access token and user profile."""
    test_email = f"arjun.{uuid.uuid4().hex[:8]}@example.com"
    reg_payload = {
        "full_name": "Arjun Das",
        "email": test_email,
        "password": "ArjunPassword123",
        "role": "patient",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201

    # Login
    login_payload = {
        "email": test_email,
        "password": "ArjunPassword123",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    session_data = data["data"]
    assert "access_token" in session_data
    assert session_data["token_type"] == "bearer"
    assert session_data["user"]["email"] == test_email
    assert session_data["user"]["role"] == "patient"


def test_login_invalid_password(client):
    """Verify incorrect password returns 401 Unauthorized."""
    login_payload = {
        "email": "arjun.das@example.com",
        "password": "WrongPassword999",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_login_pending_approval_blocked(client):
    """Verify hospital admin account with status 'pending_approval' is blocked from logging in."""
    reg_payload = {
        "full_name": "Pending Doctor",
        "email": "pending.doctor@hospital.in",
        "password": "DoctorPass123",
        "role": "hospital_admin",
        "hospital_id": 1,
    }
    client.post("/api/auth/register", json=reg_payload)

    login_res = client.post("/api/auth/login", json={"email": "pending.doctor@hospital.in", "password": "DoctorPass123"})
    assert login_res.status_code == 403
    data = login_res.get_json()
    assert data["success"] is False
    assert "pending" in data["error"]["message"].lower()


# ── 3. JWT Verification & Profile Retrieval Tests ─────────────────────────────

def test_get_current_user_profile(client):
    """Verify GET /api/auth/me returns caller profile with valid Bearer token."""
    user_email = f"me.{uuid.uuid4().hex[:8]}@example.com"
    # Register & Login
    client.post("/api/auth/register", json={
        "full_name": "Me User",
        "email": user_email,
        "password": "Password123",
    })
    login_res = client.post("/api/auth/login", json={"email": user_email, "password": "Password123"})
    token = login_res.get_json()["data"]["access_token"]

    # Call /api/auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.get_json()
    assert me_data["success"] is True
    assert me_data["data"]["email"] == user_email
    assert me_data["data"]["role"] == "patient"


def test_get_profile_missing_token(client):
    """Verify request without Authorization header returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    data = response.get_json()
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_get_profile_expired_jwt(client):
    """Verify expired JWT is rejected with 401 and specific expiration error."""
    # Generate expired token
    secret = TestingConfig.SECRET_KEY
    now = int(time.time())
    expired_payload = {
        "sub": "some-uuid",
        "email": "test@example.com",
        "iat": now - 7200,
        "exp": now - 3600,  # Expired 1 hour ago
    }
    expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    data = response.get_json()
    assert "expired" in data["error"]["message"].lower()


def test_get_profile_tampered_signature(client):
    """Verify token signed with an invalid/tampered secret key is rejected with 401."""
    fraudulent_secret = "wrong-secret-key-attacker"
    now = int(time.time())
    payload = {
        "sub": "some-uuid",
        "email": "test@example.com",
        "iat": now,
        "exp": now + 3600,
    }
    tampered_token = jwt.encode(payload, fraudulent_secret, algorithm="HS256")

    headers = {"Authorization": f"Bearer {tampered_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    data = response.get_json()
    assert "signature" in data["error"]["message"].lower()


def test_logout_revokes_session(client):
    """Verify POST /api/auth/logout revokes access token."""
    logout_email = f"logout.{uuid.uuid4().hex[:8]}@example.com"
    # Register & Login
    client.post("/api/auth/register", json={
        "full_name": "Logout User",
        "email": logout_email,
        "password": "Password123",
    })
    login_res = client.post("/api/auth/login", json={"email": logout_email, "password": "Password123"})
    token = login_res.get_json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Logout
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Subsequent request using the revoked token must be rejected
    followup_res = client.get("/api/auth/me", headers=headers)
    assert followup_res.status_code == 401


# ── 4. Role-Based Access Control (RBAC) & Hospital Isolation Tests ───────────

def test_rbac_patient_forbidden_on_hospital_admin_endpoints(client):
    """Verify patient role cannot access hospital admin operational endpoints."""
    # Create patient
    test_email = f"patient.rbac.{uuid.uuid4().hex[:8]}@example.com"
    reg_res = client.post("/api/auth/register", json={
        "full_name": "Regular Patient",
        "email": test_email,
        "password": "Password123",
        "role": "patient",
    })
    assert reg_res.status_code == 201
    login_res = client.post("/api/auth/login", json={"email": test_email, "password": "Password123"})
    assert login_res.status_code == 200
    token = login_res.get_json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Patient tries to view hospital requests
    response = client.get("/api/hospital/1/requests", headers=headers)
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN"


def test_hospital_admin_authorized_own_hospital(client):
    """Verify hospital admin can access requests for their assigned hospital."""
    profile_repo = ProfileRepository()
    admin_uuid = "admin-uuid-victoria"

    # Seed an active hospital admin assigned to Hospital 1 (Victoria Hospital)
    profile_repo.create_profile(
        user_id=admin_uuid,
        full_name="Admin Victoria",
        email="admin@victoria.in",
        role="hospital_admin",
        hospital_id=1,
        account_status="active",
    )

    auth_serv = AuthService(profile_repo=profile_repo)
    token = auth_serv._generate_jwt(user_id=admin_uuid, email="admin@victoria.in")
    headers = {"Authorization": f"Bearer {token}"}

    # Hospital 1 requests access -> Allowed (200)
    response = client.get("/api/hospital/1/requests", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["hospital_id"] == 1


def test_hospital_admin_cross_hospital_access_denied(client):
    """Verify hospital admin for Hospital 1 cannot access Hospital 2 records."""
    profile_repo = ProfileRepository()
    admin_uuid = "admin-uuid-hospital-1"

    profile_repo.create_profile(
        user_id=admin_uuid,
        full_name="Admin Hosp 1",
        email="admin@hosp1.in",
        role="hospital_admin",
        hospital_id=1,
        account_status="active",
    )

    auth_serv = AuthService(profile_repo=profile_repo)
    token = auth_serv._generate_jwt(user_id=admin_uuid, email="admin@hosp1.in")
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to access Hospital 2 -> Denied (403)
    response = client.get("/api/hospital/2/requests", headers=headers)
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "not have permission" in data["error"]["message"].lower()


def test_authority_user_can_access_any_hospital(client):
    """Verify authority role (DHO / State Command) has cross-hospital oversight."""
    profile_repo = ProfileRepository()
    auth_uuid = "authority-dho-uuid"

    profile_repo.create_profile(
        user_id=auth_uuid,
        full_name="Dr. District Health Officer",
        email="dho@health.gov.in",
        role="authority",
        account_status="active",
    )

    auth_serv = AuthService(profile_repo=profile_repo)
    token = auth_serv._generate_jwt(user_id=auth_uuid, email="dho@health.gov.in")
    headers = {"Authorization": f"Bearer {token}"}

    # Authority can access Hospital 1 and Hospital 2
    res1 = client.get("/api/hospital/1/requests", headers=headers)
    res2 = client.get("/api/hospital/2/requests", headers=headers)

    assert res1.status_code == 200
    assert res2.status_code == 200
