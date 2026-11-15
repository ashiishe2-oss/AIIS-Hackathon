"""
AIIS Backend V2 - Hospitals Test Suite (Foundational)
=====================================================
Verifies initial blueprint registration and placeholder routing for /api/hospitals.
"""

import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


def test_hospitals_blueprint_mounted(client):
    """Confirm /api/hospitals prefix is active on the application router."""
    response = client.get("/api/hospitals/undefined")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_hospital_admin_blueprint_mounted(client):
    """Confirm /api/hospital prefix is active on the application router."""
    response = client.get("/api/hospital/undefined")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"

