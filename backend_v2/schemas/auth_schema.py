"""
AIIS Backend V2 - Authentication Schemas
========================================
Validation contracts for user registration, login, and profile payload structures.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from backend_v2.utils.validators import validate_phone_number

# Public roles permitted during citizen/staff registration
PUBLIC_ALLOWED_ROLES = {"patient", "hospital_admin"}
RESTRICTED_ROLES = {"authority", "platform_admin"}


@dataclass
class UserRegisterSchema:
    """Validation schema for user registration."""
    full_name: str
    email: str
    password: str
    phone: Optional[str] = None
    role: str = "patient"
    hospital_id: Optional[int] = None

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Registration payload must be a JSON object."

        # 1. Full name validation
        full_name = str(data.get("full_name") or data.get("name") or "").strip()
        if not full_name or len(full_name) < 2:
            return False, "Field 'full_name' must be at least 2 characters long."
        if len(full_name) > 128:
            return False, "Field 'full_name' cannot exceed 128 characters."

        # 2. Email validation
        email = str(data.get("email") or data.get("username") or "").strip()
        if not email:
            return False, "Field 'email' is required."
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, email):
            return False, "Please provide a valid email address."

        # 3. Password strength validation
        password = str(data.get("password") or "")
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
            return False, "Password must contain both letters and at least one number."

        # 4. Role validation & self-escalation prevention
        requested_role = str(data.get("role") or "patient").strip().lower()
        if requested_role in RESTRICTED_ROLES:
            return False, f"Self-registration as '{requested_role}' is prohibited for security reasons."
        if requested_role not in PUBLIC_ALLOWED_ROLES:
            return False, f"Invalid role '{requested_role}'. Must be one of {sorted(PUBLIC_ALLOWED_ROLES)}."

        # 5. Phone validation (if provided)
        phone = data.get("phone")
        if phone:
            is_valid_phone, phone_err = validate_phone_number(str(phone))
            if not is_valid_phone:
                return False, phone_err

        return True, None


@dataclass
class UserLoginSchema:
    """Validation schema for user login."""
    email: str
    password: str

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Login payload must be a JSON object."

        email = str(data.get("email") or data.get("username") or "").strip()
        if not email:
            return False, "Field 'email' is required."

        password = str(data.get("password") or "")
        if not password:
            return False, "Field 'password' is required."

        return True, None

