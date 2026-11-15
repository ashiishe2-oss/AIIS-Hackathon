"""
AIIS Backend V2 - Middleware Package
"""

from backend_v2.middleware.auth import (
    require_auth,
    require_role,
    require_hospital_access,
    get_current_user,
    ROLE_PATIENT,
    ROLE_HOSPITAL_ADMIN,
    ROLE_AUTHORITY,
    ROLE_PLATFORM_ADMIN,
    ALL_ROLES,
)
from backend_v2.middleware.validation import validate_json_body

__all__ = [
    "require_auth",
    "require_role",
    "require_hospital_access",
    "get_current_user",
    "ROLE_PATIENT",
    "ROLE_HOSPITAL_ADMIN",
    "ROLE_AUTHORITY",
    "ROLE_PLATFORM_ADMIN",
    "ALL_ROLES",
    "validate_json_body",
]
