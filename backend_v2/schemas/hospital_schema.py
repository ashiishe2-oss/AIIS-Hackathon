"""
AIIS Backend V2 - Hospital Schemas
==================================
Data structures and validation for hospital discovery queries,
filtering, geolocation search, planned healthcare search, and pagination.
"""

import re
from typing import Optional, Dict, Any, Tuple
from backend_v2.utils.hospital_id_adapter import to_canonical_hospital_id
from backend_v2.utils.exceptions import ValidationException


class HospitalFilterSchema:
    """Filter parameters for querying hospitals in the public directory."""

    @staticmethod
    def validate(params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate and parse query parameters for hospital discovery.
        Returns (is_valid, error_message, cleaned_params).
        """
        if not isinstance(params, dict):
            return False, "Query parameters must be a dictionary.", {}

        cleaned = {}

        # city filter
        if params.get("city"):
            cleaned["city"] = str(params["city"]).strip()

        # generic text search (name, address, specialty)
        if params.get("search"):
            cleaned["search"] = str(params["search"]).strip()

        # department filter
        if params.get("department"):
            cleaned["department"] = str(params["department"]).strip()

        # specialty filter
        if params.get("specialty"):
            cleaned["specialty"] = str(params["specialty"]).strip()

        # Geolocation search
        lat_raw = params.get("latitude") or params.get("lat")
        lon_raw = params.get("longitude") or params.get("lon") or params.get("lng")
        if lat_raw is not None or lon_raw is not None:
            if lat_raw is None or lon_raw is None:
                return False, "Both latitude and longitude are required for geolocation search.", {}
            try:
                lat = float(lat_raw)
                lon = float(lon_raw)
                if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                    return False, "Latitude must be between -90 and 90, Longitude between -180 and 180.", {}
                cleaned["latitude"] = lat
                cleaned["longitude"] = lon
            except (ValueError, TypeError):
                return False, "Latitude and longitude must be valid floating-point numbers.", {}

        # radius filter in km (optional, default 50km if lat/lon provided)
        if params.get("radius"):
            try:
                rad = float(params["radius"])
                if rad <= 0:
                    return False, "Radius must be a positive number.", {}
                cleaned["radius"] = rad
            except (ValueError, TypeError):
                return False, "Radius must be a valid number.", {}
        elif "latitude" in cleaned:
            cleaned["radius"] = 50.0

        # pagination
        page = params.get("page", 1)
        limit = params.get("limit", 20)
        try:
            p = int(page)
            if p < 1:
                return False, "Page must be an integer >= 1.", {}
            cleaned["page"] = p
        except (ValueError, TypeError):
            return False, "Page must be a valid integer.", {}

        try:
            lim = int(limit)
            if lim < 1 or lim > 100:
                return False, "Limit must be an integer between 1 and 100.", {}
            cleaned["limit"] = lim
        except (ValueError, TypeError):
            return False, "Limit must be a valid integer.", {}

        return True, None, cleaned


class PlannedSearchSchema:
    """Filter parameters for planned healthcare discovery (POST /api/planned/search)."""

    @staticmethod
    def validate(params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate and parse parameters for planned healthcare search.
        Returns (is_valid, error_message, cleaned_params).
        """
        if not isinstance(params, dict):
            return False, "Search payload must be a JSON object.", {}

        cleaned = {}

        # 1. Specialty / Department filter
        specialty = params.get("specialty") if params.get("specialty") is not None else params.get("department")
        if specialty is not None and str(specialty).strip():
            if not isinstance(specialty, str):
                return False, "specialty must be a non-empty string.", {}
            clean_spec = specialty.strip()
            if len(clean_spec) < 3 or len(clean_spec) > 128:
                return False, "specialty must be between 3 and 128 characters.", {}
            # Reject invalid specialty strings with non-alphabetic/invalid characters
            if not re.match(r"^[a-zA-Z\s&\-/]+$", clean_spec) or clean_spec.lower() in {
                "invalid",
                "invalid_specialty",
                "unknown",
                "null",
                "none",
                "test",
            }:
                return False, f"Invalid clinical specialty: '{clean_spec}'. Expected medical department or specialty discipline.", {}
            cleaned["specialty"] = clean_spec
            cleaned["department"] = clean_spec

        # 2. Hospital filter (by ID, code, or name)
        hosp = (
            params.get("hospital")
            or params.get("hospital_name")
            or params.get("hospital_id")
            or params.get("hospitalId")
        )
        if hosp is not None:
            hosp_str = str(hosp).strip()
            if not hosp_str:
                return False, "hospital cannot be empty.", {}
            try:
                canonical_id = to_canonical_hospital_id(hosp)
                cleaned["hospital_id"] = canonical_id
            except ValidationException:
                # Treat as text search query
                cleaned["search"] = hosp_str

        # 3. Generic search text
        if params.get("search") and "search" not in cleaned:
            cleaned["search"] = str(params["search"]).strip()

        # 4. City / Area filter
        city = (
            params.get("city")
            or params.get("area")
            or params.get("location")
            or params.get("locationName")
        )
        if city is not None:
            city_str = str(city).strip()
            if city_str:
                cleaned["city"] = city_str

        # 5. Geolocation proximity search
        lat_raw = params.get("latitude") if params.get("latitude") is not None else params.get("lat")
        lon_raw = params.get("longitude") if params.get("longitude") is not None else (
            params.get("lon") if params.get("lon") is not None else params.get("lng")
        )
        if lat_raw is not None or lon_raw is not None:
            if lat_raw is None or lon_raw is None:
                return False, "Both latitude and longitude are required for geolocation search.", {}
            try:
                lat = float(lat_raw)
                lon = float(lon_raw)
                if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                    return False, "Latitude must be between -90 and 90, Longitude between -180 and 180.", {}
                cleaned["latitude"] = lat
                cleaned["longitude"] = lon
            except (ValueError, TypeError):
                return False, "Latitude and longitude must be valid floating-point numbers.", {}

        # 6. Radius filter
        rad_raw = params.get("radius") or params.get("radius_km")
        if rad_raw is not None:
            try:
                rad = float(rad_raw)
                if rad <= 0:
                    return False, "Radius must be a positive number.", {}
                cleaned["radius"] = rad
            except (ValueError, TypeError):
                return False, "Radius must be a valid number.", {}
        elif "latitude" in cleaned:
            cleaned["radius"] = 50.0

        # 7. Pagination
        page = params.get("page", 1)
        limit = params.get("limit", 20)
        try:
            p = int(page)
            if p < 1:
                return False, "Page must be an integer >= 1.", {}
            cleaned["page"] = p
        except (ValueError, TypeError):
            return False, "Page must be a valid integer.", {}

        try:
            lim = int(limit)
            if lim < 1 or lim > 100:
                return False, "Limit must be an integer between 1 and 100.", {}
            cleaned["limit"] = lim
        except (ValueError, TypeError):
            return False, "Limit must be a valid integer.", {}

        return True, None, cleaned
