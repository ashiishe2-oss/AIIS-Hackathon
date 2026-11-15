"""
AIIS Backend V2 - Hospitals Blueprint
=====================================
Public hospital directory, capability discovery, proximity filtering,
and departmental operational readiness.
Enforces honest data classification: labels baseline capacity as 'seeded_baseline'.
"""

import logging
from flask import Blueprint, request
from backend_v2.services.hospital_service import HospitalService
from backend_v2.schemas.hospital_schema import HospitalFilterSchema
from backend_v2.utils.responses import success_response
from backend_v2.utils.exceptions import ValidationException, NotFoundException
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    enrich_hospital_identifiers,
)

logger = logging.getLogger("aiis.routes.hospitals")

hospitals_bp = Blueprint("hospitals", __name__)
departments_bp = Blueprint("departments", __name__)

hospital_service = HospitalService()


@hospitals_bp.route("", methods=["GET"])
def list_hospitals():
    """
    GET /api/hospitals
    Query and filter public hospitals by city, specialty, search term, or GPS proximity.
    Supports pagination via `page` and `limit`.
    """
    query_params = request.args.to_dict()
    is_valid, err_msg, cleaned_params = HospitalFilterSchema.validate(query_params)
    if not is_valid:
        raise ValidationException(err_msg or "Invalid query parameters.")

    result = hospital_service.search_hospitals(cleaned_params)

    # Enrich hospital records with frontend-compatible codes and normalized coordinates
    for item in result.get("items", []):
        enrich_hospital_identifiers(item)

    return success_response(
        data=result["items"],
        message=f"Found {result['total']} matching facilities.",
        meta={
            "total": result["total"],
            "page": result["page"],
            "limit": result["limit"],
            "pages": result["pages"],
            "capacity_source": result["capacity_source"],
            "verified_realtime": result["verified_realtime"],
        },
        status_code=200,
    )


@hospitals_bp.route("/departments", methods=["GET"])
@departments_bp.route("", methods=["GET"])
def get_all_departments():
    """
    GET /api/departments (also aliased under GET /api/hospitals/departments)
    Retrieve distinct clinical departments across the public health network.
    """
    depts = hospital_service.get_departments(hospital_id=None)
    return success_response(
        data=depts,
        message="Network departments retrieved successfully.",
        status_code=200,
    )


@hospitals_bp.route("/<hospital_id>", methods=["GET"])
def get_hospital(hospital_id: str):
    """
    GET /api/hospitals/<hospital_id>
    Retrieve comprehensive facility profile including verified clinical capabilities,
    departments, diagnostic equipment availability, and baseline capacity metrics.
    Accepts both canonical integer IDs (e.g. 1) and frontend string codes (e.g. 'hsp-001').
    """
    if hospital_id == "departments":
        return get_all_departments()

    try:
        canonical_id = to_canonical_hospital_id(hospital_id)
    except ValidationException:
        raise NotFoundException(f"Hospital with identifier '{hospital_id}' not found.")

    profile = hospital_service.get_hospital_details(canonical_id)
    enrich_hospital_identifiers(profile)

    return success_response(
        data=profile,
        message="Hospital profile retrieved successfully.",
        status_code=200,
    )


@hospitals_bp.route("/<hospital_id>/departments", methods=["GET"])
def get_hospital_departments(hospital_id: str):
    """
    GET /api/hospitals/<hospital_id>/departments
    Retrieve active departments and doctors on duty for a specific facility.
    Accepts both canonical integer IDs (e.g. 1) and frontend string codes (e.g. 'hsp-001').
    """
    try:
        canonical_id = to_canonical_hospital_id(hospital_id)
    except ValidationException:
        raise NotFoundException(f"Hospital with identifier '{hospital_id}' not found.")

    depts = hospital_service.get_departments(hospital_id=canonical_id)
    return success_response(
        data=depts,
        message="Hospital departments retrieved successfully.",
        status_code=200,
    )
