"""
AIIS Backend V2 - Authentication & Authorization Middleware
===========================================================
Security decorators enforcing:
- Bearer JWT token verification
- Role-Based Access Control (RBAC: patient, hospital_admin, authority, platform_admin)
- Hospital ownership isolation (hospital_admin can ONLY access their assigned hospital)
"""

import functools
import logging
from typing import Callable, Any, Optional
from flask import request, session, g

from backend_v2.services.auth_service import AuthService
from backend_v2.utils.exceptions import UnauthorizedException, ForbiddenException

logger = logging.getLogger("aiis.middleware.auth")

# Standard AIIS Role Constants
ROLE_PATIENT = "patient"
ROLE_HOSPITAL_ADMIN = "hospital_admin"
ROLE_AUTHORITY = "authority"
ROLE_PLATFORM_ADMIN = "platform_admin"

ALL_ROLES = {ROLE_PATIENT, ROLE_HOSPITAL_ADMIN, ROLE_AUTHORITY, ROLE_PLATFORM_ADMIN}

# Instantiate singleton auth service
_auth_service = AuthService()


def get_current_user() -> Optional[dict]:
    """Retrieve verified current user from Flask request context."""
    return getattr(g, "user", None)


def optional_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator that checks for an optional Bearer JWT token.
    Populates g.user if valid token provided; leaves g.user = None if unauthenticated.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization", "").strip()
        token: Optional[str] = None
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif "jwt" in session:
            token = session["jwt"]
        elif "access_token" in session:
            token = session["access_token"]

        g.user = None
        if token:
            try:
                user_profile = _auth_service.verify_token(token)
                g.user = user_profile
                g.token = token
            except Exception as exc:
                logger.debug(f"Optional auth skipped: {exc}")
        elif session.get("role"):
            g.user = {
                "id": session.get("user_id", "session-user"),
                "role": session.get("role"),
                "hospital_id": session.get("hospital_id"),
                "email": session.get("email"),
                "account_status": "active",
            }
            g.token = "session-cookie"

        return func(*args, **kwargs)

    return wrapper


def require_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator requiring a valid, cryptographically verified Bearer JWT access token or authenticated session.
    Populates Flask request context `g.user` with the verified application profile.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # 1. Extract Bearer token from Authorization header or session
        auth_header = request.headers.get("Authorization", "").strip()
        token: Optional[str] = None

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif "jwt" in session:
            token = session["jwt"]
        elif "access_token" in session:
            token = session["access_token"]

        if not token and session.get("role"):
            user_profile = {
                "id": session.get("user_id", f"staff-{session.get('hospital_id', 1)}"),
                "role": session.get("role"),
                "hospital_id": session.get("hospital_id"),
                "email": session.get("email", "staff@hospital.in"),
                "account_status": "active",
            }
            g.user = user_profile
            g.token = "session-cookie"
            return func(*args, **kwargs)

        if not token:
            logger.warning(f"Unauthorized request to {request.path}: Missing Bearer token")
            raise UnauthorizedException("Authentication token is required.")

        # 2. Cryptographically verify token and load active database profile
        user_profile = _auth_service.verify_token(token)

        # 3. Store verified user in request context
        g.user = user_profile
        g.token = token
        session["user_id"] = user_profile["id"]
        session["role"] = user_profile["role"]
        session["hospital_id"] = user_profile.get("hospital_id")
        session["email"] = user_profile.get("email")

        return func(*args, **kwargs)

    return wrapper


def require_role(*roles: str) -> Callable[..., Any]:
    """
    Decorator requiring the authenticated user to hold one of the specified roles.
    Executes require_auth first if user is not already verified.
    """
    allowed_roles = set(roles)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Ensure user is authenticated
            if not getattr(g, "user", None):
                wrapper_auth = require_auth(lambda: None)
                wrapper_auth()

            user = g.user
            user_role = user.get("role")

            if not user_role or user_role not in allowed_roles:
                logger.warning(
                    f"Access forbidden: User {user.get('id')} with role '{user_role}' "
                    f"attempted to access resource requiring {allowed_roles}"
                )
                raise ForbiddenException(
                    "You do not have permission to perform this action."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_hospital_access(hospital_id_param: str = "hospital_id") -> Callable[..., Any]:
    """
    Decorator enforcing hospital resource ownership.
    Rules:
    - Authority and Platform Admin can access any hospital.
    - Hospital Admin can ONLY operate on their assigned hospital_id.
    - Patients are denied access to hospital operational endpoints.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Ensure user is authenticated
            if not getattr(g, "user", None):
                wrapper_auth = require_auth(lambda: None)
                wrapper_auth()

            user = g.user
            role = user.get("role")

            # 2. Authority and Platform Admin have system-wide oversight
            if role in {ROLE_AUTHORITY, ROLE_PLATFORM_ADMIN}:
                return func(*args, **kwargs)

            # 3. Hospital Admin must match assigned hospital
            if role == ROLE_HOSPITAL_ADMIN:
                assigned_hospital = user.get("hospital_id")
                if not assigned_hospital:
                    logger.warning(f"Hospital Admin {user.get('id')} has no assigned hospital_id.")
                    raise ForbiddenException("User account has no assigned hospital facility.")

                # Resolve requested hospital ID from path params, query params, or body
                requested_id = kwargs.get(hospital_id_param)
                if requested_id is None:
                    requested_id = request.view_args.get(hospital_id_param) if request.view_args else None
                if requested_id is None:
                    requested_id = request.args.get(hospital_id_param)
                if requested_id is None and request.is_json:
                    body = request.get_json(silent=True) or {}
                    requested_id = body.get(hospital_id_param) or body.get("hospitalId")

                if requested_id is not None:
                    try:
                        from backend_v2.utils.hospital_id_adapter import to_canonical_hospital_id
                        req_canonical = to_canonical_hospital_id(requested_id)
                        assigned_canonical = to_canonical_hospital_id(assigned_hospital)
                        is_mismatch = (req_canonical != assigned_canonical)
                    except Exception:
                        is_mismatch = (str(assigned_hospital) != str(requested_id))

                    if is_mismatch:
                        logger.warning(
                            f"Cross-hospital access blocked: Admin assigned to hospital {assigned_hospital} "
                            f"attempted to access hospital {requested_id}"
                        )
                        raise ForbiddenException(
                            "You do not have permission to access or modify this hospital."
                        )

                return func(*args, **kwargs)

            # 4. Patients cannot access hospital operational endpoints
            raise ForbiddenException("Patients cannot access hospital administration operations.")

        return wrapper

    return decorator
