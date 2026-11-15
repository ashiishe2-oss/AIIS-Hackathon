"""
AIIS Backend V2 - Schemas Package
"""

from backend_v2.schemas.emergency_schema import (
    EmergencySearchSchema,
    EmergencySOSCreateSchema,
    EmergencyCancelSchema,
    EmergencyVerifyArrivalSchema,
    EMERGENCY_CATEGORIES,
)
from backend_v2.schemas.hospital_schema import HospitalFilterSchema
from backend_v2.schemas.appointment_schema import (
    AppointmentCreateSchema,
    AppointmentStatusUpdateSchema,
    VALID_APPOINTMENT_STATUSES,
)
from backend_v2.schemas.capacity_schema import CapacityUpdateSchema
from backend_v2.schemas.auth_schema import (
    UserRegisterSchema,
    UserLoginSchema,
    PUBLIC_ALLOWED_ROLES,
    RESTRICTED_ROLES,
)

__all__ = [
    "EmergencySearchSchema",
    "EmergencySOSCreateSchema",
    "EmergencyCancelSchema",
    "EmergencyVerifyArrivalSchema",
    "EMERGENCY_CATEGORIES",
    "HospitalFilterSchema",
    "AppointmentCreateSchema",
    "AppointmentStatusUpdateSchema",
    "VALID_APPOINTMENT_STATUSES",
    "CapacityUpdateSchema",
    "UserRegisterSchema",
    "UserLoginSchema",
    "PUBLIC_ALLOWED_ROLES",
    "RESTRICTED_ROLES",
]
