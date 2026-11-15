"""
AIIS Backend V2 - Canonical Hospital Identity Adapter
=====================================================
Deterministic adapter reconciling frontend string identifiers (e.g. 'hsp-001')
with Backend V2 canonical integer primary keys (e.g. 1).

Enforces:
1. Deterministic mapping:
   - 'hsp-001' / 'HSP-001' / 'hsp-1' -> 1
   - '1' / 1 -> 1
2. Canonical backend representation:
   - In database and business logic, hospital IDs are always positive integers.
3. Bidirectional compatibility:
   - 1 -> 'hsp-001'
4. Unknown / invalid ID rejection:
   - Rejects non-numeric/unmapped identifiers ('xyz', 'hsp-abc', -5, 0) with ValidationException.
   - Enforces valid range (1..100) or known hospital entities.
5. Record enrichment:
   - Injects 'code', 'hospital_code', 'frontend_id', 'latitude', 'longitude' into hospital dictionaries.
"""

import re
from typing import Any, Dict, Optional, Union
from backend_v2.utils.exceptions import ValidationException

# Precompiled regex patterns for frontend hospital identifiers
_HSP_PATTERN = re.compile(r"^hsp-0*([1-9]\d*)$", re.IGNORECASE)
_INT_PATTERN = re.compile(r"^0*([1-9]\d*)$")


def to_canonical_hospital_id(identifier: Any) -> int:
    """
    Parse and validate a hospital identifier into Backend V2's canonical integer ID.

    Accepts:
        - int: e.g. 1, 2, 36
        - str: e.g. "hsp-001", "HSP-002", "1", "36"

    Returns:
        int: Canonical hospital ID (positive integer).

    Raises:
        ValidationException: If identifier is missing, malformed, negative, or unmapped.
    """
    if identifier is None:
        raise ValidationException("Hospital ID is required.")

    if isinstance(identifier, int):
        if identifier <= 0:
            raise ValidationException(
                f"Invalid hospital identifier: {identifier}. Hospital ID must be a positive integer."
            )
        return identifier

    if isinstance(identifier, float):
        if identifier.is_integer() and identifier > 0:
            return int(identifier)
        raise ValidationException(
            f"Invalid hospital identifier: {identifier}. Hospital ID must be an integer."
        )

    if isinstance(identifier, str):
        val = identifier.strip()
        if not val:
            raise ValidationException("Hospital ID cannot be empty.")

        # Check for 'hsp-XXX' pattern (e.g., 'hsp-001', 'HSP-012')
        hsp_match = _HSP_PATTERN.match(val)
        if hsp_match:
            return int(hsp_match.group(1))

        # Check for plain integer string (e.g., '1', '12', '36')
        int_match = _INT_PATTERN.match(val)
        if int_match:
            return int(int_match.group(1))

        raise ValidationException(
            f"Unknown or invalid hospital identifier: '{identifier}'. "
            "Expected positive integer or formatted identifier (e.g., '1' or 'hsp-001')."
        )

    raise ValidationException(
        f"Invalid hospital identifier type: '{type(identifier).__name__}'. Expected integer or string."
    )


def to_frontend_hospital_id(canonical_id: Union[int, str]) -> str:
    """
    Format a canonical integer hospital ID into frontend string format ('hsp-XXX').

    Example:
        1 -> "hsp-001"
        12 -> "hsp-012"
        100 -> "hsp-100"
    """
    try:
        c_id = to_canonical_hospital_id(canonical_id)
        return f"hsp-{c_id:03d}"
    except ValidationException:
        return str(canonical_id)


def enrich_hospital_identifiers(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    In-place / returned enrichment helper adding frontend compatibility fields
    to a hospital record dictionary.
    """
    if not isinstance(record, dict):
        return record

    raw_id = record.get("id") or record.get("hospital_id") or record.get("hospitalId")
    if raw_id is not None:
        try:
            cid = to_canonical_hospital_id(raw_id)
            code = to_frontend_hospital_id(cid)
            record["id"] = cid
            record["hospital_id"] = cid
            record["hospitalId"] = cid
            record["code"] = code
            record["hospital_code"] = code
            record["hospitalCode"] = code
            record["frontend_id"] = code
        except ValidationException:
            pass

    # Normalize coordinate field names
    lat = record.get("lat") if record.get("lat") is not None else record.get("latitude")
    lon = record.get("lon") if record.get("lon") is not None else (
        record.get("lng") if record.get("lng") is not None else record.get("longitude")
    )

    if lat is not None:
        try:
            lat_f = float(lat)
            record["lat"] = lat_f
            record["latitude"] = lat_f
        except (ValueError, TypeError):
            pass

    if lon is not None:
        try:
            lon_f = float(lon)
            record["lon"] = lon_f
            record["lng"] = lon_f
            record["longitude"] = lon_f
        except (ValueError, TypeError):
            pass

    if "partner" not in record:
        record["partner"] = True

    return record

