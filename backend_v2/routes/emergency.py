"""
AIIS Backend V2 - Emergency & Coordination Blueprints
=====================================================
REST API endpoints supporting:
- Patient emergency hospital search (GPS proximity & category match)
- Emergency SOS broadcast with 4-digit arrival OTP
- Real-time SOS status polling
- Patient arrival verification at casualty desk
- Emergency SOS cancellation
- Municipal locations catalog for quick selection
"""

import logging
import hashlib
import secrets
from flask import Blueprint, request, jsonify, g, session

from backend_v2.schemas.emergency_schema import (
    EmergencySearchSchema,
    EmergencySOSCreateSchema,
    EmergencyCancelSchema,
    EmergencyVerifyArrivalSchema,
)
from backend_v2.services.emergency_service import EmergencyService
from backend_v2.services.auth_service import AuthService
from backend_v2.utils.responses import success_response, error_response
from backend_v2.utils.exceptions import (
    ValidationException,
    UnauthorizedException,
    ForbiddenException,
)

logger = logging.getLogger("aiis.routes.emergency")

# Define Blueprints for API transport
emergency_bp = Blueprint("emergency", __name__)
coordination_bp = Blueprint("coordination", __name__)
locations_bp = Blueprint("locations", __name__)

# Instantiate domain service
emergency_service = EmergencyService()


# ── 1. Hospital Search Endpoints ──────────────────────────────────────────────

@emergency_bp.route("/search", methods=["POST"])
def search_emergency_post():
    """
    POST /api/emergency/search
    Intelligent hospital search called by deployed SPA (aiis-livid.vercel.app).
    Accepts JSON body: { latitude, longitude, category, locationName, limit }
    """
    data = request.get_json(silent=True) or {}

    is_valid, err_msg = EmergencySearchSchema.validate(data)
    if not is_valid:
        raise ValidationException(err_msg)

    lat = data.get("latitude")
    lon = data.get("longitude")
    city = data.get("city") or data.get("locationName")
    category = data.get("category") or "general"
    limit = max(1, min(int(data.get("limit", 10)), 25))

    res = emergency_service.search_emergency_hospitals(
        latitude=float(lat) if lat is not None else None,
        longitude=float(lon) if lon is not None else None,
        city=str(city) if city else None,
        category=str(category),
        limit=limit,
    )
    return jsonify(res), 200


@emergency_bp.route("/hospitals", methods=["GET"])
def search_emergency_get():
    """
    GET /api/emergency/hospitals
    Compatible with patient_entry.html and legacy portal query parameters.
    Query params: ?lat=...&lon=...&city=...&emergency_type=...
    """
    lat = request.args.get("lat", default=None, type=float)
    lon = request.args.get("lon", default=None, type=float)
    city = (request.args.get("city") or "").strip()
    category = (request.args.get("emergency_type") or "general").strip().lower()

    search_dict = {
        "latitude": lat,
        "longitude": lon,
        "city": city,
        "category": category,
    }

    is_valid, err_msg = EmergencySearchSchema.validate(search_dict)
    if not is_valid:
        raise ValidationException(err_msg)

    res = emergency_service.search_emergency_hospitals(
        latitude=lat,
        longitude=lon,
        city=city if city else None,
        category=category,
        limit=8,
    )
    return jsonify(res), 200


# ── 2. Emergency SOS & Coordination Endpoints ──────────────────────────────────

def _handle_sos_creation():
    """Shared handler for emergency SOS submission."""
    data = request.get_json(silent=True) or {}

    is_valid, err_msg = EmergencySOSCreateSchema.validate(data)
    if not is_valid:
        raise ValidationException(err_msg)

    record = emergency_service.create_sos(data)
    return jsonify({
        "success": True,
        "request": record,
        "data": record,
        "id": record.get("id"),
        "requestId": record.get("id"),
        "tracking_token": record.get("tracking_token"),
        "guest_tracking_token": record.get("guest_tracking_token"),
        "trackingToken": record.get("trackingToken"),
        "otp": record.get("otp"),
        "arrivalOtp": record.get("arrivalOtp"),
        "arrival_otp": record.get("arrival_otp") or record.get("arrivalOtp") or record.get("otp"),
        "status": record.get("status"),
    }), 201


@emergency_bp.route("/sos", methods=["POST"])
def create_emergency_sos():
    """POST /api/emergency/sos"""
    return _handle_sos_creation()


@coordination_bp.route("/request", methods=["POST"])
def create_coordination_request():
    """POST /api/coordination/request (Contract used by aiis-livid.vercel.app)"""
    return _handle_sos_creation()


def _tracking_token_from_request(body=None):
    """
    Guest tracking token: X-Tracking-Token header, ?token=, body token, or a non-JWT Bearer value.
    A signed-in patient's JWT (three dot-separated parts) is never treated as a tracking token,
    otherwise logged-in users could not follow or cancel their own request.
    """
    body = body or {}
    token = request.headers.get("X-Tracking-Token") or request.headers.get("tracking-token")
    if not token:
        token = body.get("token") or body.get("tracking_token") or request.args.get("token") or request.args.get("tracking_token")
    if not token:
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.startswith("Bearer "):
            candidate = auth_header.split(" ", 1)[1].strip()
            if candidate.count(".") != 2:
                token = candidate
    return token or None


def _handle_get_status(request_id: str):
    """
    Shared handler for retrieving SOS status.
    Accepts tracking token via Authorization (Bearer), X-Tracking-Token header,
    or ?token= query parameter. Never leaks arrival OTP or token hashes.
    """
    token = _tracking_token_from_request()

    record = emergency_service.get_sos(request_id, tracking_token=token)
    return jsonify({
        "success": True,
        "request": record,
        "data": record,
    }), 200


@emergency_bp.route("/<request_id>", methods=["GET"])
@emergency_bp.route("/<request_id>/track", methods=["GET"])
def get_emergency_status(request_id: str):
    """GET /api/emergency/<request_id> or /api/emergency/<request_id>/track"""
    return _handle_get_status(request_id)


@coordination_bp.route("/<request_id>", methods=["GET"])
@coordination_bp.route("/<request_id>/track", methods=["GET"])
def get_coordination_status(request_id: str):
    """GET /api/coordination/<request_id> or /api/coordination/<request_id>/track"""
    return _handle_get_status(request_id)


def _handle_cancel(request_id: str):
    """
    Shared handler for SOS cancellation.
    Accepts tracking token via Authorization (Bearer), X-Tracking-Token header,
    request body, or ?token= query parameter.
    """
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or data.get("cancellation_reason") or "Cancelled by patient")

    token = _tracking_token_from_request(data)

    record = emergency_service.cancel_sos(request_id, reason=reason, tracking_token=token)
    return jsonify({
        "success": True,
        "request": record,
        "data": record,
        "message": "Emergency request cancelled successfully.",
    }), 200


@emergency_bp.route("/<request_id>/cancel", methods=["POST"])
def cancel_emergency(request_id: str):
    """POST /api/emergency/<request_id>/cancel"""
    return _handle_cancel(request_id)


@coordination_bp.route("/<request_id>/cancel", methods=["POST"])
def cancel_coordination(request_id: str):
    """POST /api/coordination/<request_id>/cancel"""
    return _handle_cancel(request_id)


def _handle_verify_arrival(request_id: str):
    """
    Shared handler for arrival verification via OTP.
    Requires authenticated hospital staff authorized for the target hospital.
    A tracking token alone must never authorize arrival verification.
    """
    body = request.get_json(silent=True) or {}

    # 1. Strictly forbid guest tracking tokens from authorizing arrival verification
    raw_tracking = (
        request.headers.get("X-Tracking-Token")
        or request.headers.get("tracking-token")
        or request.args.get("token")
        or request.args.get("tracking_token")
        or body.get("token")
        or body.get("tracking_token")
    )
    if raw_tracking:
        logger.warning(
            f"Arrival verification rejected for {request_id}: Tracking token supplied instead of staff credentials."
        )
        raise ForbiddenException(
            "Guest tracking tokens cannot verify arrival. Authorized hospital staff credentials required."
        )

    # 2. Extract and cryptographically verify staff authentication token
    auth_header = request.headers.get("Authorization", "").strip()
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif getattr(g, "token", None):
        token = g.token

    user_profile = getattr(g, "user", None)
    if not user_profile:
        if not token and "jwt" in session:
            token = session["jwt"]
        if not token and session.get("role") == "hospital_admin" and session.get("hospital_id"):
            user_profile = {
                "id": session.get("user_id", f"staff-{session['hospital_id']}"),
                "role": "hospital_admin",
                "hospital_id": session.get("hospital_id"),
                "email": session.get("email", "staff@hospital.in"),
                "account_status": "active",
            }
        elif not token and session.get("role") in ("authority", "platform_admin"):
            user_profile = {
                "id": session.get("user_id", "authority-user"),
                "role": session.get("role"),
                "hospital_id": None,
                "email": session.get("email", "authority@health.gov.in"),
                "account_status": "active",
            }
        elif not token:
            raise UnauthorizedException("Authentication required to verify patient arrival. Authorized hospital staff JWT required.")
        else:
            auth_svc = AuthService()
            try:
                user_profile = auth_svc.verify_token(token)
            except UnauthorizedException:
                # Check if this token was a guest tracking token mistakenly sent as Bearer
                rec = emergency_service.emergency_repo.get_by_id(request_id)
                if rec:
                    stored_h = rec.get("tracking_token_hash") or rec.get("guest_token_hash")
                    candidate_h = hashlib.sha256(token.encode("utf-8")).hexdigest()
                    if stored_h and secrets.compare_digest(candidate_h, stored_h):
                        raise ForbiddenException(
                            "Guest tracking tokens cannot verify arrival. Authorized hospital staff credentials required."
                        )
                raise UnauthorizedException("Invalid or expired authentication credentials.")

    # 3. Validate arrival payload (OTP)
    is_valid, err_msg = EmergencyVerifyArrivalSchema.validate(body)
    if not is_valid:
        raise ValidationException(err_msg)

    otp = str(body.get("otp", "")).strip()
    record = emergency_service.verify_arrival(request_id, otp=otp, user_context=user_profile)
    return jsonify({
        "success": True,
        "request": record,
        "data": record,
        "message": "Patient arrival verified successfully.",
    }), 200


@emergency_bp.route("/<request_id>/verify-arrival", methods=["POST"])
def verify_emergency_arrival(request_id: str):
    """POST /api/emergency/<request_id>/verify-arrival"""
    return _handle_verify_arrival(request_id)


@coordination_bp.route("/<request_id>/verify-arrival", methods=["POST"])
def verify_coordination_arrival(request_id: str):
    """POST /api/coordination/<request_id>/verify-arrival"""
    return _handle_verify_arrival(request_id)


# ── 3. Locations Catalog ──────────────────────────────────────────────────────

@locations_bp.route("", methods=["GET"])
@locations_bp.route("/", methods=["GET"])
def get_locations():
    """
    GET /api/locations
    Returns monitored cities with coordinates for instant selection.
    """
    locs = emergency_service.get_locations()
    return jsonify({
        "success": True,
        "data": locs,
        "locations": locs,
    }), 200


@locations_bp.route("/detect", methods=["GET"])
def detect_location():
    """
    GET /api/locations/detect
    Detects caller location via client IP / public network or returns primary demo region (Bengaluru).
    """
    import urllib.request as u_req
    try:
        req = u_req.Request(
            "https://ipwho.is/",
            headers={"User-Agent": "Mozilla/5.0 (AIIS Emergency Locator)"}
        )
        with u_req.urlopen(req, timeout=2.5) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("success") is not False and d.get("latitude") and d.get("longitude"):
                return jsonify({
                    "success": True,
                    "city": d.get("city") or "Bengaluru",
                    "latitude": float(d["latitude"]),
                    "longitude": float(d["longitude"]),
                    "source": "ip_network"
                }), 200
    except Exception as exc:
        logger.debug(f"IP location detection fallback to default: {exc}")

    return jsonify({
        "success": True,
        "city": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "source": "default"
    }), 200


@emergency_bp.route("/hospital/<int:hospital_id>/requests", methods=["GET"])
def get_hospital_requests_endpoint(hospital_id: int):
    """
    GET /api/emergency/hospital/:id/requests
    Returns active and recent emergency requests for facility intake desk.
    """
    reqs = emergency_service.get_hospital_emergency_requests(hospital_id)
    return jsonify({
        "status": "success",
        "data": reqs,
        "requests": reqs,
    }), 200
