"""
AIIS Backend V2 - Utilities Package
"""

from backend_v2.utils.responses import api_response, success_response, error_response
from backend_v2.utils.exceptions import (
    AppException,
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ConflictException,
    ServiceUnavailableException,
)
from backend_v2.utils.validators import validate_coordinates, validate_phone_number
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    to_frontend_hospital_id,
    enrich_hospital_identifiers,
)

__all__ = [
    "api_response",
    "success_response",
    "error_response",
    "AppException",
    "ValidationException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ConflictException",
    "ServiceUnavailableException",
    "validate_coordinates",
    "validate_phone_number",
    "to_canonical_hospital_id",
    "to_frontend_hospital_id",
    "enrich_hospital_identifiers",
]

