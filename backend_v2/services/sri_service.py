"""
AIIS Backend V2 - Strain Risk Index (SRI) Service
=================================================
Calculates the Regional and Facility-Level Strain Risk Index (SRI).
Adheres strictly to deterministic mathematical evaluation based on persisted operational data.

Formula Specification:
----------------------
SRI = (w1 * Bed Occupancy %) + (w2 * ICU Occupancy %) + (w3 * Provisional Hold %) + (w4 * Capacity Variability)
Where:
    w1 = 0.40 (Bed Occupancy Ratio: occupied_beds / total_beds * 100)
    w2 = 0.35 (ICU Occupancy Ratio: icu_occupied / icu_total * 100, falls back to Bed Occupancy if icu_total == 0)
    w3 = 0.15 (Provisional Emergency Hold Ratio: provisionally_allocated_beds / total_beds * 100)
    w4 = 0.10 (Historical Capacity Variability: standard deviation of occupancy across snapshots, clamped 0..100)
Total Weights: 0.40 + 0.35 + 0.15 + 0.10 = 1.00 (Score bounded strictly to 0.0 - 100.0)

Risk Band Thresholds:
---------------------
- LOW:        score < 40.0
- MODERATE:   40.0 <= score < 70.0
- HIGH:       70.0 <= score < 85.0
- CRITICAL:   score >= 85.0

Data Integrity & Honesty Rules:
-------------------------------
1. If data is missing or total capacity is zero, returns status: "INSUFFICIENT_DATA".
2. Pure deterministic calculation. Never generates random scores or pseudo-random forecasts.
3. Descriptive operational infrastructure metric, not a clinical forecast.
"""

import math
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

from backend_v2.repositories.capacity_repository import CapacityRepository
from backend_v2.repositories.hospital_repository import HospitalRepository
from backend_v2.utils.hospital_id_adapter import (
    to_canonical_hospital_id,
    to_frontend_hospital_id,
)

logger = logging.getLogger("aiis.services.sri")


class SRIService:
    """Service providing deterministic Strain Risk Index calculation."""

    WEIGHT_BED_OCCUPANCY = 0.40
    WEIGHT_ICU_OCCUPANCY = 0.35
    WEIGHT_PROVISIONAL_HOLD = 0.15
    WEIGHT_VARIABILITY = 0.10

    def __init__(
        self,
        capacity_repo: Optional[CapacityRepository] = None,
        hospital_repo: Optional[HospitalRepository] = None,
    ):
        self.capacity_repo = capacity_repo or CapacityRepository()
        self.hospital_repo = hospital_repo or HospitalRepository()

    @classmethod
    def get_risk_band(cls, score: Optional[float]) -> str:
        """Classify numerical SRI score into standardized risk band."""
        if score is None:
            return "INSUFFICIENT_DATA"
        if score < 40.0:
            return "LOW"
        if score < 70.0:
            return "MODERATE"
        if score < 85.0:
            return "HIGH"
        return "CRITICAL"

    def _calculate_hospital_variability(
        self, hospital_id: int, use_remote: bool = True
    ) -> float:
        """
        Calculate historical capacity variability (std deviation of occupancy) from history snapshots.
        Returns a value clamped between 0.0 and 100.0.
        """
        if not use_remote:
            with self.capacity_repo._lock:
                history = list(reversed(self.capacity_repo._history.get(hospital_id, [])))[:20]
        else:
            history = self.capacity_repo.list_history(hospital_id, limit=20)

        if len(history) < 2:
            return 0.0

        ratios = []
        for h in history:
            tot = float(h.get("total_beds", 0))
            occ = float(h.get("occupied_beds", 0))
            if tot > 0:
                ratios.append((occ / tot) * 100.0)

        if len(ratios) < 2:
            return 0.0

        mean = sum(ratios) / len(ratios)
        variance = sum((r - mean) ** 2 for r in ratios) / len(ratios)
        std_dev = math.sqrt(variance)
        return min(100.0, round(std_dev, 2))

    def calculate_hospital_sri(
        self,
        hospital_id: Any,
        hospital_dict: Optional[Dict[str, Any]] = None,
        use_remote_history: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculate deterministic SRI score for a single facility.
        Safe against zero capacity, missing data, and invalid values.
        """
        canonical_id = to_canonical_hospital_id(hospital_id)
        hospital = hospital_dict or self.hospital_repo.get_by_id(canonical_id)
        cap = self.capacity_repo.get_capacity(canonical_id)

        if not cap or not hospital:
            return {
                "hospital_id": canonical_id,
                "hospitalId": to_frontend_hospital_id(canonical_id),
                "sri_score": None,
                "risk_band": "INSUFFICIENT_DATA",
                "status": "INSUFFICIENT_DATA",
                "message": f"Capacity data unavailable for hospital {hospital_id}.",
            }

        tot_beds = float(cap.get("total_beds", 0))
        occ_beds = float(cap.get("occupied_beds", 0))
        prov_beds = float(cap.get("provisionally_allocated_beds", 0))
        icu_tot = float(cap.get("icu_total", 0))
        icu_occ = float(cap.get("icu_occupied", 0))

        # Safe zero capacity handling
        if tot_beds <= 0:
            return {
                "hospital_id": canonical_id,
                "hospitalId": to_frontend_hospital_id(canonical_id),
                "sri_score": None,
                "risk_band": "INSUFFICIENT_DATA",
                "status": "INSUFFICIENT_DATA",
                "message": "Hospital has zero recorded total bed capacity.",
            }

        # Sub-indices
        bed_occ_pct = min(100.0, max(0.0, (occ_beds / tot_beds) * 100.0))
        if icu_tot > 0:
            icu_occ_pct = min(100.0, max(0.0, (icu_occ / icu_tot) * 100.0))
        else:
            icu_occ_pct = bed_occ_pct  # Fall back to general bed occupancy if hospital has no ICU

        hold_pct = min(100.0, max(0.0, (prov_beds / tot_beds) * 100.0))
        variability = self._calculate_hospital_variability(canonical_id, use_remote=use_remote_history)

        score = (
            (self.WEIGHT_BED_OCCUPANCY * bed_occ_pct)
            + (self.WEIGHT_ICU_OCCUPANCY * icu_occ_pct)
            + (self.WEIGHT_PROVISIONAL_HOLD * hold_pct)
            + (self.WEIGHT_VARIABILITY * variability)
        )
        final_score = round(min(100.0, max(0.0, score)), 1)
        risk_band = self.get_risk_band(final_score)

        return {
            "hospital_id": canonical_id,
            "hospitalId": to_frontend_hospital_id(canonical_id),
            "hospital_code": to_frontend_hospital_id(canonical_id),
            "name": hospital.get("name", "Public Hospital"),
            "city": hospital.get("city", ""),
            "district": hospital.get("district") or hospital.get("city") or "Bengaluru Urban",
            "sri_score": final_score,
            "score": final_score,
            "risk_band": risk_band,
            "strain_risk": risk_band.capitalize(),
            "strain_risk_class": risk_band.lower(),
            "status": "VALID",
            "bed_occupancy_pct": round(bed_occ_pct, 1),
            "icu_occupancy_pct": round(icu_occ_pct, 1),
            "provisional_hold_pct": round(hold_pct, 1),
            "capacity_variability": round(variability, 2),
            "total_beds": int(tot_beds),
            "available_beds": int(cap.get("available_beds", 0)),
            "occupied_beds": int(occ_beds),
            "total_icu": int(icu_tot),
            "available_icu": int(cap.get("icu_available", 0)),
            "source": cap.get("source", "seeded_baseline"),
            "verified_realtime": False,
            "freshness": cap.get("freshness", "baseline"),
            "updated_at": cap.get("updated_at"),
        }

    def calculate_regional_sri(
        self, city: Optional[str] = None, district: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate composite Regional Strain Risk Index across the healthcare network or specific municipality.
        Returns aggregate metrics, risk distribution, hospital details, and documented formula.
        """
        all_hospitals = self.hospital_repo.list_all()
        if not all_hospitals:
            return self._insufficient_data_response("No hospital records found in database.")

        # Filter by city or district if supplied
        filtered_hospitals = all_hospitals
        if city:
            c_target = city.strip().lower()
            filtered_hospitals = [
                h for h in filtered_hospitals if c_target in str(h.get("city", "")).lower()
            ]

        if not filtered_hospitals:
            return self._insufficient_data_response(
                f"No facilities found matching city='{city}'."
            )

        now = datetime.now(timezone.utc)
        observation_start = (now - timedelta(days=7)).isoformat()
        calculation_ts = now.isoformat()

        hospital_results: List[Dict[str, Any]] = []
        tot_network_beds = 0
        tot_network_occ = 0
        tot_network_avail = 0
        tot_network_prov = 0
        tot_network_icu = 0
        tot_network_icu_occ = 0
        tot_network_icu_avail = 0

        weighted_sri_sum = 0.0
        total_eval_beds = 0
        has_realtime = False

        for h in filtered_hospitals:
            h_res = self.calculate_hospital_sri(h["id"], hospital_dict=h, use_remote_history=False)
            hospital_results.append(h_res)

            if h_res.get("status") == "VALID":
                b_tot = h_res.get("total_beds", 0)
                tot_network_beds += b_tot
                tot_network_occ += h_res.get("occupied_beds", 0)
                tot_network_avail += h_res.get("available_beds", 0)
                tot_network_icu += h_res.get("total_icu", 0)
                tot_network_icu_avail += h_res.get("available_icu", 0)

                sri_val = h_res.get("sri_score", 0.0)
                weighted_sri_sum += sri_val * b_tot
                total_eval_beds += b_tot

                if h_res.get("verified_realtime"):
                    has_realtime = True

        if total_eval_beds <= 0 or not hospital_results:
            return self._insufficient_data_response("Zero operational beds across evaluated facilities.")

        # Aggregate weighted regional score
        regional_score = round(weighted_sri_sum / total_eval_beds, 1)
        regional_risk_band = self.get_risk_band(regional_score)

        # Risk distribution counts
        risk_dist = {
            "low_risk": sum(1 for h in hospital_results if h.get("risk_band") == "LOW"),
            "medium_risk": sum(1 for h in hospital_results if h.get("risk_band") == "MODERATE"),
            "high_risk": sum(1 for h in hospital_results if h.get("risk_band") == "HIGH"),
            "critical_risk": sum(1 for h in hospital_results if h.get("risk_band") == "CRITICAL"),
        }

        # Check freshness
        has_recent = any(h.get("freshness") == "recent" for h in hospital_results)
        data_freshness = "recent" if has_recent else "baseline"

        valid_count = sum(1 for h in hospital_results if h.get("status") == "VALID")
        completeness_pct = round((valid_count / max(1, len(hospital_results))) * 100.0, 1)

        return {
            "status": "VALID",
            "regional_score": regional_score,
            "avg_sri": regional_score,
            "risk_band": regional_risk_band,
            "region": city or "All Karnataka Regions",
            "observation_period": {
                "start": observation_start,
                "end": calculation_ts,
                "facilities_evaluated": len(hospital_results),
            },
            "calculation_timestamp": calculation_ts,
            "metrics": {
                "total_hospitals": len(hospital_results),
                "total_beds": tot_network_beds,
                "occupied_beds": tot_network_occ,
                "available_beds": tot_network_avail,
                "avg_bed_occupancy_pct": round((tot_network_occ / max(1, tot_network_beds)) * 100.0, 1),
                "total_icu": tot_network_icu,
                "available_icu": tot_network_icu_avail,
                "avg_icu_occupancy_pct": round(
                    ((tot_network_icu - tot_network_icu_avail) / max(1, tot_network_icu)) * 100.0, 1
                ),
                "data_completeness_pct": completeness_pct,
                "data_freshness": data_freshness,
                "verified_realtime": False,
            },
            "risk_distribution": risk_dist,
            "kpi": {
                "total_hospitals": len(hospital_results),
                "total_beds": tot_network_beds,
                "total_icu": tot_network_icu,
                "high_risk": risk_dist["high_risk"] + risk_dist["critical_risk"],
                "medium_risk": risk_dist["medium_risk"],
                "low_risk": risk_dist["low_risk"],
                "avg_sri": regional_score,
                "avg_occupancy": round((tot_network_occ / max(1, tot_network_beds)) * 100.0, 1),
                "avg_opd_growth": 0.0,
            },
            "hospitals": hospital_results,
            "formula": {
                "name": "Deterministic Composite Strain Risk Index (SRI)",
                "weights": {
                    "bed_occupancy_ratio": self.WEIGHT_BED_OCCUPANCY,
                    "icu_occupancy_ratio": self.WEIGHT_ICU_OCCUPANCY,
                    "provisional_emergency_holds": self.WEIGHT_PROVISIONAL_HOLD,
                    "capacity_variability": self.WEIGHT_VARIABILITY,
                },
                "thresholds": {
                    "low": "score < 40.0",
                    "moderate": "40.0 <= score < 70.0",
                    "high": "70.0 <= score < 85.0",
                    "critical": "score >= 85.0",
                },
                "disclaimer": (
                    "SRI is an operational workload metric based on recorded bed occupancy "
                    "and provisional hold ratios. It is not an algorithmic emergency match disqualifier "
                    "or a machine-learning future forecast."
                ),
            },
        }

    def _insufficient_data_response(self, message: str) -> Dict[str, Any]:
        """Structured deterministic response when data is insufficient for SRI calculation."""
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "status": "INSUFFICIENT_DATA",
            "regional_score": None,
            "avg_sri": None,
            "risk_band": "INSUFFICIENT_DATA",
            "message": message,
            "calculation_timestamp": now_iso,
            "metrics": {
                "total_hospitals": 0,
                "total_beds": 0,
                "occupied_beds": 0,
                "available_beds": 0,
                "avg_bed_occupancy_pct": 0.0,
                "total_icu": 0,
                "available_icu": 0,
                "avg_icu_occupancy_pct": 0.0,
                "data_completeness_pct": 0.0,
                "data_freshness": "insufficient",
                "verified_realtime": False,
            },
            "risk_distribution": {
                "low_risk": 0,
                "medium_risk": 0,
                "high_risk": 0,
                "critical_risk": 0,
            },
            "hospitals": [],
            "formula": {
                "name": "Deterministic Composite Strain Risk Index (SRI)",
                "weights": {
                    "bed_occupancy_ratio": self.WEIGHT_BED_OCCUPANCY,
                    "icu_occupancy_ratio": self.WEIGHT_ICU_OCCUPANCY,
                    "provisional_emergency_holds": self.WEIGHT_PROVISIONAL_HOLD,
                    "capacity_variability": self.WEIGHT_VARIABILITY,
                },
            },
        }
