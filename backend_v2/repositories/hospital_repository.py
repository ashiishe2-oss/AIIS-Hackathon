"""
AIIS Backend V2 - Hospital Repository
=====================================
Data access abstraction for hospitals and infrastructure capacity records.
Interacts with Supabase 'hospitals' table with fallback to verified local dataset.
"""

import os
import csv
import logging
from typing import Optional, Dict, Any, List
from backend_v2.extensions import supabase
from backend_v2.utils.hospital_directory import (
    apply_verified,
    directory_record,
    directory_records,
    is_directory_only,
    is_hidden,
)

logger = logging.getLogger("aiis.repositories.hospital")


class HospitalRepository:
    """Repository handling database operations for hospitals."""

    def __init__(self, data_csv_path: Optional[str] = None):
        self._supabase = supabase
        self._csv_path = data_csv_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "hospitals.csv",
        )
        self._cached_hospitals: Optional[List[Dict[str, Any]]] = None

    def _load_from_csv(self) -> List[Dict[str, Any]]:
        """Load and normalize hospital records from the local CSV file."""
        if self._cached_hospitals is not None:
            return self._cached_hospitals

        hospitals: List[Dict[str, Any]] = []
        if not os.path.exists(self._csv_path):
            logger.warning(f"Hospital CSV file not found at {self._csv_path}")
            return []

        try:
            with open(self._csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        h_id = int(row.get("id", 0))
                        lat = float(row.get("lat", 0.0))
                        lon = float(row.get("lon", 0.0))
                        num_beds = int(row.get("num_beds") or 100)
                        icu_beds = int(row.get("icu_beds") or 10)
                        ventilators = int(row.get("ventilators") or 5)

                        # Available beds approximation for realistic readiness
                        avail_er = max(2, int(num_beds * 0.15))
                        avail_icu = max(1, int(icu_beds * 0.20))

                        hospitals.append({
                            "id": h_id,
                            "name": str(row.get("name", "Public Hospital")).strip(),
                            "city": str(row.get("city", "Bengaluru")).strip(),
                            "district": str(row.get("district", "Bengaluru Urban")).strip(),
                            "specialty": str(row.get("specialty", "Multi-Specialty")).strip(),
                            "lat": lat,
                            "lon": lon,
                            "coordinates": {"latitude": lat, "longitude": lon},
                            "address": str(row.get("address", "")).strip(),
                            "phone": None,
                            "emergencyPhone": None,
                            "receptionPhone": None,
                            "num_beds": num_beds,
                            "icu_beds": icu_beds,
                            "ventilators": ventilators,
                            "num_doctors": int(row.get("num_doctors") or 25),
                            "avg_wait_time": int(row.get("avg_wait_time") or 20),
                            "rating": float(row.get("rating") or 4.0),
                            "score": float(row.get("score") or 50.0),
                            "capacity": {
                                "emergencyBeds": {"total": num_beds, "available": avail_er},
                                "icuBeds": {"total": icu_beds, "available": avail_icu},
                                "ventilators": {"total": ventilators, "available": max(1, int(ventilators * 0.3))},
                            },
                            "emergencyFacilities": ["24/7 Casualty"],
                            "sector": "Government",
                            "dataFreshness": {"lastUpdated": None, "source": "seeded_baseline (demo values)", "isSimulated": True},
                        })
                    except (ValueError, KeyError) as parse_err:
                        logger.debug(f"Skipping malformed hospital row: {parse_err}")
                        continue

            self._cached_hospitals = hospitals
            logger.info(f"Loaded {len(hospitals)} hospital records from CSV.")
        except Exception as exc:
            logger.error(f"Error reading hospital CSV: {exc}")
            return []

        return self._cached_hospitals

    @staticmethod
    def _normalize_db_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Supabase hospitals row (+ hospital_capacity) for the API."""
        lat = float(row.get("latitude") or row.get("lat") or 0.0)
        lon = float(row.get("longitude") or row.get("lon") or 0.0)
        cap_data = row.get("hospital_capacity") or {}
        if isinstance(cap_data, list):
            cap_data = cap_data[0] if cap_data else {}

        capacity = None
        freshness = {"lastUpdated": None, "source": "No capacity record", "isSimulated": False}
        if cap_data:
            capacity = {
                "emergencyBeds": {"total": cap_data.get("total_beds"), "available": cap_data.get("available_beds")},
                "icuBeds": {"total": cap_data.get("icu_total"), "available": cap_data.get("icu_available")},
                "ventilators": {"total": cap_data.get("ventilators_total"), "available": cap_data.get("ventilators_available")},
                "provisionalHolds": cap_data.get("provisionally_allocated_beds"),
            }
            reported = bool(cap_data.get("updated_by"))
            freshness = {
                "lastUpdated": cap_data.get("updated_at"),
                # Seeded baseline numbers are sample values until a hospital admin updates them.
                "source": "hospital_admin_reported" if reported else "seeded_baseline (demo values)",
                "isSimulated": not reported,
            }

        phone = row.get("emergency_phone") or row.get("contact_number")
        return {
            **row,
            "lat": lat,
            "lon": lon,
            "coordinates": {"latitude": lat, "longitude": lon},
            "phone": phone,
            "emergencyPhone": phone,
            "receptionPhone": row.get("contact_number") or phone,
            "specialty": row.get("specialty") or "Multi-Specialty Public Hospital",
            "sector": row.get("sector") or "Government",
            "num_beds": (cap_data or {}).get("total_beds"),
            "icu_beds": (cap_data or {}).get("icu_total"),
            "ventilators": (cap_data or {}).get("ventilators_total"),
            "capacity": capacity,
            "dataFreshness": freshness,
            "emergencyFacilities": ["24/7 Casualty"],
        }

    def _finish(self, records: List[Dict[str, Any]], city: Optional[str] = None) -> List[Dict[str, Any]]:
        """Apply verified locations/phones, drop duplicate or unverifiable rows, add directory hospitals."""
        out = [apply_verified(r) for r in records if not is_hidden(r.get("id"))]
        known = {str(r.get("id")) for r in out}
        out += [d for d in directory_records(city) if str(d["id"]) not in known]
        return out

    def list_all(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Query all hospitals with optional filtering.
        Attempts Supabase query first if configured; falls back to local dataset.
        Every record gets the verified location and phone overlay.
        """
        city = (filters or {}).get("city")
        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("hospitals").select("*, hospital_capacity(*)")
                if city:
                    query = query.ilike("city", f"%{city}%")
                response = query.execute()
                if response.data and len(response.data) > 0:
                    normalized = [self._normalize_db_row(row) for row in response.data]
                    logger.info(f"Retrieved {len(normalized)} hospitals from Supabase.")
                    return self._finish(normalized, city)
            except Exception as exc:
                logger.warning(f"Supabase query failed, falling back to local dataset: {exc}")

        # Fallback to local dataset
        records = [dict(r) for r in self._load_from_csv()]
        if filters and filters.get("city"):
            target_city = str(filters["city"]).strip().lower()
            records = [h for h in records if target_city in h["city"].lower()]
        if filters and filters.get("specialty"):
            target_spec = str(filters["specialty"]).strip().lower()
            records = [h for h in records if target_spec in h["specialty"].lower()]
        return self._finish(records, city)

    def get_by_id(self, hospital_id: Any) -> Optional[Dict[str, Any]]:
        """Retrieve a hospital by its ID (database, then CSV, then the verified directory)."""
        if is_directory_only(hospital_id):
            return directory_record(hospital_id)
        client = self._supabase.get_client()
        if client:
            try:
                res = client.table("hospitals").select("*, hospital_capacity(*)").eq("id", hospital_id).execute()
                if res.data and len(res.data) > 0:
                    return apply_verified(self._normalize_db_row(res.data[0]))
            except Exception as exc:
                logger.warning(f"Supabase get_by_id failed: {exc}")

        for h in self._load_from_csv():
            if str(h["id"]) == str(hospital_id):
                return apply_verified(dict(h))
        return None

    def list_departments(self, hospital_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve operational departments for a hospital or all departments."""
        if hospital_id is not None and is_directory_only(hospital_id):
            return []  # not an AIIS partner: nothing reported
        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("hospital_departments").select("*")
                if hospital_id is not None:
                    query = query.eq("hospital_id", hospital_id)
                res = query.execute()
                if res.data and len(res.data) > 0:
                    return res.data
            except Exception as exc:
                logger.warning(f"Failed to query hospital_departments from Supabase: {exc}")

        default_depts = [
            {"name": "Emergency & Casualty", "status": "Ready", "doctors_on_duty": 4, "notes": "24/7 Trauma and triage"},
            {"name": "Intensive Care Unit (ICU)", "status": "Ready", "doctors_on_duty": 3, "notes": "Critical care & ventilator support"},
            {"name": "General Medicine", "status": "Ready", "doctors_on_duty": 5, "notes": "OPD and inpatient consultation"},
            {"name": "Cardiology", "status": "Ready", "doctors_on_duty": 2, "notes": "Cath lab & emergency ECG"},
            {"name": "Paediatrics", "status": "Ready", "doctors_on_duty": 3, "notes": "OPD and neonatal care"},
            {"name": "Radiology & Imaging", "status": "Ready", "doctors_on_duty": 2, "notes": "CT, X-Ray & Ultrasound"},
        ]
        if hospital_id:
            return [{"id": i + 1, "hospital_id": hospital_id, **d} for i, d in enumerate(default_depts)]
        return default_depts

    def list_equipment(self, hospital_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve diagnostic and life-support equipment for a facility."""
        if hospital_id is not None and is_directory_only(hospital_id):
            return []  # not an AIIS partner: nothing reported
        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("hospital_equipment").select("*")
                if hospital_id is not None:
                    query = query.eq("hospital_id", hospital_id)
                res = query.execute()
                if res.data and len(res.data) > 0:
                    return res.data
            except Exception as exc:
                logger.warning(f"Failed to query hospital_equipment from Supabase: {exc}")

        default_equip = [
            {"name": "CT Scanner", "status": "Available", "total_units": 1, "available_units": 1},
            {"name": "Ventilators", "status": "Available", "total_units": 20, "available_units": 6},
            {"name": "X-Ray Machine", "status": "Available", "total_units": 2, "available_units": 2},
            {"name": "Hemodialysis", "status": "Available", "total_units": 6, "available_units": 2},
        ]
        if hospital_id:
            return [{"id": i + 1, "hospital_id": hospital_id, **e} for i, e in enumerate(default_equip)]
        return default_equip

    def list_capabilities(self, hospital_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve verified clinical capabilities for a facility."""
        if hospital_id is not None and is_directory_only(hospital_id):
            return []  # not an AIIS partner: nothing reported
        client = self._supabase.get_client()
        if client:
            try:
                query = client.table("hospital_capabilities").select("*")
                if hospital_id is not None:
                    query = query.eq("hospital_id", hospital_id)
                res = query.execute()
                if res.data and len(res.data) > 0:
                    return res.data
            except Exception as exc:
                logger.warning(f"Failed to query hospital_capabilities from Supabase: {exc}")

        default_caps = [
            {"capability_name": "emergency_receiving", "verification_state": "verified", "details": {"triage_available": True}},
            {"capability_name": "icu", "verification_state": "verified", "details": {"level": "Level 2"}},
            {"capability_name": "respiratory_emergencies", "verification_state": "verified", "details": {"piped_o2": True}},
        ]
        if hospital_id:
            return [{"hospital_id": hospital_id, **c} for c in default_caps]
        return default_caps

    def get_distinct_departments(self) -> List[str]:
        """Return unique sorted list of department names across the network."""
        client = self._supabase.get_client()
        if client:
            try:
                res = client.table("hospital_departments").select("name").execute()
                if res.data and len(res.data) > 0:
                    names = sorted(list(set(row["name"] for row in res.data if row.get("name"))))
                    if names:
                        return names
            except Exception as exc:
                logger.warning(f"Failed to get distinct departments from Supabase: {exc}")

        return [
            "Cardiology",
            "Emergency & Casualty",
            "General Medicine",
            "Intensive Care Unit (ICU)",
            "Paediatrics",
            "Radiology & Imaging",
        ]

    def get_cities(self) -> List[str]:
        """Return unique sorted list of cities present in the network."""
        records = self._load_from_csv()
        cities = sorted(list(set(h["city"] for h in records if h.get("city"))))
        return cities

    def get_locations(self) -> List[Dict[str, Any]]:
        """Return city centers with representative coordinates for quick frontend selection."""
        city_groups: Dict[str, List[Dict[str, Any]]] = {}
        for h in self._load_from_csv():
            city = h.get("city")
            if city:
                city_groups.setdefault(city, []).append(h)

        locations = []
        for city, hosp_list in sorted(city_groups.items()):
            avg_lat = sum(h["lat"] for h in hosp_list) / len(hosp_list)
            avg_lon = sum(h["lon"] for h in hosp_list) / len(hosp_list)
            locations.append({
                "name": city,
                "label": f"{city} ({len(hosp_list)} facilities)",
                "lat": round(avg_lat, 4),
                "lng": round(avg_lon, 4),
                "count": len(hosp_list),
            })

        # Add major urban localities for fine-grained neighbourhood selection
        bengaluru_localities = [
            {"name": "Bengaluru - MG Road (Central)", "label": "Bengaluru - MG Road (Central)", "lat": 12.9757, "lng": 77.605, "count": 0},
            {"name": "Bengaluru - Majestic / KR Market", "label": "Bengaluru - Majestic / KR Market", "lat": 12.9698, "lng": 77.5733, "count": 0},
            {"name": "Bengaluru - Shivajinagar", "label": "Bengaluru - Shivajinagar", "lat": 12.9857, "lng": 77.6057, "count": 0},
            {"name": "Bengaluru - Malleswaram", "label": "Bengaluru - Malleswaram", "lat": 13.0035, "lng": 77.571, "count": 0},
            {"name": "Bengaluru - Rajajinagar", "label": "Bengaluru - Rajajinagar", "lat": 12.9916, "lng": 77.5556, "count": 0},
            {"name": "Bengaluru - Hebbal", "label": "Bengaluru - Hebbal", "lat": 13.0358, "lng": 77.597, "count": 0},
            {"name": "Bengaluru - Yelahanka", "label": "Bengaluru - Yelahanka", "lat": 13.1007, "lng": 77.5963, "count": 0},
            {"name": "Bengaluru - Indiranagar", "label": "Bengaluru - Indiranagar", "lat": 12.9719, "lng": 77.6412, "count": 0},
            {"name": "Bengaluru - Whitefield", "label": "Bengaluru - Whitefield", "lat": 12.9698, "lng": 77.75, "count": 0},
            {"name": "Bengaluru - Marathahalli", "label": "Bengaluru - Marathahalli", "lat": 12.9569, "lng": 77.7011, "count": 0},
            {"name": "Bengaluru - Bellandur", "label": "Bengaluru - Bellandur", "lat": 12.9304, "lng": 77.6784, "count": 0},
            {"name": "Bengaluru - Koramangala", "label": "Bengaluru - Koramangala", "lat": 12.9352, "lng": 77.6245, "count": 0},
            {"name": "Bengaluru - Jayanagar", "label": "Bengaluru - Jayanagar", "lat": 12.925, "lng": 77.5938, "count": 0},
            {"name": "Bengaluru - Bannerghatta Road", "label": "Bengaluru - Bannerghatta Road", "lat": 12.889, "lng": 77.597, "count": 0},
            {"name": "Bengaluru - Electronic City", "label": "Bengaluru - Electronic City", "lat": 12.8452, "lng": 77.6602, "count": 0},
            {"name": "Bengaluru - Rajarajeshwari Nagar", "label": "Bengaluru - Rajarajeshwari Nagar", "lat": 12.9274, "lng": 77.5155, "count": 0},
            {"name": "Bengaluru - Kengeri", "label": "Bengaluru - Kengeri", "lat": 12.9081, "lng": 77.482, "count": 0},
            {"name": "Bengaluru - Vijayanagar", "label": "Bengaluru - Vijayanagar", "lat": 12.9719, "lng": 77.5321, "count": 0},
        ]
        return locations + bengaluru_localities
