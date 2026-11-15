"""
AIIS Backend V2 - Hospital Service
==================================
Business operations for public hospital discovery, filtering,
proximity geolocation calculations, and operational department readiness.
Enforces honest data classification: labels baseline capacity as 'seeded_baseline'.
"""

import math
import logging
from typing import Dict, Any, List, Optional
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.utils.exceptions import NotFoundException

logger = logging.getLogger("aiis.services.hospital")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    R = 6371.0
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


class HospitalService:
    """Service handling hospital search, department discovery, and facility profiles."""

    def __init__(self, hospital_repo: Optional[HospitalRepository] = None):
        self.hospital_repo = hospital_repo or HospitalRepository()

    def search_hospitals(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Search and filter hospitals with optional geolocation proximity and pagination.
        Enforces honest capacity metadata labeling.
        """
        filters = filters or {}
        raw_hospitals = self.hospital_repo.list_all()

        matching: List[Dict[str, Any]] = []

        target_city = str(filters.get("city", "")).strip().lower()
        search_term = str(filters.get("search", "")).strip().lower()
        target_dept = str(filters.get("department", "")).strip().lower()
        target_spec = str(filters.get("specialty", "")).strip().lower()

        user_lat = filters.get("latitude")
        user_lon = filters.get("longitude")
        radius_km = filters.get("radius")

        # Known clinical disciplines standardly offered by Multi-Specialty public hospitals
        known_multi_specialties = {
            "cardiology", "emergency", "casualty", "general medicine", "medicine",
            "icu", "intensive care", "paediatrics", "pediatrics", "radiology",
            "imaging", "surgery", "orthopaedics", "orthopedics", "neurology",
            "oncology", "gynaecology", "gynecology", "obstetrics", "dermatology",
            "ent", "ophthalmology", "nephrology", "pulmonology", "urology",
        }

        for h in raw_hospitals:
            h_name = str(h.get("name", "")).lower()
            h_city = str(h.get("city", "")).lower()
            h_addr = str(h.get("address", "")).lower()
            h_spec = str(h.get("specialty", "")).lower()

            # City filter
            if target_city and target_city not in h_city:
                continue

            # Text search filter
            if search_term and (search_term not in h_name and search_term not in h_addr and search_term not in h_city and search_term not in h_spec):
                continue

            # Specialty hospitals only match their own specialty
            scope = h.get("emergencyScope") or "general"
            scope_spec = {"cardiac": "cardiology", "neuro": "neurology", "trauma": "orthopaedics",
                          "children": "paediatrics", "maternity": "obstetrics gynaecology", "eye": "ophthalmology"}.get(scope)
            if scope_spec:
                h_spec = scope_spec

            # Specialty / Department filter
            if target_spec:
                is_multi = "multi" in h_spec
                matches_direct = target_spec in h_spec
                matches_multi = is_multi and any(target_spec in s or s in target_spec for s in known_multi_specialties)
                if not (matches_direct or matches_multi):
                    continue

            if target_dept:
                is_multi = "multi" in h_spec
                matches_direct = target_dept in h_spec
                matches_multi = is_multi and any(target_dept in s or s in target_dept for s in known_multi_specialties)
                if not (matches_direct or matches_multi):
                    continue

            # Geolocation proximity filter
            dist = None
            if user_lat is not None and user_lon is not None:
                h_lat = float(h.get("lat") or h.get("latitude") or 0.0)
                h_lon = float(h.get("lon") or h.get("longitude") or 0.0)
                if h_lat != 0.0 or h_lon != 0.0:
                    dist = haversine_km(user_lat, user_lon, h_lat, h_lon)
                    if radius_km is not None and dist > radius_km:
                        continue

            item = dict(h)
            if dist is not None:
                item["distance_km"] = round(dist, 1)
                item["distanceKm"] = round(dist, 1)
                item["transitMins"] = max(3, int(round(dist * 1.35 / 20.0 * 60.0 + 3)))

            # Honest capacity classification
            item["capacity_metadata"] = {
                "source": "seeded_baseline",
                "verified_realtime": False,
                "freshness": "baseline",
            }
            matching.append(item)

        # Sort by distance if geolocation was provided, else by rating
        if user_lat is not None and user_lon is not None:
            matching.sort(key=lambda x: x.get("distance_km", 99999.0))
        else:
            matching.sort(key=lambda x: float(x.get("rating") or 4.0), reverse=True)

        # Pagination
        total = len(matching)
        page = int(filters.get("page", 1))
        limit = int(filters.get("limit", 20))
        total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1

        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_items = matching[start_idx:end_idx]

        return {
            "items": paginated_items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": total_pages,
            "capacity_source": "seeded_baseline",
            "verified_realtime": False,
        }

    def get_hospital_details(self, hospital_id: int) -> Dict[str, Any]:
        """
        Retrieve complete hospital profile including departments, equipment,
        and verified clinical capabilities.
        """
        hospital = self.hospital_repo.get_by_id(hospital_id)
        if not hospital:
            raise NotFoundException(f"Hospital with ID {hospital_id} does not exist.")

        departments = self.hospital_repo.list_departments(hospital_id)
        equipment = self.hospital_repo.list_equipment(hospital_id)
        capabilities = self.hospital_repo.list_capabilities(hospital_id)

        profile = dict(hospital)
        profile["departments"] = departments
        profile["equipment"] = equipment
        profile["capabilities"] = capabilities
        profile["capacity_metadata"] = {
            "source": "seeded_baseline",
            "verified_realtime": False,
            "freshness": "baseline",
        }
        return profile

    def get_departments(self, hospital_id: Optional[int] = None) -> List[Any]:
        """Retrieve departments for a specific facility or distinct network list."""
        if hospital_id is not None:
            hosp = self.hospital_repo.get_by_id(hospital_id)
            if not hosp:
                raise NotFoundException(f"Hospital with ID {hospital_id} does not exist.")
            return self.hospital_repo.list_departments(hospital_id)
        return self.hospital_repo.get_distinct_departments()

    def get_locations(self) -> List[Dict[str, Any]]:
        """Return city centers with representative coordinates."""
        return self.hospital_repo.get_locations()
