"""
AIIS Backend V2 - Repositories Package
"""

from backend_v2.repositories.emergency_repository import EmergencyRepository
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.repositories.appointment_repository import AppointmentRepository

__all__ = [
    "EmergencyRepository",
    "HospitalRepository",
    "ProfileRepository",
    "AppointmentRepository",
]
