"""
AIIS Backend V2 - Validation Utilities
======================================
Reusable input validation functions for geographic coordinates, phone numbers, etc.
"""

import re
from typing import Optional, Tuple


def validate_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """Validate latitude and longitude ranges."""
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False, "Coordinates must be numerical values."
    if not (-90.0 <= lat <= 90.0):
        return False, f"Latitude {lat} must be between -90 and 90."
    if not (-180.0 <= lon <= 180.0):
        return False, f"Longitude {lon} must be between -180 and 180."
    return True, None


def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate standard Indian / international phone format."""
    if not isinstance(phone, str):
        return False, "Phone number must be a string."
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    # Allows +91xxxxxxxxxx or 10-digit Indian mobile numbers
    if re.match(r"^(\+91)?[6-9]\d{9}$", cleaned):
        return True, None
    return False, "Invalid phone number format."

