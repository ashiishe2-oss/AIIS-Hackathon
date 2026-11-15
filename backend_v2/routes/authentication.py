"""
AIIS Backend V2 - Authentication Routes
=======================================
REST API endpoints supporting:
- User registration (patient self-registration with privilege escalation prevention)
- Supabase user authentication and JWT session issuance
- Session termination / logout
- Authenticated current user profile retrieval (/api/auth/me)
"""

import logging
from flask import Blueprint, request, jsonify, g

from backend_v2.schemas.auth_schema import UserRegisterSchema, UserLoginSchema
from backend_v2.services.auth_service import AuthService
from backend_v2.middleware.auth import require_auth, get_current_user
from backend_v2.utils.responses import success_response
from backend_v2.utils.exceptions import ValidationException

logger = logging.getLogger("aiis.routes.auth")

auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    POST /api/auth/register
    Registers a new citizen/patient or hospital staff account.
    Self-registration is restricted to 'patient' or 'hospital_admin' (pending approval).
    """
    # Parse JSON or form data
    data = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    if not data:
        data = {}

    is_valid, err_msg = UserRegisterSchema.validate(data)
    if not is_valid:
        raise ValidationException(err_msg)

    full_name = str(data.get("full_name") or data.get("name")).strip()
    email = str(data.get("email") or data.get("username")).strip()
    password = str(data.get("password"))
    phone = data.get("phone")
    role = str(data.get("role") or "patient").strip().lower()
    hospital_id = data.get("hospital_id")
    if hospital_id is not None:
        try:
            hospital_id = int(hospital_id)
        except (ValueError, TypeError):
            hospital_id = None

    profile = auth_service.register(
        full_name=full_name,
        email=email,
        password=password,
        phone=str(phone) if phone else None,
        requested_role=role,
        hospital_id=hospital_id,
    )

    return success_response(
        data=profile,
        message="User account registered successfully.",
        status_code=201,
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /api/auth/login
    Authenticates user credentials and returns verified Supabase JWT session.
    """
    data = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    if not data:
        data = {}

    is_valid, err_msg = UserLoginSchema.validate(data)
    if not is_valid:
        raise ValidationException(err_msg)

    email = str(data.get("email") or data.get("username")).strip()
    password = str(data.get("password"))

    session_data = auth_service.login(email=email, password=password)

    return success_response(
        data=session_data,
        message="Authentication successful.",
        status_code=200,
    )


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    """
    POST /api/auth/logout
    Revokes the active user access token.
    """
    token = getattr(g, "token", None)
    auth_service.logout(token=token)

    return success_response(
        data={"revoked": True},
        message="Session successfully terminated.",
        status_code=200,
    )


@auth_bp.route("/me", methods=["GET"])
@require_auth
def get_current_user_profile():
    """
    GET /api/auth/me
    Retrieves the verified application profile of the authenticated caller.
    """
    user = get_current_user()
    return success_response(
        data=user,
        status_code=200,
    )
