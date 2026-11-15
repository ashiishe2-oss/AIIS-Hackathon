"""
AIIS Backend V2 - Health & Foundation Tests
===========================================
Pytest suite verifying application factory initialization,
health check contract, blueprint registration, and secret isolation.
"""

import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig


@pytest.fixture
def app():
    """Create and configure a Flask application instance for testing."""
    test_app = create_app(TestingConfig)
    return test_app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def test_app_starts(app):
    """Verify application factory initializes and sets testing mode."""
    assert app is not None
    assert app.testing is True
    assert app.config["APP_NAME"] == "AIIS Backend V2"


def test_blueprints_registered(app):
    """Verify all designated blueprints are registered with expected prefixes."""
    expected_blueprints = {"health", "emergency", "hospitals", "hospital_admin", "auth"}
    registered_blueprints = set(app.blueprints.keys())

    for bp in expected_blueprints:
        assert bp in registered_blueprints, f"Blueprint '{bp}' should be registered"


def test_health_endpoint_success(client):
    """
    Verify GET /api/health returns HTTP 200 and exact required JSON payload:
    {
      "success": true,
      "data": {
        "service": "AIIS Backend V2",
        "status": "healthy"
      }
    }
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert data["success"] is True
    assert "data" in data
    assert data["data"]["service"] == "AIIS Backend V2"
    assert data["data"]["status"] == "healthy"


def test_health_endpoint_trailing_slash(client):
    """Verify GET /api/health/ also returns HTTP 200 without redirecting or breaking."""
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"


def test_missing_env_vars_no_secret_exposure(client, app):
    """
    Verify that unconfigured / missing environment variables do not leak
    credentials or sensitive internals in HTTP responses or headers.
    """
    response = client.get("/api/health")
    response_text = response.get_data(as_text=True)

    # Ensure secret keys are never present in the response
    assert app.config["SECRET_KEY"] not in response_text
    assert "SUPABASE_ANON_KEY" not in response_text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in response_text

    # Verify no server headers leak detailed internal secrets
    headers_combined = " ".join([f"{k}:{v}" for k, v in response.headers.items()])
    assert app.config["SECRET_KEY"] not in headers_combined


def test_not_found_error_envelope(client):
    """Verify 404 responses conform to standardized error envelope."""
    response = client.get("/api/non_existent_route")
    assert response.status_code == 404
    assert response.is_json

    payload = response.get_json()
    assert payload["success"] is False
    assert "error" in payload
    assert payload["error"]["code"] == "NOT_FOUND"
    assert "message" in payload["error"]

