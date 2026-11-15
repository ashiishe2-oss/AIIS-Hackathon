"""
AIIS Backend V2 - Planned Healthcare Blueprint
==============================================
Citizen planned healthcare and outpatient (OPD) discovery:
- Search facilities by specialty or department (e.g. Cardiology, Paediatrics)
- Hospital name, code, or identifier matching
- Municipal city or area directory filtering
- Geolocation GPS proximity filtering
- Enforces honest data classification: states consultant rota and waiting times as unmonitored.
"""

import logging
from flask import Blueprint, request, jsonify

from backend_v2.schemas.hospital_schema import PlannedSearchSchema
from backend_v2.services.hospital_service import HospitalService
from backend_v2.utils.hospital_id_adapter import enrich_hospital_identifiers
from backend_v2.utils.exceptions import ValidationException

logger = logging.getLogger("aiis.routes.planned")

planned_bp = Blueprint("planned", __name__)
hospital_service = HospitalService()


@planned_bp.route("/search", methods=["POST"])
def search_planned_healthcare():
    """
    POST /api/planned/search
    Intelligent planned healthcare facility discovery for outpatient care.
    Accepts JSON body: { specialty, hospital, city, latitude, longitude, radius, page, limit }
    """
    data = request.get_json(silent=True) or {}
    is_valid, err_msg, cleaned_params = PlannedSearchSchema.validate(data)
    if not is_valid:
        raise ValidationException(err_msg or "Invalid search parameters.")

    # Search hospitals using hospital service
    result = hospital_service.search_hospitals(cleaned_params)

    # If specific hospital_id was requested, filter directly
    target_hosp_id = cleaned_params.get("hospital_id")
    items = result.get("items", [])
    if target_hosp_id is not None:
        items = [h for h in items if int(h.get("id", 0)) == int(target_hosp_id)]
        result["items"] = items
        result["total"] = len(items)

    # Enrich each facility with canonical frontend IDs, departments, and honest limitations
    # Batch-load departments to avoid N+1 remote queries
    dept_map = {}
    try:
        all_depts = hospital_service.hospital_repo.list_departments()
        for d in all_depts:
            hid = d.get("hospital_id")
            if hid is not None:
                dept_map.setdefault(int(hid), []).append(d)
    except Exception:
        dept_map = {}

    for h in items:
        enrich_hospital_identifiers(h)
        h_id_val = int(h.get("id", 0))
        # Only departments a hospital has actually reported; never invent doctor counts.
        h["departments"] = dept_map.get(h_id_val) or []

        # Honest disclosure: real-time clinician availability & live waiting times are not monitored
        h["consultant_availability"] = False
        h["doctor_availability"] = None
        h["consultant_schedule"] = "Unavailable - Real-time OPD clinician rota is not monitored."
        h["waiting_time_disclaimer"] = "Real-time clinician waiting time is not monitored; subject to on-site casualty triage."
        h["opd_schedule_notice"] = "Consultation slots are subject to hospital casualty and OPD registration on arrival."
        h["estimated_waiting_time"] = None
        h["live_slots_available"] = False
        h["booking_mode"] = "REQUESTED"

    return jsonify({
        "success": True,
        "data": items,
        "items": items,
        "results": items,
        "meta": {
            "total": result.get("total", len(items)),
            "page": result.get("page", 1),
            "limit": result.get("limit", 20),
            "pages": result.get("pages", 1),
            "specialty": cleaned_params.get("specialty"),
            "city": cleaned_params.get("city"),
            "capacity_source": "seeded_baseline",
            "verified_realtime": False,
            "realtime_consultant_roster": False,
            "notice": "Consultation slots are subject to hospital casualty and OPD registration on arrival.",
            "limitations": "Clinician schedules and real-time waiting times are not provided by baseline infrastructure telemetry.",
        },
    }), 200
