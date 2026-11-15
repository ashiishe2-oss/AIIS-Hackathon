"""
AIIS Backend V2 - Hospital Capacity Blueprint
=============================================
REST API endpoints for hospital capacity inspection and updates:
- POST /api/hospitals/:id/capacity (and PUT /api/hospitals/:id/capacity)
- GET /api/hospitals/:id/capacity
- GET /api/hospitals/:id/capacity/history
- Compatibility aliases under /api/hospital/:id/capacity and /api/update-beds
Protected by strict role-based access control (hospital administrators for target facility, authority, platform admin).
"""

import logging
from flask import Blueprint, request, g

from backend_v2.middleware.auth import require_hospital_access, require_auth, optional_auth
from backend_v2.services.capacity_service import CapacityService
from backend_v2.utils.responses import success_response
from backend_v2.utils.exceptions import ValidationException, ForbiddenException
from backend_v2.utils.hospital_id_adapter import to_canonical_hospital_id

logger = logging.getLogger("aiis.routes.capacity")

capacity_bp = Blueprint("capacity", __name__)
capacity_service = CapacityService()


@capacity_bp.route("/<hospital_id>/capacity", methods=["POST", "PUT"])
@require_hospital_access("hospital_id")
def update_capacity(hospital_id: str):
    """
    POST /api/hospitals/<hospital_id>/capacity (also PUT)
    Update live operational capacity telemetry for this hospital.
    Only authenticated hospital admins assigned to this facility (or authority/admin) can update.
    Validates non-negative figures and mathematical balance constraints.
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


@capacity_bp.route("/<hospital_id>/capacity", methods=["GET"])
@optional_auth
def get_capacity(hospital_id: str):
    """
    GET /api/hospitals/<hospital_id>/capacity
    Retrieve current operational capacity snapshot, department readiness,
    equipment availability, and freshness metadata.
    """
    canonical_id = to_canonical_hospital_id(hospital_id)
    cap = capacity_service.get_live_capacity(canonical_id)
    return success_response(
        data=cap,
        message="Hospital capacity snapshot retrieved successfully.",
        status_code=200,
    )


@capacity_bp.route("/<hospital_id>/capacity/history", methods=["GET"])
@require_hospital_access("hospital_id")
def get_capacity_history(hospital_id: str):
    """
    GET /api/hospitals/<hospital_id>/capacity/history
    Retrieve append-only historical capacity ledger snapshots for this facility.
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
