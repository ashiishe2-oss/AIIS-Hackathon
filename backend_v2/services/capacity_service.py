"""
AIIS Backend V2 - Capacity Management Service
=============================================
Domain business logic for hospital live capacity telemetry,
department readiness, equipment availability, and provisional emergency bed holds.
Enforces honest data classification: distinguishes baseline capacity from verified real-time telemetry.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from backend_v2.repositories.capacity_repository import CapacityRepository
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.schemas.capacity_schema import CapacityUpdateSchema
from backend_v2.services.audit_service import AuditService
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    to_frontend_hospital_id,
)
from backend_v2.utils.exceptions import (
    ValidationException,
    NotFoundException,
    ConflictException,
)

logger = logging.getLogger("aiis.services.capacity")


class CapacityService:
    """Service handling hospital capacity snapshots, updates, and emergency provisional holds."""

    def __init__(
        self,
        capacity_repo: Optional[CapacityRepository] = None,
        hospital_repo: Optional[HospitalRepository] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self.capacity_repo = capacity_repo or CapacityRepository()
        self.hospital_repo = hospital_repo or HospitalRepository()
        self.audit_service = audit_service or AuditService()

    def _enrich_capacity_record(
        self, capacity: Dict[str, Any], hospital_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Attach frontend compatibility keys, departments, and equipment."""
        enriched = dict(capacity)
        h_id = int(capacity.get("hospital_id", 0))
        code = to_frontend_hospital_id(h_id)

        enriched["hospitalId"] = code
        enriched["hospitalCode"] = code
        enriched["hospital_code"] = code
        enriched["hospital_id"] = h_id

        if not hospital_name and h_id:
            hosp = self.hospital_repo.get_by_id(h_id)
            if hosp:
                hospital_name = hosp.get("name")

        if hospital_name:
            enriched["hospital_name"] = hospital_name
            enriched["hospitalName"] = hospital_name

        # Frontend camelCase aliases
        enriched["totalBeds"] = enriched.get("total_beds", 0)
        enriched["availableBeds"] = enriched.get("available_beds", 0)
        enriched["occupiedBeds"] = enriched.get("occupied_beds", 0)
        enriched["provisionallyAllocatedBeds"] = enriched.get("provisionally_allocated_beds", 0)
        enriched["icuTotal"] = enriched.get("icu_total", 0)
        enriched["icuAvailable"] = enriched.get("icu_available", 0)
        enriched["icuOccupied"] = enriched.get("icu_occupied", 0)
        enriched["ventilatorsTotal"] = enriched.get("ventilators_total", 0)
        enriched["ventilatorsAvailable"] = enriched.get("ventilators_available", 0)
        enriched["oxygenStatus"] = enriched.get("oxygen_status", "unknown")
        enriched["emergencyReceivingStatus"] = enriched.get("emergency_receiving_status", "unknown")
        enriched["updatedAt"] = enriched.get("updated_at")

        # Honest provenance and telemetry metadata
        src = enriched.get("source")
        if not src or src == "hospital_admin_telemetry":
            src = "hospital_admin_reported" if enriched.get("updated_by") else "seeded_baseline"
        enriched["source"] = src

        # Compute dynamic freshness from updated_at timestamp
        updated_at_str = enriched.get("updated_at")
        is_fresh = True
        if updated_at_str:
            try:
                dt = datetime.fromisoformat(str(updated_at_str).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - dt
                if age.total_seconds() > 86400:  # Older than 24 hours
                    is_fresh = False
            except Exception:
                is_fresh = True

        # verified_realtime strictly False across baseline and admin-reported data
        enriched["verified_realtime"] = False

        if src == "seeded_baseline":
            enriched["freshness"] = "baseline"
        elif src == "hospital_admin_reported":
            enriched["freshness"] = "recent" if is_fresh else "stale"
        else:
            enriched["freshness"] = "recent" if is_fresh else "stale"

        # Department & equipment telemetry
        try:
            enriched["departments"] = self.hospital_repo.list_departments(h_id)
            enriched["departmentReadiness"] = enriched["departments"]
        except Exception:
            enriched["departments"] = []
            enriched["departmentReadiness"] = []

        try:
            enriched["equipment"] = self.hospital_repo.list_equipment(h_id)
            enriched["equipmentAvailability"] = enriched["equipment"]
        except Exception:
            enriched["equipment"] = []
            enriched["equipmentAvailability"] = []

        return enriched

    def get_live_capacity(self, hospital_id: Any) -> Dict[str, Any]:
        """
        Fetch current operational capacity snapshot for a facility.
        Returns verified database state with honest metadata markings.
        """
        canonical_id = to_canonical_hospital_id(hospital_id)
        hospital = self.hospital_repo.get_by_id(canonical_id)
        if not hospital:
            raise NotFoundException(f"Hospital with ID '{hospital_id}' does not exist.")

        raw_cap = self.capacity_repo.get_capacity(canonical_id)
        if not raw_cap:
            raise NotFoundException(f"Capacity record for hospital {hospital_id} not found.")

        return self._enrich_capacity_record(raw_cap, hospital_name=hospital.get("name"))

    def update_hospital_capacity(
        self,
        hospital_id: Any,
        capacity_data: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update live capacity metrics for a hospital.
        Validates non-negative values and mathematical balance constraints.
        Persists to database, records historical ledger snapshot, and logs audit event.
        """
        canonical_id = to_canonical_hospital_id(hospital_id)
        hospital = self.hospital_repo.get_by_id(canonical_id)
        if not hospital:
            raise NotFoundException(f"Hospital with ID '{hospital_id}' does not exist.")

        current = self.capacity_repo.get_capacity(canonical_id)
        if not current:
            raise NotFoundException(f"Capacity record for hospital {hospital_id} not found.")

        # Validate updates against current record
        is_valid, err_msg, cleaned = CapacityUpdateSchema.validate(
            capacity_data, current_record=current
        )
        if not is_valid:
            raise ValidationException(err_msg or "Invalid capacity update data.")

        user_id = user_context.get("id") if user_context else None
        reason = cleaned.pop("change_reason", None) or "hospital_admin_update"

        # Disallow client-supplied provenance tags (strictly server-assigned)
        for prov_field in ("source", "verified_realtime", "verifiedRealtime", "freshness"):
            cleaned.pop(prov_field, None)

        # Separate department & equipment updates
        departments = cleaned.pop("departments", None)
        equipment = cleaned.pop("equipment", None)

        persisted = self.capacity_repo.update_capacity(
            hospital_id=canonical_id,
            updates=cleaned,
            user_id=user_id,
            change_reason=reason,
        )

        # Log audit event
        self.audit_service.log_event(
            event_type="HOSPITAL_CAPACITY_UPDATED",
            actor_id=user_id or "hospital_admin",
            actor_role="hospital_admin",
            target_resource=f"hospital/{canonical_id}",
            details={
                "hospital_id": canonical_id,
                "updated_metrics": list(cleaned.keys()),
                "total_beds": persisted.get("total_beds"),
                "available_beds": persisted.get("available_beds"),
                "occupied_beds": persisted.get("occupied_beds"),
            },
        )

        logger.info(
            f"CapacityService: Successfully updated capacity for hospital {canonical_id} by {user_id}"
        )
        return self._enrich_capacity_record(persisted, hospital_name=hospital.get("name"))

    def allocate_provisional_hold(self, hospital_id: Any, request_id: str) -> bool:
        """
        Atomically allocate 1 provisional bed hold for an incoming emergency SOS.
        Reduces available beds by 1 and increases provisionally allocated beds by 1.
        Raises ConflictException if no capacity is available.
        """
        canonical_id = to_canonical_hospital_id(hospital_id)
        allocated = self.capacity_repo.allocate_hold(canonical_id)
        if not allocated:
            raise ConflictException(
                f"Cannot allocate emergency bed hold: Hospital {hospital_id} has zero available beds."
            )

        self.audit_service.log_event(
            event_type="EMERGENCY_HOLD_ALLOCATED",
            actor_id="system_dispatch",
            actor_role="system",
            target_resource=f"hospital/{canonical_id}",
            details={"request_id": request_id, "delta": -1},
        )
        return True

    def release_provisional_hold(
        self, hospital_id: Any, request_id: str, reason: str = "cancelled"
    ) -> bool:
        """
        Atomically release 1 provisional bed hold, restoring available bed capacity.
        """
        canonical_id = to_canonical_hospital_id(hospital_id)
        released = self.capacity_repo.release_hold(canonical_id, reason=reason)
        if released:
            self.audit_service.log_event(
                event_type="EMERGENCY_HOLD_RELEASED",
                actor_id="system_dispatch",
                actor_role="system",
                target_resource=f"hospital/{canonical_id}",
                details={"request_id": request_id, "reason": reason, "delta": +1},
            )
        return released

    def confirm_provisional_hold_arrival(self, hospital_id: Any, request_id: str) -> bool:
        """
        Atomically transition 1 provisional hold into an occupied bed upon casualty desk arrival.
        """
        canonical_id = to_canonical_hospital_id(hospital_id)
        confirmed = self.capacity_repo.confirm_arrival(canonical_id)
        if confirmed:
            self.audit_service.log_event(
                event_type="EMERGENCY_HOLD_CONFIRMED_ARRIVAL",
                actor_id=f"hospital/{canonical_id}",
                actor_role="hospital_casualty_desk",
                target_resource=f"hospital/{canonical_id}",
                details={"request_id": request_id},
            )
        return confirmed

    def list_capacity_history(self, hospital_id: Any, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve historical capacity snapshots for trend and SRI analysis."""
        canonical_id = to_canonical_hospital_id(hospital_id)
        return self.capacity_repo.list_history(canonical_id, limit=limit)
