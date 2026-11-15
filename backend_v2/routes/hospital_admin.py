"""
AIIS Backend V2 - Hospital Admin Blueprint
==========================================
Protected operational endpoints for hospital administrators:
- View incoming emergency requests (isolated to authorized hospital)
- Hospital capacity management (protected by hospital ownership verification)
- Outpatient appointment management (isolated to authorized hospital)
"""

import logging
from typing import Any, Optional, Dict, List
from flask import Blueprint, request, jsonify, g

from backend_v2.middleware.auth import require_hospital_access, require_role, ROLE_HOSPITAL_ADMIN, ROLE_AUTHORITY
from backend_v2.repositories.emergency_repository import EmergencyRepository
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.services.appointment_service import AppointmentService
from backend_v2.services.capacity_service import CapacityService
from backend_v2.utils.responses import success_response
from backend_v2.utils.exceptions import ValidationException, NotFoundException
from backend_v2.utils.hospital_id_adapter import to_canonical_hospital_id

logger = logging.getLogger("aiis.routes.hospital_admin")

hospital_admin_bp = Blueprint("hospital_admin", __name__)

emergency_repo = EmergencyRepository()
hospital_repo = HospitalRepository()
appointment_service = AppointmentService()
capacity_service = CapacityService()


@hospital_admin_bp.route("/<hospital_id>/requests", methods=["GET"])
@hospital_admin_bp.route("/<int:hospital_id>/requests", methods=["GET"])
@require_hospital_access("hospital_id")
def get_hospital_requests(hospital_id: Any):
    """
    GET /api/hospital/<hospital_id>/requests
    Lists incoming and active emergency requests targeted at this hospital.
    Protected by @require_hospital_access: Cross-hospital access is strictly blocked.
    """
    canonical_id = to_canonical_hospital_id(hospital_id)
    hospital_requests = emergency_repo.list_by_hospital(canonical_id)
    # Ensure all active requests are included
    for r in emergency_repo.list_active():
        if str(r.get("hospitalId") or r.get("hospital_id")) in (str(canonical_id), f"hsp-{canonical_id:03d}"):
            if not any(x.get("id") == r.get("id") for x in hospital_requests):
                hospital_requests.append(r)

    return success_response(
        data={"hospital_id": canonical_id, "requests": hospital_requests, "count": len(hospital_requests)},
        status_code=200,
    )


@hospital_admin_bp.route("/<hospital_id>/capacity", methods=["GET"])
def get_hospital_capacity(hospital_id: str):
    """
    GET /api/hospital/<hospital_id>/capacity
    Retrieve live capacity snapshot for this hospital.
    """
    canonical_id = to_canonical_hospital_id(hospital_id)
    cap = capacity_service.get_live_capacity(canonical_id)
    return success_response(
        data=cap,
        message="Hospital capacity snapshot retrieved successfully.",
        status_code=200,
    )


@hospital_admin_bp.route("/<hospital_id>/capacity", methods=["POST", "PUT"])
@require_hospital_access("hospital_id")
def update_hospital_capacity(hospital_id: str):
    """
    POST/PUT /api/hospital/<hospital_id>/capacity
    Updates live capacity telemetry for this hospital.
    Protected by @require_hospital_access: Only authorized admin can update.
    """
    data = request.get_json(silent=True)
    if not data:
        raise ValidationException("Request body must be a valid JSON object.")

    canonical_id = to_canonical_hospital_id(hospital_id)
    persisted = capacity_service.update_hospital_capacity(
        canonical_id, data, user_context=getattr(g, "user", None)
    )

    return success_response(
        data=persisted,
        message="Hospital operational capacity updated successfully.",
        status_code=200,
    )


@hospital_admin_bp.route("/<hospital_id>/capacity/history", methods=["GET"])
@require_hospital_access("hospital_id")
def get_hospital_capacity_history(hospital_id: str):
    """
    GET /api/hospital/<hospital_id>/capacity/history
    Retrieve capacity history ledger for this hospital.
    """
    canonical_id = to_canonical_hospital_id(hospital_id)
    limit = request.args.get("limit", 50)
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        limit_int = 50

    history = capacity_service.list_capacity_history(canonical_id, limit=limit_int)
    return success_response(
        data=history,
        message="Hospital capacity history retrieved successfully.",
        meta={"hospital_id": canonical_id, "count": len(history)},
        status_code=200,
    )


@hospital_admin_bp.route("/update-beds", methods=["POST"])
@require_hospital_access("hospital_id")
def update_beds_legacy():
    """
    POST /api/hospital/update-beds (legacy compatibility)
    Accepts { "hospital_id": 1, "num_beds": 100 }
    """
    data = request.get_json(silent=True) or {}
    h_id = data.get("hospital_id") or data.get("hospitalId")
    if h_id is None:
        raise ValidationException("Field 'hospital_id' is required.")

    canonical_id = to_canonical_hospital_id(h_id)
    num_beds = data.get("num_beds")
    if num_beds is None:
        raise ValidationException("Field 'num_beds' is required.")

    try:
        num_beds_int = int(num_beds)
    except (ValueError, TypeError):
        raise ValidationException("Field 'num_beds' must be an integer.")

    persisted = capacity_service.update_hospital_capacity(
        canonical_id,
        {"total_beds": num_beds_int, "num_beds": num_beds_int},
        user_context=getattr(g, "user", None),
    )
    return success_response(
        data={"hospital_id": canonical_id, "num_beds": num_beds_int, "capacity": persisted},
        message="Beds updated successfully.",
        status_code=200,
    )


@hospital_admin_bp.route("/<int:hospital_id>/appointments", methods=["GET"])
@require_hospital_access("hospital_id")
def get_hospital_appointments(hospital_id: int):
    """
    GET /api/hospital/<hospital_id>/appointments
    List scheduled outpatient appointments for this hospital.
    Supports optional status query filter (?status=REQUESTED|CONFIRMED|...).
    Protected by @require_hospital_access.
    """
    status_filter = request.args.get("status")
    appointments = appointment_service.list_hospital_appointments(hospital_id, status=status_filter)
    return success_response(
        data=appointments,
        message=f"Retrieved {len(appointments)} appointments for hospital {hospital_id}.",
        meta={"hospital_id": hospital_id, "count": len(appointments)},
        status_code=200,
    )


@hospital_admin_bp.route("/<int:hospital_id>/appointments/<appointment_id>", methods=["GET"])
@require_hospital_access("hospital_id")
def get_hospital_appointment_by_id(hospital_id: int, appointment_id: str):
    """
    GET /api/hospital/<hospital_id>/appointments/<appointment_id>
    Retrieve a specific appointment for this hospital.
    Protected by @require_hospital_access.
    """
    apt = appointment_service.get_appointment(appointment_id, user_context=g.user)
    if int(apt.get("hospital_id", 0)) != int(hospital_id):
        raise NotFoundException(f"Appointment '{appointment_id}' does not belong to hospital {hospital_id}.")
    return success_response(
        data=apt,
        message="Appointment details retrieved.",
        status_code=200,
    )


@hospital_admin_bp.route("/<int:hospital_id>/appointments/<appointment_id>/status", methods=["PUT"])
@require_hospital_access("hospital_id")
def update_hospital_appointment_status(hospital_id: int, appointment_id: str):
    """
    PUT /api/hospital/<hospital_id>/appointments/<appointment_id>/status
    Update the status of an appointment (CONFIRMED, CANCELLED, COMPLETED).
    Protected by @require_hospital_access.
    """
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status:
        raise ValidationException("Field 'status' is required.")

    notes = data.get("notes")
    updated = appointment_service.update_appointment_status(
        appointment_id, new_status, notes=notes, user_context=g.user
    )
    return success_response(
        data=updated,
        message=f"Appointment '{appointment_id}' status updated to '{new_status}'.",
        status_code=200,
    )
