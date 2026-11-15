"""
AIIS Backend V2 - Emergency Schemas
===================================
Data validation contracts and serialization schemas for Emergency SOS,
nearby hospital search, and arrival verification.
"""

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from backend_v2.utils.validators import validate_coordinates, validate_phone_number
from backend_v2.utils.hospital_id_adapter import to_canonical_hospital_id
from backend_v2.utils.exceptions import ValidationException

# Supported clinical emergency categories
EMERGENCY_CATEGORIES = {
    "general": "General Medical Emergency",
    "cardiac": "Chest Pain / Cardiac Condition",
    "stroke": "Stroke / Neurological Signs",
    "trauma": "Accident / Trauma / Hemorrhage",
    "breathing": "Breathing Trouble / Respiratory Distress",
    "child": "Paediatric / Maternal Emergency",
    "burns": "Severe Burns / Scalds",
    "other": "Other Emergency Condition",
}


@dataclass
class EmergencySearchSchema:
    """Validation for emergency hospital search requests."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    category: str = "general"
    location_name: Optional[str] = None
    limit: int = 8

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Search payload must be a JSON object."

        lat = data.get("latitude") if data.get("latitude") is not None else data.get("lat")
        lon = data.get("longitude") if data.get("longitude") is not None else (
            data.get("lon") if data.get("lon") is not None else data.get("lng")
        )
        city = data.get("city") or data.get("locationName") or data.get("location_name")

        has_coords = lat is not None and lon is not None
        has_city = bool(city and str(city).strip())

        if not has_coords and not has_city:
            return False, "Provide GPS coordinates (latitude and longitude) or select a city."

        if has_coords:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                return False, "Coordinates must be numeric values."

            is_valid_coords, err = validate_coordinates(lat_f, lon_f)
            if not is_valid_coords:
                return False, err

        return True, None


@dataclass
class EmergencySOSCreateSchema:
    """Validation for citizen emergency SOS submission."""
    hospital_id: Any
    emergency_category: str = "general"
    patient_name: Optional[str] = None
    companion_name: Optional[str] = None
    contact_phone: Optional[str] = None
    estimated_travel_minutes: int = 15
    user_location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "SOS payload must be a JSON object."

        # Hospital ID check
        hosp_id = data.get("hospitalId") if data.get("hospitalId") is not None else data.get("hospital_id")
        if hosp_id is None or str(hosp_id).strip() == "":
            return False, "Hospital ID ('hospitalId') is required to target an emergency dispatch."

        try:
            to_canonical_hospital_id(hosp_id)
        except ValidationException as e:
            return False, e.message

        # Phone validation (if provided)
        phone = data.get("contactPhone") or data.get("contact_phone")
        if phone:
            phone_str = str(phone).strip()
            digits = "".join(filter(str.isdigit, phone_str))
            if len(digits) < 10:
                return False, "Contact phone number must contain at least 10 digits."

        return True, None


@dataclass
class EmergencyCancelSchema:
    """Validation for emergency SOS cancellation."""
    reason: str = "Cancelled by patient"

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Cancellation payload must be a JSON object."
        return True, None


@dataclass
class EmergencyVerifyArrivalSchema:
    """Validation for hospital casualty desk arrival verification."""
    otp: str

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Verification payload must be a JSON object."
        otp = str(data.get("otp", "")).strip()
        if not otp:
            return False, "Arrival OTP is required."
        if not otp.isdigit() or len(otp) != 4:
            return False, "Arrival OTP must be a 4-digit numeric code."
        return True, None
