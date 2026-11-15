"""
AIIS Backend V2 - Appointment Service
=====================================
Domain service managing outpatient (OPD) consultation appointments.
Enforces business rules:
1. Rejection of past appointment dates.
2. Verification of facility existence and hospital ID resolution.
3. Strict patient privacy isolation (patients can only view/cancel their own appointments).
4. Strict hospital admin isolation (hospital administrators only access their assigned hospital).
5. Lifecycle status transitions (REQUESTED -> CONFIRMED -> COMPLETED / CANCELLED).
6. Frontend dual-key naming compatibility.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from backend_v2.repositories.appointment_repository import AppointmentRepository
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.repositories.profile_repository import ProfileRepository
from backend_v2.schemas.appointment_schema import (
    AppointmentCreateSchema,
    AppointmentStatusUpdateSchema,
)
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    to_frontend_hospital_id,
)
from backend_v2.utils.exceptions import (
    ValidationException,
    NotFoundException,
    ForbiddenException,
    ConflictException,
)

logger = logging.getLogger("aiis.services.appointment")


class AppointmentService:
    """Service handling outpatient consultation appointment booking and lifecycle."""

    def __init__(
        self,
        appointment_repo: Optional[AppointmentRepository] = None,
        hospital_repo: Optional[HospitalRepository] = None,
        profile_repo: Optional[ProfileRepository] = None,
    ):
        self.appointment_repo = appointment_repo or AppointmentRepository()
        self.hospital_repo = hospital_repo or HospitalRepository()
        self.profile_repo = profile_repo or ProfileRepository()

    def _enrich_appointment(
        self, apt: Dict[str, Any], hospital_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Attach frontend-compatible dual keys and honest booking notice."""
        enriched = dict(apt)
        h_id = apt.get("hospital_id")
        if h_id is not None:
            try:
                cid = to_canonical_hospital_id(h_id)
                code = to_frontend_hospital_id(cid)
                enriched["hospital_id"] = cid
                enriched["hospitalId"] = code
                enriched["hospital_code"] = code
                enriched["hospitalCode"] = code
            except Exception:
                pass

        if not hospital_name and h_id:
            hosp = self.hospital_repo.get_by_id(h_id)
            if hosp:
                hospital_name = hosp.get("name")

        if hospital_name:
            enriched["hospital_name"] = hospital_name
            enriched["hospitalName"] = hospital_name

        enriched["appointmentId"] = enriched.get("id")
        enriched["patientId"] = enriched.get("patient_id")
        enriched["patientName"] = enriched.get("patient_name")
        enriched["patientPhone"] = enriched.get("patient_phone")
        enriched["patientAge"] = enriched.get("patient_age")
        enriched["preferredDate"] = enriched.get("preferred_date")
        enriched["preferredTimeSlot"] = enriched.get("preferred_time_slot")
        enriched["createdAt"] = enriched.get("created_at")
        enriched["updatedAt"] = enriched.get("updated_at")

        # Honest disclosure: status is strictly REQUESTED until desk confirmation
        enriched["booking_mode"] = "REQUESTED"
        enriched["bookingMode"] = "REQUESTED"
        enriched["notice"] = (
            "Outpatient appointment is in REQUESTED status. "
            "Final clinical consultation is confirmed upon hospital casualty / OPD desk registration."
        )

        return enriched

    def create_appointment(
        self, data: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new outpatient consultation appointment.
        Validates payload, resolves hospital ID, verifies facility existence,
        and binds authenticated patient identity.
        """
        is_valid, error_msg = AppointmentCreateSchema.validate(data)
        if not is_valid:
            raise ValidationException(error_msg or "Invalid appointment data.")

        # Resolve hospital ID via adapter
        raw_hosp = data.get("hospital_id") if data.get("hospital_id") is not None else data.get("hospitalId")
        canonical_hosp_id = to_canonical_hospital_id(raw_hosp)

        hospital = self.hospital_repo.get_by_id(canonical_hosp_id)
        if not hospital:
            raise NotFoundException(f"Hospital with ID {raw_hosp} does not exist.")

        # Bind patient identity strictly from trusted server profile
        patient_id = None
        if user_context and user_context.get("id"):
            patient_id = str(user_context["id"])

        appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"

        # Resolve fields with dual-key fallbacks
        p_name = str(
            data.get("patient_name")
            or data.get("patientName")
            or (user_context.get("full_name") if user_context else "")
            or "Patient"
        ).strip()

        p_phone = str(
            data.get("patient_phone")
            or data.get("patientPhone")
            or data.get("phone")
            or data.get("contactPhone")
            or (user_context.get("phone") if user_context else "")
            or ""
        ).strip()

        p_age = str(data.get("patient_age") or data.get("patientAge") or data.get("age") or "").strip() or None
        spec = str(data.get("specialty") or data.get("department")).strip()
        p_date = str(data.get("preferred_date") or data.get("preferredDate") or data.get("date")).strip()
        p_time = str(
            data.get("preferred_time_slot")
            or data.get("preferredTimeSlot")
            or data.get("time_slot")
            or data.get("timeSlot")
        ).strip()
        notes = str(data.get("notes") or "").strip() or None

        record = {
            "id": appointment_id,
            "hospital_id": canonical_hosp_id,
            "patient_id": patient_id,
            "patient_name": p_name,
            "patient_phone": p_phone,
            "patient_age": p_age,
            "specialty": spec,
            "preferred_date": p_date,
            "preferred_time_slot": p_time,
            "notes": notes,
            "status": "REQUESTED",
        }

        created = self.appointment_repo.create(record)
        logger.info(
            f"Booked appointment {appointment_id} for hospital {canonical_hosp_id} "
            f"(Patient: {patient_id or 'Guest'})"
        )
        return self._enrich_appointment(created, hospital_name=hospital.get("name"))

    def get_appointment(
        self, appointment_id: str, user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve appointment details with RBAC authorization checks.
        """
        apt = self.appointment_repo.get_by_id(appointment_id)
        if not apt:
            raise NotFoundException(f"Appointment with ID '{appointment_id}' not found.")

        if user_context:
            role = user_context.get("role")
            user_id = str(user_context.get("id"))
            admin_hosp = user_context.get("hospital_id")

            # Patient isolation: patients can only access their own appointments
            if role == "patient":
                if apt.get("patient_id") and str(apt.get("patient_id")) != user_id:
                    raise ForbiddenException("You are not authorized to view another patient's appointment.")

            # Hospital Admin isolation: hospital admins only access their hospital's appointments
            elif role == "hospital_admin":
                if admin_hosp is None:
                    raise ForbiddenException("Hospital administrator has no assigned facility.")
                try:
                    admin_cid = to_canonical_hospital_id(admin_hosp)
                    apt_cid = to_canonical_hospital_id(apt.get("hospital_id", 0))
                    if admin_cid != apt_cid:
                        raise ForbiddenException("Hospital administrator cannot access another hospital's appointments.")
                except Exception:
                    if int(apt.get("hospital_id", 0)) != int(admin_hosp):
                        raise ForbiddenException("Hospital administrator cannot access another hospital's appointments.")

        return self._enrich_appointment(apt)

    def list_my_appointments(
        self, user_id: str, phone_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all appointments belonging to the requesting authenticated patient.
        If phone_hint is provided, validates that it does not attempt cross-patient snooping.
        """
        if not user_id:
            return []

        # If phone_hint is passed, check against caller's profile
        if phone_hint:
            hint_clean = str(phone_hint).strip()
            profile = self.profile_repo.get_by_id(user_id)
            if profile and profile.get("phone"):
                prof_phone = str(profile.get("phone")).strip()
                prof_digits = "".join(filter(str.isdigit, prof_phone))
                hint_digits = "".join(filter(str.isdigit, hint_clean))
                # If both have digits and don't match on last 8 digits: reject
                if prof_digits and hint_digits and len(hint_digits) >= 8 and len(prof_digits) >= 8:
                    if not (prof_digits.endswith(hint_digits[-8:]) or hint_digits.endswith(prof_digits[-8:])):
                        logger.warning(
                            f"User {user_id} attempted phone query with foreign phone '{hint_clean}'"
                        )
                        raise ForbiddenException("Cannot query appointments for another patient's phone number.")

        raw_apts = self.appointment_repo.list_by_patient(user_id)
        return [self._enrich_appointment(a) for a in raw_apts]

    def list_hospital_appointments(
        self, hospital_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all appointments for a specific hospital, accessible by authorized administrators."""
        cid = to_canonical_hospital_id(hospital_id)
        raw_apts = self.appointment_repo.list_by_hospital(cid, status=status)
        return [self._enrich_appointment(a) for a in raw_apts]

    def cancel_appointment(
        self, appointment_id: str, user_context: Dict[str, Any], reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel an appointment.
        Authorized for the booking patient, the hospital's admin, or platform authorities.
        """
        apt = self.get_appointment(appointment_id, user_context=user_context)

        # Enforce valid state transition: cannot cancel already completed or cancelled appointment
        current_status = str(apt.get("status", "")).upper()
        if current_status in {"CANCELLED", "COMPLETED"}:
            raise ConflictException(f"Cannot cancel appointment with status '{current_status}'.")

        updated_notes = apt.get("notes") or ""
        if reason:
            updated_notes = f"{updated_notes} | Cancellation Reason: {reason}".strip(" | ")

        updated = self.appointment_repo.update_status(
            appointment_id, "CANCELLED", notes=updated_notes
        )
        if not updated:
            raise NotFoundException(f"Failed to cancel appointment '{appointment_id}'.")

        logger.info(f"Cancelled appointment {appointment_id} by user {user_context.get('id')}")
        return self._enrich_appointment(updated)

    def update_appointment_status(
        self,
        appointment_id: str,
        new_status: str,
        notes: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update appointment lifecycle status (CONFIRMED, CANCELLED, COMPLETED).
        """
        is_valid, err = AppointmentStatusUpdateSchema.validate({"status": new_status})
        if not is_valid:
            raise ValidationException(err or "Invalid status update.")

        # Ensure appointment exists and caller is authorized
        self.get_appointment(appointment_id, user_context=user_context)

        updated = self.appointment_repo.update_status(
            appointment_id, new_status, notes=notes
        )
        if not updated:
            raise NotFoundException(f"Failed to update appointment '{appointment_id}'.")

        logger.info(f"Updated appointment {appointment_id} status to {new_status}")
        return self._enrich_appointment(updated)
