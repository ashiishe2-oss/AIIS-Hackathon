"""
AIIS Backend V2 - Appointments Blueprint
========================================
Citizen-facing outpatient (OPD) consultation appointment booking,
history, and cancellation endpoints.
Supports canonical V2 routes and frontend compatibility aliases:
- POST /api/appointments and POST /api/appointments/request
- GET /api/appointments/me and GET /api/appointments?phone=...
- GET /api/appointments/<id>
- POST /api/appointments/<id>/cancel
Enforces RBAC, cryptographic token verification, and patient identity isolation.
"""

import logging
from flask import Blueprint, request, jsonify, g
from backend_v2.services.appointment_service import AppointmentService
from backend_v2.middleware.auth import require_auth, optional_auth
from backend_v2.utils.responses import success_response
from backend_v2.utils.exceptions import ValidationException, UnauthorizedException

logger = logging.getLogger("aiis.routes.appointments")

appointments_bp = Blueprint("appointments", __name__)
appointment_service = AppointmentService()


@appointments_bp.route("", methods=["POST"])
@appointments_bp.route("/request", methods=["POST"])
@optional_auth
def create_appointment():
    """
    POST /api/appointments (also aliased under POST /api/appointments/request)
    Book a new outpatient (OPD) consultation appointment.
    Validates required fields, rejects past dates, resolves hospital IDs,
    and binds trusted patient identity if authenticated.
    """
    data = request.get_json(silent=True)
    if not data:
        raise ValidationException("Request body must be a valid JSON object.")

    created = appointment_service.create_appointment(
        data, user_context=getattr(g, "user", None)
    )
    return success_response(
        data=created,
        message="Outpatient appointment scheduled successfully.",
        status_code=201,
    )


@appointments_bp.route("", methods=["GET"])
@appointments_bp.route("/me", methods=["GET"])
@require_auth
def get_my_appointments():
    """
    GET /api/appointments (also aliased under GET /api/appointments/me)
    List all appointments booked by the authenticated citizen/patient.
    Protected by @require_auth. Strict tenant isolation to caller's user_id.
    Optional query param ?phone=... validates caller identity without cross-tenant leakage.
    """
    user_id = g.user["id"]
    phone_param = request.args.get("phone")
    appointments = appointment_service.list_my_appointments(user_id, phone_hint=phone_param)
    return jsonify({
        "status": "success",
        "success": True,
        "data": appointments,
        "appointments": appointments,
        "message": f"Retrieved {len(appointments)} appointments for current patient.",
        "meta": {"count": len(appointments), "total": len(appointments)},
    }), 200


@appointments_bp.route("/<appointment_id>", methods=["GET"])
@require_auth
def get_appointment(appointment_id: str):
    """
    GET /api/appointments/<appointment_id>
    Retrieve appointment details.
    Enforces RBAC: patients may only view their own appointments;
    hospital admins may only view appointments for their assigned facility.
    """
    apt = appointment_service.get_appointment(appointment_id, user_context=g.user)
    return success_response(
        data=apt,
        message="Appointment details retrieved.",
        status_code=200,
    )


@appointments_bp.route("/<appointment_id>/cancel", methods=["POST"])
@require_auth
def cancel_appointment(appointment_id: str):
    """
    POST /api/appointments/<appointment_id>/cancel
    Cancel an existing outpatient appointment.
    Authorized for the owning patient, assigned hospital administrator, or authority.
    Prevents invalid transitions on already cancelled or completed appointments.
    """
    req_data = request.get_json(silent=True) or {}
    reason = req_data.get("reason") or req_data.get("cancellation_reason")
    user_ctx = g.user
    cancelled = appointment_service.cancel_appointment(
        appointment_id, user_context=user_ctx, reason=reason
    )
    return success_response(
        data=cancelled,
        message="Appointment has been successfully cancelled.",
        status_code=200,
    )
