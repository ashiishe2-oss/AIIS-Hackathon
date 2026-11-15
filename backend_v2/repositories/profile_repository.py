"""
AIIS Backend V2 - Profile Repository
====================================
Data access abstraction for user profiles and hospital authorization anchors.
Manages persistent records in Supabase 'profiles' table with local thread-safe
cache for development and testing resilience.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from threading import Lock
from backend_v2.extensions import supabase
from backend_v2.utils.exceptions import DatabaseException

logger = logging.getLogger("aiis.repositories.profile")


class ProfileRepository:
    """Repository handling database operations for user profiles."""

    # Thread-safe shared class-level store across repository instances
    _shared_profiles: Dict[str, Dict[str, Any]] = {}
    _lock = Lock()

    def __init__(self):
        self._supabase = supabase

    def create_profile(
        self,
        user_id: str,
        full_name: str,
        email: str,
        role: str = "patient",
        phone: Optional[str] = None,
        hospital_id: Optional[int] = None,
        account_status: str = "active",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new application profile linked to a Supabase user ID.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        # Ensure email is mirrored in metadata for forward/backward compatibility
        clean_email = email.strip().lower()
        meta = dict(metadata or {})
        meta["email"] = clean_email

        profile_data = {
            "id": str(user_id),
            "full_name": full_name,
            "email": clean_email,
            "phone": phone,
            "role": role,
            "hospital_id": hospital_id,
            "account_status": account_status,
            "metadata": meta,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        with self._lock:
            self._shared_profiles[str(user_id)] = profile_data

        # Sync to Supabase if configured
        client = self._supabase.get_admin_client() or self._supabase.get_client()
        if client:
            try:
                client.table("profiles").insert(profile_data).execute()
                logger.info(f"Profile for user {user_id} saved to Supabase.")
            except Exception as exc:
                err_msg = str(exc)
                if any(k in err_msg for k in ["PGRST204", "schema cache", "42703", "column profiles.email", "'email' column"]):
                    logger.warning(f"Remote profiles table lacks email column; falling back to metadata storage: {exc}")
                    try:
                        fallback_payload = {k: v for k, v in profile_data.items() if k != "email"}
                        client.table("profiles").insert(fallback_payload).execute()
                        logger.info(f"Profile for user {user_id} saved to Supabase with metadata email fallback.")
                    except Exception as inner_exc:
                        logger.error(f"Supabase profile creation failed on fallback: {inner_exc}")
                        if os.environ.get("FLASK_ENV") == "production":
                            raise DatabaseException(f"Failed to persist user profile to database: {inner_exc}")
                else:
                    logger.error(f"Supabase profile creation failed: {exc}")
                    if os.environ.get("FLASK_ENV") == "production":
                        raise DatabaseException(f"Failed to persist user profile to database: {exc}")

        return profile_data

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile by unique Supabase UUID."""
        uid = str(user_id)

        # 1. Check in-memory store
        with self._lock:
            if uid in self._shared_profiles:
                return dict(self._shared_profiles[uid])

        # 2. Check Supabase
        client = self._supabase.get_admin_client() or self._supabase.get_client()
        if client:
            try:
                res = client.table("profiles").select("*").eq("id", uid).execute()
                if res.data and len(res.data) > 0:
                    profile = res.data[0]
                    profile["email"] = profile.get("email") or (profile.get("metadata") or {}).get("email") or ""
                    with self._lock:
                        self._shared_profiles[uid] = profile
                    return profile
            except Exception as exc:
                logger.warning(f"Supabase get_by_id profile query failed: {exc}")

        return None

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Lookup profile by user email address."""
        clean_email = email.strip().lower()

        with self._lock:
            for p in self._shared_profiles.values():
                if p.get("email", "").lower() == clean_email or (p.get("metadata") or {}).get("email", "").lower() == clean_email:
                    return dict(p)

        client = self._supabase.get_admin_client() or self._supabase.get_client()
        if client:
            try:
                res = client.table("profiles").select("*").eq("email", clean_email).execute()
                if res.data and len(res.data) > 0:
                    profile = res.data[0]
                    profile["email"] = profile.get("email") or clean_email
                    with self._lock:
                        self._shared_profiles[str(profile["id"])] = profile
                    return profile
            except Exception as exc:
                err_msg = str(exc)
                if any(k in err_msg for k in ["PGRST204", "schema cache", "42703", "column profiles.email", "'email' column"]):
                    # Fall back to querying inside JSONB metadata
                    try:
                        res = client.table("profiles").select("*").filter("metadata->>email", "eq", clean_email).execute()
                        if res.data and len(res.data) > 0:
                            profile = res.data[0]
                            profile["email"] = clean_email
                            with self._lock:
                                self._shared_profiles[str(profile["id"])] = profile
                            return profile
                    except Exception as inner_exc:
                        logger.warning(f"Supabase get_by_email metadata fallback query failed: {inner_exc}")
                else:
                    logger.warning(f"Supabase get_by_email query failed: {exc}")

        return None

    def update_profile(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update permitted profile attributes."""
        uid = str(user_id)
        record = self.get_by_id(uid)
        if not record:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        sanitized_updates = {
            k: v for k, v in updates.items()
            if k not in {"id", "created_at"}
        }
        sanitized_updates["updated_at"] = now_iso

        with self._lock:
            record.update(sanitized_updates)
            self._shared_profiles[uid] = record

        client = self._supabase.get_admin_client() or self._supabase.get_client()
        if client:
            try:
                client.table("profiles").update(sanitized_updates).eq("id", uid).execute()
            except Exception as exc:
                logger.error(f"Supabase profile update failed: {exc}")
                if os.environ.get("FLASK_ENV") == "production":
                    raise DatabaseException(f"Failed to update profile in database: {exc}")

        return record
