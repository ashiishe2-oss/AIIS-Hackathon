"""
AIIS Backend V2 - Appointment Schemas
=====================================
Validation and data structures for outpatient (OPD) consultation appointments.
Enforces business rules including mandatory fields, valid phone numbers,
and rejection of past appointment dates.
Supports both frontend camelCase and backend snake_case naming conventions.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple
import re

from backend_v2.utils.hospital_id_adapter import to_canonical_hospital_id
from backend_v2.utils.exceptions import ValidationException

VALID_APPOINTMENT_STATUSES = {"REQUESTED", "CONFIRMED", "CANCELLED", "COMPLETED"}
UPDATABLE_APPOINTMENT_STATUSES = {"CONFIRMED", "CANCELLED", "COMPLETED"}


class AppointmentCreateSchema:
    """Validator for creating a new outpatient appointment."""

    @staticmethod
    def validate(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate appointment creation payload.
        Returns (is_valid, error_msg).
        """
        if not isinstance(data, dict):
            return False, "Request body must be a valid JSON object."

        # 1. Hospital identifier validation (accepts 'hsp-001', '1', 1)
        raw_hospital = data.get("hospital_id") if data.get("hospital_id") is not None else data.get("hospitalId")
        if raw_hospital is None or str(raw_hospital).strip() == "":
            return False, "hospital_id is required."

        try:
            canonical_hosp_id = to_canonical_hospital_id(raw_hospital)
            if canonical_hosp_id <= 0:
                return False, "hospital_id must be a positive integer."
        except ValidationException as e:
            return False, e.message

        # 2. Patient name validation
        patient_name = data.get("patient_name") or data.get("patientName")
        if not patient_name or not str(patient_name).strip():
            return False, "patient_name is required."
        clean_name = str(patient_name).strip()
        if len(clean_name) > 128:
            return False, "patient_name exceeds maximum length of 128 characters."

        # 3. Patient phone validation
        patient_phone = (
            data.get("patient_phone")
            or data.get("patientPhone")
            or data.get("phone")
            or data.get("contactPhone")
        )
        if not patient_phone or not str(patient_phone).strip():
            return False, "patient_phone is required."
        clean_phone = re.sub(r"[\s\-\(\)]", "", str(patient_phone))
        digits = "".join(filter(str.isdigit, clean_phone))
        if len(digits) < 8 or len(digits) > 16:
            return False, "patient_phone must contain between 8 and 16 digits."

        # 4. Specialty / Department validation
        specialty = data.get("specialty") or data.get("department")
        if not specialty or not str(specialty).strip():
            return False, "specialty is required."
        clean_specialty = str(specialty).strip()
        if len(clean_specialty) > 128:
            return False, "specialty exceeds maximum length of 128 characters."

        # 5. Preferred date validation (must be valid YYYY-MM-DD and NOT in the past)
        pref_date_raw = data.get("preferred_date") or data.get("preferredDate") or data.get("date")
        if not pref_date_raw:
            return False, "preferred_date is required (format YYYY-MM-DD)."
        try:
            parsed_date = datetime.strptime(str(pref_date_raw).strip(), "%Y-%m-%d").date()
        except ValueError:
            return False, "preferred_date must follow ISO format YYYY-MM-DD."

        today = date.today()
        if parsed_date < today:
            return False, f"preferred_date cannot be in the past ({parsed_date} < {today})."

        # 6. Preferred time slot validation
        pref_time = (
            data.get("preferred_time_slot")
            or data.get("preferredTimeSlot")
            or data.get("time_slot")
            or data.get("timeSlot")
        )
        if not pref_time or not str(pref_time).strip():
            return False, "preferred_time_slot is required."
        clean_time = str(pref_time).strip()
        if len(clean_time) > 64:
            return False, "preferred_time_slot exceeds maximum length of 64 characters."

        # 7. Optional patient age validation
        patient_age = data.get("patient_age") or data.get("patientAge") or data.get("age")
        if patient_age is not None and str(patient_age).strip():
            clean_age = str(patient_age).strip()
            if len(clean_age) > 16:
                return False, "patient_age exceeds maximum length of 16 characters."

        return True, None


class AppointmentStatusUpdateSchema:
    """Validator for updating appointment lifecycle status."""

    @staticmethod
    def validate(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(data, dict):
            return False, "Request body must be a valid JSON object."

        status = data.get("status")
        if not status or not str(status).strip():
            return False, "status is required."

        clean_status = str(status).strip().upper()
        if clean_status not in UPDATABLE_APPOINTMENT_STATUSES:
            return False, f"Invalid status '{clean_status}'. Allowed: {sorted(list(UPDATABLE_APPOINTMENT_STATUSES))}."

        return True, None
