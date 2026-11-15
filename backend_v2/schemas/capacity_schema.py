"""
AIIS Backend V2 - Capacity Schemas
==================================
Data validation and normalization for hospital live capacity updates.
Enforces non-negative values, mathematical balance constraints,
and bidirectional frontend naming compatibility (camelCase <-> snake_case).
"""

from typing import Optional, Dict, Any, Tuple


class CapacityUpdateSchema:
    """Validator and normalizer for hospital capacity updates."""

    VALID_OXYGEN_STATUSES = {"adequate", "low", "critical", "surplus", "unavailable", "unknown"}
    VALID_RECEIVING_STATUSES = {
        "available", "open", "busy", "divert", "diverting", "full", "closing", "closed", "unknown"
    }
    VALID_CAPACITY_STATUSES = {"available", "occupied", "provisionally_allocated", "unavailable", "unknown"}

    @classmethod
    def validate(
        cls, data: Dict[str, Any], current_record: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validate and clean capacity update payload.
        Merges with current_record to verify balance constraints when partial updates are provided.
        Returns: (is_valid, error_message, cleaned_dict)
        """
        if not isinstance(data, dict):
            return False, "Capacity payload must be a JSON object.", {}

        cleaned: Dict[str, Any] = {}
        curr = current_record or {}

        # 1. Integer fields extraction & non-negative checks
        field_mappings = {
            "total_beds": ["total_beds", "totalBeds", "num_beds"],
            "available_beds": ["available_beds", "availableBeds", "emergency_beds", "emergencyBeds"],
            "occupied_beds": ["occupied_beds", "occupiedBeds"],
            "provisionally_allocated_beds": ["provisionally_allocated_beds", "provisionallyAllocatedBeds"],
            "icu_total": ["icu_total", "icuTotal", "total_icu", "totalIcu", "icu_beds", "icuBeds"],
            "icu_available": ["icu_available", "icuAvailable", "available_icu", "availableIcu"],
            "icu_occupied": ["icu_occupied", "icuOccupied", "occupied_icu", "occupiedIcu"],
            "ventilators_total": ["ventilators_total", "ventilatorsTotal", "ventilators"],
            "ventilators_available": ["ventilators_available", "ventilatorsAvailable"],
        }

        for canonical_name, aliases in field_mappings.items():
            val = None
            for alias in aliases:
                if alias in data and data[alias] is not None:
                    raw_val = data[alias]
                    if isinstance(raw_val, dict):
                        if canonical_name in ("total_beds", "icu_total", "ventilators_total"):
                            val = raw_val.get("total") or raw_val.get("capacity") or raw_val.get("max")
                        elif canonical_name in ("available_beds", "icu_available", "ventilators_available"):
                            val = raw_val.get("available") or raw_val.get("free") or raw_val.get("vacant") or raw_val.get("count")
                        elif canonical_name in ("occupied_beds", "icu_occupied"):
                            val = raw_val.get("occupied") or raw_val.get("busy")
                    else:
                        val = raw_val

                    if val is not None:
                        break

            if val is not None:
                try:
                    int_val = int(val)
                except (ValueError, TypeError):
                    return False, f"Field '{canonical_name}' must be an integer.", {}

                if int_val < 0:
                    return False, f"Field '{canonical_name}' must be a non-negative integer.", {}

                cleaned[canonical_name] = int_val

        # Handle simple legacy update-beds payload: e.g. {"num_beds": 500}
        # If total_beds is updated but occupied/available are not specified, adjust available_beds
        if "total_beds" in cleaned and "occupied_beds" not in cleaned and "available_beds" not in cleaned:
            tot = cleaned["total_beds"]
            curr_occ = int(curr.get("occupied_beds", 0))
            curr_prov = int(curr.get("provisionally_allocated_beds", 0))
            if curr_occ + curr_prov > tot:
                cleaned["occupied_beds"] = tot - curr_prov
                cleaned["available_beds"] = 0
            else:
                cleaned["available_beds"] = tot - curr_occ - curr_prov

        # 2. Mathematical balance constraint validation
        tot_beds = cleaned.get("total_beds", curr.get("total_beds", 0))
        occ_beds = cleaned.get("occupied_beds", curr.get("occupied_beds", 0))
        avail_beds = cleaned.get("available_beds", curr.get("available_beds", 0))
        prov_beds = cleaned.get("provisionally_allocated_beds", curr.get("provisionally_allocated_beds", 0))

        if (occ_beds + avail_beds + prov_beds) > tot_beds:
            if "available_beds" in cleaned and "occupied_beds" not in cleaned:
                cleaned["occupied_beds"] = max(0, tot_beds - avail_beds - prov_beds)
            else:
                return (
                    False,
                    f"Capacity balance constraint violated: occupied_beds ({occ_beds}) + available_beds ({avail_beds}) "
                    f"+ provisionally_allocated_beds ({prov_beds}) exceeds total_beds ({tot_beds}).",
                    {},
                )

        tot_icu = cleaned.get("icu_total", curr.get("icu_total", 0))
        occ_icu = cleaned.get("icu_occupied", curr.get("icu_occupied", 0))
        avail_icu = cleaned.get("icu_available", curr.get("icu_available", 0))

        if (occ_icu + avail_icu) > tot_icu:
            if "icu_available" in cleaned and "icu_occupied" not in cleaned:
                cleaned["icu_occupied"] = max(0, tot_icu - avail_icu)
            else:
                return (
                    False,
                    f"ICU balance constraint violated: icu_occupied ({occ_icu}) + icu_available ({avail_icu}) "
                    f"exceeds icu_total ({tot_icu}).",
                    {},
                )

        tot_vent = cleaned.get("ventilators_total", curr.get("ventilators_total", 0))
        avail_vent = cleaned.get("ventilators_available", curr.get("ventilators_available", 0))

        if avail_vent > tot_vent:
            return (
                False,
                f"Ventilator constraint violated: ventilators_available ({avail_vent}) "
                f"exceeds ventilators_total ({tot_vent}).",
                {},
            )

        # 3. Status string fields
        raw_oxygen = data.get("oxygen_status") or data.get("oxygenStatus")
        if raw_oxygen is not None:
            ox_str = str(raw_oxygen).strip().lower()
            if ox_str not in cls.VALID_OXYGEN_STATUSES:
                return (
                    False,
                    f"Invalid oxygen_status '{raw_oxygen}'. Must be one of: {sorted(cls.VALID_OXYGEN_STATUSES)}",
                    {},
                )
            cleaned["oxygen_status"] = ox_str

        raw_receiving = data.get("emergency_receiving_status") or data.get("emergencyReceivingStatus")
        if raw_receiving is not None:
            rec_str = str(raw_receiving).strip().lower()
            if rec_str not in cls.VALID_RECEIVING_STATUSES:
                return (
                    False,
                    f"Invalid emergency_receiving_status '{raw_receiving}'. Must be one of: {sorted(cls.VALID_RECEIVING_STATUSES)}",
                    {},
                )
            cleaned["emergency_receiving_status"] = rec_str

        raw_status = data.get("status")
        if raw_status is not None:
            st_str = str(raw_status).strip().lower()
            if st_str not in cls.VALID_CAPACITY_STATUSES:
                return (
                    False,
                    f"Invalid status '{raw_status}'. Must be one of: {sorted(cls.VALID_CAPACITY_STATUSES)}",
                    {},
                )
            cleaned["status"] = st_str

        # 4. Department readiness and equipment availability
        depts = (
            data.get("department_readiness")
            or data.get("departmentReadiness")
            or data.get("departments")
        )
        if depts is not None:
            if not isinstance(depts, list):
                return False, "Department readiness must be a list of department objects.", {}
            cleaned["departments"] = depts

        equipment = (
            data.get("equipment_availability")
            or data.get("equipmentAvailability")
            or data.get("equipment")
        )
        if equipment is not None:
            if not isinstance(equipment, list):
                return False, "Equipment availability must be a list of equipment objects.", {}
            cleaned["equipment"] = equipment

        # 5. Change reason / notes
        reason = data.get("change_reason") or data.get("reason") or data.get("notes")
        if reason is not None:
            cleaned["change_reason"] = str(reason).strip()

        return True, None, cleaned
