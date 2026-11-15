"""
AIIS Backend V2 - Appointment Repository
========================================
Data access abstraction for outpatient consultation appointments.
Persists to Supabase 'public.appointments' table with shared thread-safe
in-memory caching across repository instances for fallback reliability.
"""

import os
import threading
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from backend_v2.extensions import supabase
from backend_v2.utils.exceptions import DatabaseException

logger = logging.getLogger("aiis.repositories.appointment")


class AppointmentRepository:
    """Repository handling database operations for outpatient appointments."""

    _shared_store: Dict[str, Dict[str, Any]] = {}
    _lock = threading.Lock()

    def __init__(self):
        self._supabase = supabase
        self._in_memory_store = AppointmentRepository._shared_store

    def create(self, appointment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new appointment record.
        Persists to Supabase if available; always writes to shared thread-safe memory store.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        record = {
            "id": appointment_data["id"],
            "hospital_id": int(appointment_data["hospital_id"]),
            "patient_id": str(appointment_data["patient_id"]) if appointment_data.get("patient_id") else None,
            "patient_name": str(appointment_data["patient_name"]).strip(),
            "patient_phone": str(appointment_data["patient_phone"]).strip(),
            "patient_age": str(appointment_data.get("patient_age") or "").strip() or None,
            "specialty": str(appointment_data["specialty"]).strip(),
            "preferred_date": str(appointment_data["preferred_date"]).strip(),
            "preferred_time_slot": str(appointment_data["preferred_time_slot"]).strip(),
            "notes": str(appointment_data.get("notes") or "").strip() or None,
            "status": str(appointment_data.get("status") or "REQUESTED").strip().upper(),
            "created_at": appointment_data.get("created_at") or now_ts,
            "updated_at": appointment_data.get("updated_at") or now_ts,
        }

        # Cache in memory
        with self._lock:
            self._in_memory_store[record["id"]] = record.copy()

        client = self._supabase.get_client()
        if client:
            try:
                db_payload = {k: v for k, v in record.items() if v is not None}
                res = client.table("appointments").insert(db_payload).execute()
                if res.data and len(res.data) > 0:
                    created_row = res.data[0]
                    with self._lock:
                        self._in_memory_store[created_row["id"]] = created_row
                    logger.info(f"Persisted appointment '{created_row['id']}' to Supabase.")
                    return created_row
            except Exception as exc:
                logger.error(f"Supabase appointment insert failed: {exc}")
                if os.environ.get("FLASK_ENV") == "production":
                    raise DatabaseException(f"Failed to persist appointment to database: {exc}")
                logger.warning(f"Retaining in-memory record for local testing.")

        return record

    def get_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an appointment by its unique ID."""
        clean_id = str(appointment_id).strip()

        # Check memory first
        with self._lock:
            if clean_id in self._in_memory_store:
                return self._in_memory_store[clean_id].copy()

        client = self._supabase.get_client()
        if client:
            try:
                res = client.table("appointments").select("*").eq("id", clean_id).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    with self._lock:
                        self._in_memory_store[clean_id] = row
                    return row
            except Exception as exc:
                logger.warning(f"Supabase get_by_id failed for appointment {clean_id}: {exc}")

        return None

    def list_by_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        """List all appointments booked by a specific patient."""
        clean_patient_id = str(patient_id).strip()
        results: List[Dict[str, Any]] = []

        client = self._supabase.get_client()
        if client:
            try:
                res = (
                    client.table("appointments")
                    .select("*")
                    .eq("patient_id", clean_patient_id)
                    .order("created_at", desc=True)
                    .execute()
                )
                if res.data:
                    for row in res.data:
                        with self._lock:
                            self._in_memory_store[row["id"]] = row
                    return res.data
            except Exception as exc:
                logger.warning(f"Supabase list_by_patient failed: {exc}")

        # Fallback to memory
        with self._lock:
            for apt in self._in_memory_store.values():
                if str(apt.get("patient_id")) == clean_patient_id:
                    results.append(apt.copy())

        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def list_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """List appointments matching patient phone number."""
        clean_phone = "".join(filter(str.isdigit, str(phone)))
        if not clean_phone:
            return []
        results: List[Dict[str, Any]] = []

        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("appointments").select("*")
                response = query.execute()
                for row in (response.data or []):
                    r_ph = "".join(filter(str.isdigit, str(row.get("patient_phone") or "")))
                    if r_ph and (r_ph.endswith(clean_phone[-8:]) or clean_phone.endswith(r_ph[-8:])):
                        results.append(row)
                if results:
                    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                    return results
            except Exception as exc:
                logger.warning(f"Remote appointment search by phone failed, using memory store: {exc}")

        with self._lock:
            for apt in self._in_memory_store.values():
                apt_ph = "".join(filter(str.isdigit, str(apt.get("patient_phone") or apt.get("patientPhone") or "")))
                if apt_ph and (apt_ph.endswith(clean_phone[-8:]) or clean_phone.endswith(apt_ph[-8:])):
                    results.append(apt.copy())

        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def list_by_hospital(self, hospital_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List appointments for a specific hospital with optional status filter."""
        h_id = int(hospital_id)
        results: List[Dict[str, Any]] = []

        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("appointments").select("*").eq("hospital_id", h_id)
                if status:
                    query = query.eq("status", str(status).strip().upper())
                res = query.order("created_at", desc=True).execute()
                if res.data:
                    for row in res.data:
                        with self._lock:
                            self._in_memory_store[row["id"]] = row
                    return res.data
            except Exception as exc:
                logger.warning(f"Supabase list_by_hospital failed: {exc}")

        # Fallback to memory
        clean_status = str(status).strip().upper() if status else None
        with self._lock:
            for apt in self._in_memory_store.values():
                if int(apt.get("hospital_id", 0)) == h_id:
                    if clean_status is None or apt.get("status") == clean_status:
                        results.append(apt.copy())

        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def list_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """List appointments matching patient phone number."""
        clean_phone = "".join(filter(str.isdigit, str(phone)))
        if not clean_phone:
            return []
        results: List[Dict[str, Any]] = []

        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("appointments").select("*")
                response = query.execute()
                for row in (response.data or []):
                    r_ph = "".join(filter(str.isdigit, str(row.get("patient_phone") or "")))
                    if r_ph and (r_ph.endswith(clean_phone[-8:]) or clean_phone.endswith(r_ph[-8:])):
                        results.append(row)
                if results:
                    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                    return results
            except Exception as exc:
                logger.warning(f"Remote appointment search by phone failed, using memory store: {exc}")

        with self._lock:
            for apt in self._in_memory_store.values():
                apt_ph = "".join(filter(str.isdigit, str(apt.get("patient_phone") or apt.get("patientPhone") or "")))
                if apt_ph and (apt_ph.endswith(clean_phone[-8:]) or clean_phone.endswith(apt_ph[-8:])):
                    results.append(apt.copy())

        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def update_status(self, appointment_id: str, new_status: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update appointment lifecycle status."""
        clean_id = str(appointment_id).strip()
        status_norm = str(new_status).strip().upper()
        now_ts = datetime.now(timezone.utc).isoformat()

        record = self.get_by_id(clean_id)
        if not record:
            return None

        record["status"] = status_norm
        record["updated_at"] = now_ts
        if notes:
            record["notes"] = str(notes).strip()

        with self._lock:
            self._in_memory_store[clean_id] = record.copy()

        client = self._supabase.get_client()
        if client:
            try:
                update_payload = {"status": status_norm, "updated_at": now_ts}
                if notes:
                    update_payload["notes"] = str(notes).strip()
                res = client.table("appointments").update(update_payload).eq("id", clean_id).execute()
                if res.data and len(res.data) > 0:
                    with self._lock:
                        self._in_memory_store[clean_id] = res.data[0]
                    return res.data[0]
            except Exception as exc:
                logger.error(f"Supabase update_status failed for appointment {clean_id}: {exc}")
                if os.environ.get("FLASK_ENV") == "production":
                    raise DatabaseException(f"Failed to update appointment status in database: {exc}")

        return record

