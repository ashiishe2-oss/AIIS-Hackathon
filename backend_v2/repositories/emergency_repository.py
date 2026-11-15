"""
AIIS Backend V2 - Emergency Repository
======================================
Data access abstraction for patient emergency SOS records and dispatch tracking.
Persists records to Supabase 'emergency_requests' table with a thread-safe
in-memory cache for offline/testing robustness.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from threading import Lock
from backend_v2.extensions import supabase
from backend_v2.utils.exceptions import DatabaseException

logger = logging.getLogger("aiis.repositories.emergency")


# Database check constraint mapper for emergency_category column
_CATEGORY_DB_MAP = {
    "general": "other_unsure",
    "cardiac": "cardiac",
    "stroke": "stroke_neuro",
    "stroke_neuro": "stroke_neuro",
    "trauma": "trauma",
    "breathing": "breathing",
    "child": "paediatric",
    "paediatric": "paediatric",
    "burns": "trauma",
    "other": "other_unsure",
    "other_unsure": "other_unsure",
}

# Status mapping between frontend domain model and Postgres check constraint
_STATUS_TO_DB = {
    "PATIENT_ARRIVED": "completed",
    "CANCELLED": "cancelled",
    "EXPIRED": "expired",
    "REQUEST_SUBMITTED": "REQUEST_SUBMITTED",
}

_STATUS_FROM_DB = {
    "completed": "PATIENT_ARRIVED",
    "cancelled": "CANCELLED",
    "expired": "EXPIRED",
}


class EmergencyRepository:
    """Repository handling persistence for emergency SOS records."""

    _shared_requests: Dict[str, Dict[str, Any]] = {}
    _shared_lock: Lock = Lock()

    def __init__(self):
        self._supabase = supabase
        self._lock = EmergencyRepository._shared_lock
        # Thread-safe in-memory store shared across all repository instances
        self._in_memory_requests = EmergencyRepository._shared_requests

    def create_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist a new emergency SOS request.
        """
        request_id = data.get("id")
        now_iso = datetime.now(timezone.utc).isoformat()
        record = {
            **data,
            "created_at": data.get("created_at", now_iso),
            "updated_at": now_iso,
        }

        # 1. Update in-memory store
        with self._lock:
            self._in_memory_requests[str(request_id)] = record

        # 2. Persist to Supabase if configured
        client = self._supabase.get_client()
        if client:
            try:
                raw_cat = str(
                    record.get("emergency_category") or record.get("emergencyCategory") or "other_unsure"
                ).strip().lower()
                db_cat = _CATEGORY_DB_MAP.get(raw_cat, "other_unsure")

                # Convert camelCase to snake_case for Supabase if needed
                supabase_row = {
                    "id": str(request_id),
                    "hospital_id": record.get("hospital_id") or record.get("hospitalId"),
                    "target_hospital_id": record.get("hospital_id") or record.get("hospitalId"),
                    "emergency_category": db_cat,
                    "patient_name": record.get("patient_name") or record.get("patientName"),
                    "companion_name": record.get("companion_name") or record.get("companionName"),
                    "contact_phone": record.get("contact_phone") or record.get("contactPhone"),
                    "estimated_travel_minutes": record.get("estimated_travel_minutes") or record.get("estimatedTravelMinutes", 15),
                    "user_location_name": record.get("user_location_name") or record.get("userLocationName"),
                    "status": record.get("status", "REQUEST_SUBMITTED"),
                    "otp": str(record.get("otp", "")),
                    "notes": record.get("notes"),
                    "tracking_token_hash": record.get("tracking_token_hash") or record.get("guest_token_hash"),
                    "hold_expires_at": record.get("hold_expires_at") or record.get("holdExpiresAt"),
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                }
                client.table("emergency_requests").insert(supabase_row).execute()
                logger.info(f"Emergency SOS record {request_id} synced to Supabase.")
            except Exception as exc:
                logger.error(f"Supabase emergency_requests insert failed: {exc}")
                if os.environ.get("FLASK_ENV") == "production":
                    raise DatabaseException(f"Failed to persist emergency request to database: {exc}")

        return record

    def get_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an emergency SOS request by its unique identifier."""
        req_id_str = str(request_id)

        # 1. Check in-memory store first
        with self._lock:
            if req_id_str in self._in_memory_requests:
                return dict(self._in_memory_requests[req_id_str])

        # 2. Check Supabase
        client = self._supabase.get_client()
        if client:
            try:
                res = client.table("emergency_requests").select("*").eq("id", req_id_str).execute()
                if res.data and len(res.data) > 0:
                    row = dict(res.data[0])
                    if "tracking_token_hash" in row and not row.get("guest_token_hash"):
                        row["guest_token_hash"] = row["tracking_token_hash"]
                    if row.get("status") in _STATUS_FROM_DB:
                        row["status"] = _STATUS_FROM_DB[row["status"]]
                    with self._lock:
                        self._in_memory_requests[req_id_str] = row
                    return row
            except Exception as exc:
                logger.warning(f"Supabase emergency get_by_id failed: {exc}")

        return None

    def update_status(
        self,
        request_id: str,
        status: str,
        cancellation_reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update the lifecycle status of an emergency request."""
        req_id_str = str(request_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        record = self.get_by_id(req_id_str)
        if not record:
            return None

        with self._lock:
            record["status"] = status
            record["updated_at"] = now_iso
            if cancellation_reason:
                record["cancellation_reason"] = cancellation_reason
            self._in_memory_requests[req_id_str] = record

        # Sync to Supabase
        client = self._supabase.get_client()
        if client:
            try:
                db_status = _STATUS_TO_DB.get(status, status)
                update_payload = {"status": db_status, "updated_at": now_iso}
                if cancellation_reason:
                    update_payload["cancellation_reason"] = cancellation_reason
                client.table("emergency_requests").update(update_payload).eq("id", req_id_str).execute()
            except Exception as exc:
                logger.error(f"Supabase update_status failed: {exc}")
                if os.environ.get("FLASK_ENV") == "production":
                    raise DatabaseException(f"Failed to update emergency request in database: {exc}")

        return record

    def list_active(self) -> List[Dict[str, Any]]:
        """List active requests (REQUEST_SUBMITTED, HOSPITAL_ACCEPTED)."""
        active_statuses = {"REQUEST_SUBMITTED", "AWAITING_HOSPITAL_RESPONSE", "HOSPITAL_ACCEPTED"}
        with self._lock:
            return [
                r for r in self._in_memory_requests.values()
                if r.get("status") in active_statuses
            ]

    def list_by_hospital(self, hospital_id: int) -> List[Dict[str, Any]]:
        """List recent emergency requests assigned to a hospital."""
        h_requests: List[Dict[str, Any]] = []
        with self._lock:
            for r in self._in_memory_requests.values():
                r_hid = r.get("hospital_id") if r.get("hospital_id") is not None else r.get("hospitalId")
                h_match = (
                    r_hid == hospital_id
                    or str(r_hid) == str(hospital_id)
                    or str(r_hid) == f"hsp-{int(hospital_id):03d}"
                    or r.get("target_hospital_id") == hospital_id
                )
                if h_match:
                    h_requests.append(dict(r))

        client = self._supabase.get_client()
        if client:
            try:
                res = (
                    client.table("emergency_requests")
                    .select("*")
                    .or_(f"hospital_id.eq.{hospital_id},target_hospital_id.eq.{hospital_id}")
                    .order("created_at", desc=True)
                    .limit(20)
                    .execute()
                )
                if res.data:
                    for row in res.data:
                        db_st = row.get("status")
                        row["status"] = _STATUS_FROM_DB.get(db_st, db_st)
                        if not any(x.get("id") == row.get("id") for x in h_requests):
                            h_requests.append(row)
            except Exception as exc:
                logger.warning(f"Failed to query Supabase emergency_requests for hospital {hospital_id}: {exc}")

        h_requests.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return h_requests
