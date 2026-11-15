"""
AIIS Backend V2 - Emergency Service
===================================
Domain orchestrator for patient Emergency SOS workflows:
- Intelligent proximity search and clinical categorization
- Emergency SOS broadcast and provisional bed hold creation
- Real-time status tracking with cryptographic guest tokens
- Patient arrival OTP verification at hospital casualty desks
- Request cancellation handling
"""

import math
import random
import logging
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend_v2.repositories.emergency_repository import EmergencyRepository
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.services.audit_service import AuditService
from backend_v2.services.capacity_service import CapacityService
from backend_v2.utils.exceptions import (
    AppException,
    NotFoundException,
    ValidationException,
    ConflictException,
    ForbiddenException,
    UnauthorizedException,
)
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    to_frontend_hospital_id,
    enrich_hospital_identifiers,
)

logger = logging.getLogger("aiis.services.emergency")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def estimate_transit_minutes(distance_km: float) -> int:
    """
    Rough city travel time by road: straight-line distance x 1.35 road factor,
    about 20 km/h average city traffic, plus 3 minutes to get moving.
    """
    return max(3, int(round(distance_km * 1.35 / 20.0 * 60.0 + 3)))


# Which specialty hospitals suit which emergency (24x7 general hospitals suit all of them).
CATEGORY_SCOPES = {
    "general": [], "cardiac": ["cardiac"], "stroke": ["neuro"], "trauma": ["trauma"],
    "child": ["children"], "pregnancy": ["maternity"], "eye": ["eye"], "breathing": [], "burns": [],
}


class EmergencyService:
    """Service handling citizen emergency search and SOS workflows."""

    def __init__(
        self,
        emergency_repo: Optional[EmergencyRepository] = None,
        hospital_repo: Optional[HospitalRepository] = None,
        audit_service: Optional[AuditService] = None,
        capacity_service: Optional[CapacityService] = None,
    ):
        self.emergency_repo = emergency_repo or EmergencyRepository()
        self.hospital_repo = hospital_repo or HospitalRepository()
        self.audit_service = audit_service or AuditService()
        self.capacity_service = capacity_service or CapacityService()

    def search_emergency_hospitals(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        city: Optional[str] = None,
        category: str = "general",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search and rank public hospitals for emergency intake.
        Supports GPS proximity calculation or municipal city directory filtering.
        """
        all_hospitals = self.hospital_repo.list_all()
        has_coords = latitude is not None and longitude is not None
        suits = CATEGORY_SCOPES.get(category, [])
        ranked: List[Dict[str, Any]] = []

        def beds_of(h: Dict[str, Any]) -> Optional[int]:
            cap = h.get("capacity") or {}
            er = cap.get("emergencyBeds") if isinstance(cap, dict) else None
            val = er.get("available") if isinstance(er, dict) else None
            return int(val) if isinstance(val, (int, float)) else None

        if has_coords:
            match_basis = "straight_line_distance"
            for h in all_hospitals:
                h_lat = float(h.get("lat") or h.get("latitude") or 0.0)
                h_lon = float(h.get("lon") or h.get("longitude") or 0.0)
                if h_lat == 0.0 and h_lon == 0.0:
                    continue
                dist = round(haversine_km(latitude, longitude, h_lat, h_lon), 1)
                mins = estimate_transit_minutes(dist)
                scope = h.get("emergencyScope") or "general"
                is_general = scope == "general"
                matches = scope in suits
                beds = beds_of(h)
                simulated = bool((h.get("dataFreshness") or {}).get("isSimulated"))

                effective = mins
                if not is_general and not matches:
                    effective += 10  # keep specialty-only hospitals below nearby general ones
                if matches:
                    effective -= 5
                if beds == 0 and not simulated:
                    effective += 15

                reasons = [f"About {mins} min away ({dist} km in a straight line)"]
                if not is_general:
                    reasons.append(h.get("scopeNote") or "Specialty hospital")
                if beds is not None and not simulated:
                    reasons.append(f"{beds} emergency beds free, reported by the hospital" if beds > 0 else "Hospital reports no emergency beds free")
                elif beds is not None and simulated:
                    reasons.append("Bed numbers are sample (demo) values. Call to confirm.")
                else:
                    reasons.append("Live bed numbers not shared. Call to check.")

                item = {
                    **h,
                    "distanceKm": dist,
                    "distance_km": dist,
                    "transitMins": mins,
                    "transit_minutes": mins,
                    "effectiveMins": effective,
                    "primary": is_general or matches,
                    "whyRanked": reasons,
                    "rationale": reasons,
                }
                if h.get("directoryOnly"):
                    item["partner"] = False
                enrich_hospital_identifiers(item)
                ranked.append(item)

            key = lambda x: (x["effectiveMins"], x["distanceKm"])
            primary = sorted([x for x in ranked if x["primary"]], key=key)
            top = primary[:3]
            rest = sorted([x for x in ranked if x not in top], key=lambda x: (x["transitMins"], x["distanceKm"]))
            ranked = top + rest
        else:
            match_basis = "city_directory"
            target_city = (city or "").strip().lower()
            for h in all_hospitals:
                if target_city and target_city not in (h.get("city") or "").lower():
                    continue
                item = {
                    **h,
                    "distanceKm": None,
                    "distance_km": None,
                    "transitMins": None,
                    "transit_minutes": None,
                    "whyRanked": [f"Hospital in {h.get('city')}"],
                    "rationale": [f"Hospital in {h.get('city')}"],
                }
                if h.get("directoryOnly"):
                    item["partner"] = False
                enrich_hospital_identifiers(item)
                ranked.append(item)
            ranked.sort(key=lambda x: ((x.get("emergencyScope") or "general") != "general", x.get("name", "")))

        results = [dict(r, rank=i + 1) for i, r in enumerate(ranked[:limit])]
        quick = next((r for r in results if r.get("primary", True) and r.get("emergencyPhone") and r.get("phoneStatus") == "official"), None) \
            or next((r for r in results if r.get("primary", True) and r.get("emergencyPhone")), None)

        return {
            "success": True,
            "data": results,
            "results": results,
            "rankedHospitals": results,
            "hospitals": results,
            "quickCall": {
                "hospitalId": quick["id"], "name": quick["name"], "phone": quick["emergencyPhone"],
                "phoneLabel": quick.get("emergencyPhoneLabel") or "Emergency",
                "transitMins": quick.get("transitMins"), "distanceKm": quick.get("distanceKm"),
            } if quick else None,
            "meta": {
                "emergency_type": category,
                "category": category,
                "match_basis": match_basis,
                "result_count": len(results),
                "availability_verified": False,
                "locations_verified": "Hospital pins and addresses match each hospital's Google Maps listing.",
                "notice": (
                    "Distances are straight-line from your location; travel times are estimates. "
                    "Bed numbers may be sample values: call the hospital to confirm, or call 108/112."
                ),
            },
        }

    def create_sos(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create and broadcast a patient Emergency SOS request.
        Generates a 4-digit arrival OTP, sets a provisional bed hold,
        generates a cryptographically secure guest tracking token,
        and records the event for hospital casualty desk notification.
        """
        raw_hosp_id = payload.get("hospitalId") if payload.get("hospitalId") is not None else payload.get("hospital_id")
        canonical_hosp_id = to_canonical_hospital_id(raw_hosp_id)
        hospital = self.hospital_repo.get_by_id(canonical_hosp_id)
        if not hospital:
            raise NotFoundException(f"Hospital with ID '{raw_hosp_id}' does not exist.")
        if hospital.get("directoryOnly") or hospital.get("partner") is False:
            raise ConflictException(
                f"{hospital.get('name', 'This hospital')} is not connected to AIIS yet. Please call them directly."
            )

        # Generate unique request ID: REQ-XXXXXX
        random_suffix = f"{random.randint(0x100000, 0xFFFFFF):06X}"
        request_id = f"REQ-{random_suffix}"

        # Generate 4-digit numeric arrival OTP
        otp_code = f"{random.randint(1000, 9999)}"

        # Generate cryptographically secure plaintext guest tracking token
        plaintext_tracking_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plaintext_tracking_token.encode("utf-8")).hexdigest()

        now = datetime.now(timezone.utc)
        travel_mins = int(
            payload.get("estimatedTravelMinutes")
            or payload.get("estimated_travel_minutes")
            or 15
        )
        # 30-minute default window (travel time + 15 min buffer)
        hold_expires_at = (now + timedelta(minutes=travel_mins + 15)).isoformat()

        sos_record = {
            "id": request_id,
            "requestId": request_id,
            "hospitalId": canonical_hosp_id,
            "hospital_id": canonical_hosp_id,
            "hospitalCode": to_frontend_hospital_id(canonical_hosp_id),
            "hospital_code": to_frontend_hospital_id(canonical_hosp_id),
            "hospitalName": hospital.get("name", "Public Hospital"),
            "hospitalAddress": hospital.get("address", ""),
            "emergencyPhone": hospital.get("emergencyPhone") or hospital.get("phone"),
            "patientName": payload.get("patientName") or payload.get("patient_name") or "Patient",
            "companionName": payload.get("companionName") or payload.get("companion_name"),
            "contactPhone": payload.get("contactPhone") or payload.get("contact_phone"),
            "emergencyCategory": (
                payload.get("emergencyCategory")
                or payload.get("emergency_category")
                or payload.get("category")
                or "general"
            ),
            "status": "REQUEST_SUBMITTED",
            "otp": otp_code,
            "arrivalOtp": otp_code,
            "arrival_otp": otp_code,
            "estimatedTravelMinutes": travel_mins,
            "estimated_travel_minutes": travel_mins,
            "userLocationName": (
                payload.get("userLocationName")
                or payload.get("user_location_name")
                or payload.get("locationName")
            ),
            "latitude": payload.get("latitude") if payload.get("latitude") is not None else payload.get("lat"),
            "longitude": payload.get("longitude") if payload.get("longitude") is not None else (
                payload.get("lon") if payload.get("lon") is not None else payload.get("lng")
            ),
            "notes": payload.get("notes"),
            "holdExpiresAt": hold_expires_at,
            "hold_expires_at": hold_expires_at,
            "guest_token_hash": token_hash,
            "tracking_token_hash": token_hash,
            "created_at": now.isoformat(),
            "createdAt": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # Atomically allocate provisional emergency bed hold
        self.capacity_service.allocate_provisional_hold(canonical_hosp_id, request_id)

        # Persist through repository
        saved_record = self.emergency_repo.create_request(sos_record)

        # Log audit event
        self.audit_service.log_event(
            event_type="EMERGENCY_SOS_CREATED",
            actor_id=payload.get("contactPhone") or "citizen_anonymous",
            actor_role="citizen",
            target_resource=f"hospital/{canonical_hosp_id}",
            details={"request_id": request_id, "category": sos_record["emergencyCategory"]},
        )

        # NEVER log the plaintext token or arrival OTP
        logger.info(
            f"Emergency SOS created: {request_id} for hospital {canonical_hosp_id}"
        )

        # Response contains plaintext tracking token for client (returned only once at creation)
        # Internal token hash is stripped
        response_dict = dict(saved_record)
        response_dict.pop("guest_token_hash", None)
        response_dict.pop("tracking_token_hash", None)
        response_dict["tracking_token"] = plaintext_tracking_token
        response_dict["guest_tracking_token"] = plaintext_tracking_token
        response_dict["trackingToken"] = plaintext_tracking_token
        response_dict["arrival_otp"] = otp_code
        return response_dict

    def get_sos(
        self, request_id: str, tracking_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch details of an active or past emergency request.
        If a tracking token is supplied, validates it cryptographically against stored hash.
        Never exposes internal token hashes.
        """
        record = self.emergency_repo.get_by_id(request_id)
        if not record:
            raise NotFoundException(f"Emergency request '{request_id}' not found.")

        # If tracking token was provided, verify it strictly using constant-time comparison
        stored_hash = record.get("tracking_token_hash") or record.get("guest_token_hash")
        if tracking_token is not None:
            candidate_hash = hashlib.sha256(str(tracking_token).strip().encode("utf-8")).hexdigest()
            if not stored_hash or not secrets.compare_digest(candidate_hash, stored_hash):
                raise AppException(
                    message="Invalid or expired guest tracking token.",
                    error_code="UNAUTHORIZED",
                    status_code=401,
                )

        # Check for hold expiration if request is still in submitted status
        hold_exp_str = record.get("hold_expires_at") or record.get("holdExpiresAt")
        if record.get("status") == "REQUEST_SUBMITTED" and hold_exp_str:
            try:
                hold_exp_dt = datetime.fromisoformat(hold_exp_str.replace("Z", "+00:00"))
                if hold_exp_dt.tzinfo is None:
                    hold_exp_dt = hold_exp_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > hold_exp_dt:
                    h_id = record.get("hospital_id") or record.get("hospitalId")
                    if h_id:
                        self.capacity_service.release_provisional_hold(h_id, request_id, reason="expired")
                    self.emergency_repo.update_status(request_id, "EXPIRED")
                    record["status"] = "EXPIRED"
            except Exception as e:
                logger.debug(f"Hold expiration check parsing error: {e}")

        # Clean internal hashes & token attributes
        safe_record = dict(record)
        safe_record.pop("guest_token_hash", None)
        safe_record.pop("tracking_token_hash", None)
        safe_record.pop("tracking_token", None)
        safe_record.pop("guest_tracking_token", None)
        safe_record.pop("trackingToken", None)

        # Guarantee dual-key naming for frontend compatibility
        safe_record["requestId"] = safe_record.get("id")
        safe_record["hospitalId"] = safe_record.get("hospital_id")
        if safe_record.get("hospital_id"):
            h_code = to_frontend_hospital_id(int(safe_record["hospital_id"]))
            safe_record["hospitalCode"] = h_code
            safe_record["hospital_code"] = h_code
        # Strip arrival OTP and sensitive credentials from status polling
        safe_record.pop("otp", None)
        safe_record.pop("arrivalOtp", None)
        safe_record.pop("arrival_otp", None)
        safe_record["holdExpiresAt"] = safe_record.get("hold_expires_at")
        safe_record["createdAt"] = safe_record.get("created_at")

        # Ensure hospital details are present
        if not safe_record.get("hospitalName") and safe_record.get("hospital_id"):
            h = self.hospital_repo.get_by_id(safe_record["hospital_id"])
            if h:
                safe_record["hospitalName"] = h.get("name")
                safe_record["hospitalAddress"] = h.get("address")
                safe_record["emergencyPhone"] = h.get("phone")

        return safe_record

    def cancel_sos(
        self,
        request_id: str,
        reason: str = "Cancelled by patient",
        tracking_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an ongoing emergency request."""
        record = self.get_sos(request_id, tracking_token=tracking_token)
        if record.get("status") in {"PATIENT_ARRIVED", "CANCELLED", "EXPIRED"}:
            raise ConflictException(f"Cannot cancel request in status '{record.get('status')}'.")

        # Release provisional hold if request was active
        if record.get("status") == "REQUEST_SUBMITTED":
            h_id = record.get("hospital_id") or record.get("hospitalId")
            if h_id:
                self.capacity_service.release_provisional_hold(h_id, request_id, reason="cancelled")

        updated = self.emergency_repo.update_status(
            request_id=request_id,
            status="CANCELLED",
            cancellation_reason=reason,
        )

        self.audit_service.log_event(
            event_type="EMERGENCY_SOS_CANCELLED",
            actor_id=record.get("contactPhone") or "citizen_anonymous",
            actor_role="citizen",
            target_resource=f"request/{request_id}",
            details={"reason": reason},
        )

        logger.info(f"Emergency SOS {request_id} cancelled: {reason}")
        return self.get_sos(request_id)

    def verify_arrival(
        self, request_id: str, otp: str, user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify patient arrival at hospital casualty desk using the 4-digit OTP.
        Transitions request to 'PATIENT_ARRIVED'.
        Requires authenticated hospital staff authorized for this hospital facility.
        Guarantees idempotency on repeat calls.
        """
        record = self.emergency_repo.get_by_id(request_id)
        if not record:
            raise NotFoundException(f"Emergency request '{request_id}' not found.")

        # Enforce staff authorization if user_context provided
        if user_context is not None:
            role = user_context.get("role")
            if role == "guest":
                raise ForbiddenException(
                    "Guest tracking tokens cannot verify arrival. Authorized hospital staff credentials required."
                )
            if role not in ("hospital_admin", "authority", "platform_admin"):
                raise ForbiddenException(
                    "Only authorized hospital staff or health authorities can verify patient arrival."
                )
            if role == "hospital_admin":
                user_hosp = user_context.get("hospital_id")
                target_hosp = record.get("hospital_id") or record.get("hospitalId")
                if not user_hosp or to_canonical_hospital_id(user_hosp) != to_canonical_hospital_id(target_hosp):
                    raise ForbiddenException(
                        "You do not have permission to verify arrival for this hospital facility."
                    )

        # Constant-time OTP comparison
        saved_otp = str(record.get("otp") or "").strip()
        provided_otp = str(otp).strip()

        if not saved_otp or not secrets.compare_digest(saved_otp, provided_otp):
            logger.warning(f"Arrival verification failed for {request_id}: OTP mismatch.")
            raise ValidationException("Invalid arrival code (OTP). Please check the 4-digit code.")

        # Idempotency check: if already arrived, return without double-counting beds
        if record.get("status") == "PATIENT_ARRIVED":
            logger.info(f"Patient arrival already verified for {request_id} (idempotent call).")
            return self.get_sos(request_id)

        if record.get("status") == "CANCELLED":
            raise ConflictException("This emergency request was previously cancelled.")

        # Transition provisional hold into confirmed occupied bed
        if record.get("status") == "REQUEST_SUBMITTED":
            h_id = record.get("hospital_id") or record.get("hospitalId")
            if h_id:
                self.capacity_service.confirm_provisional_hold_arrival(h_id, request_id)

        updated = self.emergency_repo.update_status(
            request_id=request_id,
            status="PATIENT_ARRIVED",
        )

        self.audit_service.log_event(
            event_type="PATIENT_ARRIVED_VERIFIED",
            actor_id=user_context.get("id") if user_context else f"hospital/{record.get('hospital_id')}",
            actor_role=user_context.get("role") if user_context else "hospital_admin",
            target_resource=f"request/{request_id}",
            details={"verified_at": datetime.now(timezone.utc).isoformat(), "hospital_id": record.get("hospital_id")},
        )

        logger.info(f"Patient arrival verified successfully for {request_id}.")
        return self.get_sos(request_id)

    def expire_request(self, request_id: str) -> Dict[str, Any]:
        """Manually or automatically expire a provisional bed hold."""
        record = self.emergency_repo.get_by_id(request_id)
        if not record:
            raise NotFoundException(f"Emergency request '{request_id}' not found.")

        if record.get("status") == "REQUEST_SUBMITTED":
            h_id = record.get("hospital_id") or record.get("hospitalId")
            if h_id:
                self.capacity_service.release_provisional_hold(h_id, request_id, reason="expired")
            self.emergency_repo.update_status(request_id, "EXPIRED")
            record["status"] = "EXPIRED"

            self.audit_service.log_event(
                event_type="EMERGENCY_HOLD_EXPIRED",
                actor_id="system_expiry",
                actor_role="system",
                target_resource=f"request/{request_id}",
                details={"request_id": request_id},
            )

        return self.get_sos(request_id)

    def get_locations(self) -> List[Dict[str, Any]]:
        """Return available cities and coordinates for quick frontend selection."""
        locs = self.hospital_repo.get_locations()
        enriched = []
        for loc in locs:
            name = loc.get("name") or loc.get("city") or ""
            lat = loc.get("lat") if loc.get("lat") is not None else loc.get("latitude")
            lon = loc.get("lon") if loc.get("lon") is not None else (
                loc.get("lng") if loc.get("lng") is not None else loc.get("longitude")
            )
            enriched.append({
                "name": name,
                "city": name,
                "lat": lat,
                "lng": lon,
                "lon": lon,
                "latitude": lat,
                "longitude": lon,
            })
        return enriched

    def get_hospital_emergency_requests(self, hospital_id: int) -> List[Dict[str, Any]]:
        """Retrieve recent emergency requests for a facility casualty desk."""
        records = self.emergency_repo.list_by_hospital(hospital_id)
        sanitized = []
        for r in records:
            item = dict(r)
            item.pop("otp", None)
            item.pop("arrivalOtp", None)
            item.pop("otp_code_hash", None)
            item.pop("tracking_token_hash", None)
            sanitized.append(item)
        return sanitized
