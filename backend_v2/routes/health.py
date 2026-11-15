"""
AIIS Backend V2 - Health Check Route
====================================
Foundational system health verification endpoint.
"""

from flask import Blueprint
from backend_v2.utils.responses import success_response

health_bp = Blueprint("health", __name__)


@health_bp.route("", methods=["GET"])
@health_bp.route("/", methods=["GET"])
def check_health():
    """
    Standard health check endpoint.
    Returns:
        JSON response with service name and operational status.
    """
    return success_response(
        data={
            "service": "AIIS Backend V2",
            "status": "healthy",
        },
        status_code=200,
    )

