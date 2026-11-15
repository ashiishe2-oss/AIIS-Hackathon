"""
AIIS Backend V2 - Routes Package
================================
Registers and exports all Blueprints.
"""

from backend_v2.routes.health import health_bp
from backend_v2.routes.emergency import emergency_bp, coordination_bp, locations_bp
from backend_v2.routes.hospitals import hospitals_bp, departments_bp
from backend_v2.routes.hospital_admin import hospital_admin_bp
from backend_v2.routes.capacity import capacity_bp
from backend_v2.routes.sri import sri_bp
from backend_v2.routes.authentication import auth_bp
from backend_v2.routes.appointments import appointments_bp
from backend_v2.routes.planned import planned_bp
from backend_v2.routes.web import web_bp

__all__ = [
    "health_bp",
    "emergency_bp",
    "coordination_bp",
    "locations_bp",
    "hospitals_bp",
    "departments_bp",
    "hospital_admin_bp",
    "capacity_bp",
    "sri_bp",
    "auth_bp",
    "appointments_bp",
    "planned_bp",
    "web_bp",
]
