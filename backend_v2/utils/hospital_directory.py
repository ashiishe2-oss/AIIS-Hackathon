"""
AIIS Backend V2 - Verified hospital locations and phone numbers
================================================================
Single source of truth for *where* each hospital is and *which number* to call.

`data/verified_hospitals.json` holds, per hospital:
  - the exact location: the hospital's own Google Maps place pin (lat/lng) and its
    Google-listed address, checked 14 Nov 2026;
  - real phone numbers with their source (official website or Google listing);
  - its emergency scope (general / cardiac / neuro / trauma / children / maternity / eye).

Why this exists: the database seed carried placeholder numbers (+91-800-000-xxxx) and
approximate coordinates. A raw lat/lng sent to Google Maps snaps to the nearest building
(for Victoria Hospital that was "Centenary Building"), so "Directions" opened the wrong place.
Directions now use the hospital's own name + address, which Google resolves to the exact
place listing, and distances use the verified pin.

The overlay is applied on read, so it works whether data comes from Supabase or the CSV.
`directory` adds real Bengaluru hospitals that are not in the database: they can be called
and navigated to, but are not AIIS partners (no "Tell them I'm coming").
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional
from urllib.parse import quote

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "verified_hospitals.json")

SCOPE_NOTE = {
    "general": "24x7 emergency for all emergencies",
    "cardiac": "Heart emergencies only",
    "neuro": "Brain, nerve and mental health emergencies only",
    "trauma": "Accidents, fractures and injuries",
    "children": "Children only",
    "maternity": "Pregnancy, childbirth and newborns",
    "eye": "Eye emergencies only",
}


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    try:
        with open(_DATA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # pragma: no cover - data file must ship with the app
        return {"hospitals": {}, "hidden": {}, "directory": {}, "checked": None}


def checked_date() -> Optional[str]:
    return _load().get("checked")


def maps_links(name: str, address: str) -> Dict[str, str]:
    """Google Maps links that open the hospital's own place listing (not a nearby building)."""
    q = quote(f"{name}, {address}".strip(", "))
    return {
        "mapsUrl": f"https://www.google.com/maps/search/?api=1&query={q}",
        "directionsUrl": f"https://www.google.com/maps/dir/?api=1&destination={q}&travelmode=driving",
    }


def _phone_status(phones: List[Dict[str, str]]) -> Optional[str]:
    if not phones:
        return None
    src = (phones[0].get("source") or "").lower()
    return "official" if ("official" in src or "website" in src) else "listing"


def _source(phones: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if not phones:
        return None
    return {"label": phones[0].get("source") or "", "url": ""}


def is_hidden(hospital_id: Any) -> bool:
    return str(hospital_id) in _load().get("hidden", {})


def is_directory_only(hospital_id: Any) -> bool:
    return str(hospital_id) in _load().get("directory", {})


def _verified_fields(v: Dict[str, Any]) -> Dict[str, Any]:
    phones = [p for p in (v.get("phones") or []) if p.get("number")]
    lat, lng = float(v["lat"]), float(v["lng"])
    first = phones[0]["number"] if phones else None
    second = phones[1]["number"] if len(phones) > 1 else first
    scope = v.get("emergencyScope") or "general"
    out = {
        "name": v["name"],
        "address": v["address"],
        "lat": lat, "lon": lon_or(lng), "lng": lng, "latitude": lat, "longitude": lng,
        "coordinates": {"latitude": lat, "longitude": lng},
        "locationVerified": True,
        "locationSource": "Google Maps place listing (checked %s)" % (checked_date() or ""),
        "phones": phones,
        "phone": first,
        "emergencyPhone": first,
        "emergencyPhoneLabel": phones[0]["label"] if phones else None,
        "receptionPhone": second,
        "receptionPhoneLabel": phones[1]["label"] if len(phones) > 1 else (phones[0]["label"] if phones else None),
        "contact_number": first,
        "emergency_phone": first,
        "phoneStatus": _phone_status(phones),
        "source": _source(phones),
        "noPhoneNote": None if phones else "No verified phone number for this hospital. Call 108 for an ambulance.",
        "emergencyScope": scope,
        "scopeNote": SCOPE_NOTE.get(scope, ""),
    }
    out.update(maps_links(v["name"], v["address"]))
    return out


def lon_or(x: float) -> float:
    return float(x)


def apply_verified(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Overlay verified location / phones on a hospital record (in place) and return it."""
    if not isinstance(record, dict):
        return record
    v = _load().get("hospitals", {}).get(str(record.get("id")))
    if v:
        record.update(_verified_fields(v))
    else:
        # Never expose placeholder numbers such as +91-800-000-xxxx.
        for k in ("phone", "emergencyPhone", "receptionPhone", "contact_number", "emergency_phone"):
            val = str(record.get(k) or "")
            if "800-000" in val or val.endswith("HELP"):
                record[k] = None
        if record.get("name"):
            record.update(maps_links(record["name"], record.get("address") or record.get("city") or ""))
        record.setdefault("emergencyScope", "general")
        record.setdefault("scopeNote", SCOPE_NOTE["general"])
        record.setdefault("locationVerified", False)
    return record


def directory_records(city: Optional[str] = None) -> List[Dict[str, Any]]:
    """Real hospitals that are not in the AIIS database (call and directions only)."""
    out = []
    for hid, v in _load().get("directory", {}).items():
        if city and city.strip().lower() not in (v.get("city") or "").lower():
            continue
        rec = {
            "id": int(hid),
            "city": v.get("city", "Bengaluru"),
            "district": v.get("district", "Bengaluru Urban"),
            "state": "Karnataka",
            "sector": v.get("sector"),
            "type": "Hospital",
            "specialty": "Multi-Specialty" if v.get("emergencyScope") == "general" else "Specialty",
            "capacity": None,
            "partner": False,
            "directoryOnly": True,
            "emergencyFacilities": [SCOPE_NOTE.get(v.get("emergencyScope") or "general", "")],
            "dataFreshness": {"lastUpdated": None, "source": "Not connected to AIIS: call to check beds", "isSimulated": False},
        }
        rec.update(_verified_fields(v))
        out.append(rec)
    return out


def directory_record(hospital_id: Any) -> Optional[Dict[str, Any]]:
    for r in directory_records():
        if str(r["id"]) == str(hospital_id):
            return r
    return None
