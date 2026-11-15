"""
AIIS Backend V2 - Stage 4: Hospital Discovery & Details Tests
============================================================
Comprehensive test suite verifying:
- Hospital discovery and listing
- Query filtering by city, specialty, and text search
- GPS proximity radius filtering and distance calculation
- Honest capacity classification ('seeded_baseline', verified_realtime: False)
- Pagination contract (page, limit, total, pages)
- Facility details with hydrated departments, equipment, and capabilities
- 404 handling for unknown facility IDs
- Department network queries (/api/departments and /api/hospitals/<id>/departments)
"""

import pytest
from backend_v2.app import create_app
from backend_v2.config import TestingConfig


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


def test_list_hospitals_all(client):
    """Verify GET /api/hospitals returns 200 with honest capacity metadata and pagination envelope."""
    response = client.get("/api/hospitals")
    assert response.status_code == 200
    assert response.is_json

    body = response.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0

    meta = body["meta"]
    assert meta["total"] >= len(body["data"])
    assert meta["page"] == 1
    assert meta["capacity_source"] == "seeded_baseline"
    assert meta["verified_realtime"] is False

    # Check first hospital structure
    first = body["data"][0]
    assert "id" in first
    assert "name" in first
    assert "city" in first
    assert "capacity_metadata" in first
    assert first["capacity_metadata"]["source"] == "seeded_baseline"
    assert first["capacity_metadata"]["verified_realtime"] is False


def test_list_hospitals_city_filter(client):
    """Verify city filter restricts returned facilities strictly to the target city."""
    response = client.get("/api/hospitals?city=Bengaluru")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    for hosp in body["data"]:
        assert "bengaluru" in hosp["city"].lower()


def test_list_hospitals_text_search(client):
    """Verify text search matches facility name or address."""
    response = client.get("/api/hospitals?search=Victoria")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["data"]) >= 1
    assert any("victoria" in h["name"].lower() for h in body["data"])


def test_list_hospitals_gps_proximity(client):
    """Verify GPS proximity filters within radius and orders by ascending distance."""
    lat, lon = 12.9716, 77.5946
    response = client.get(f"/api/hospitals?latitude={lat}&longitude={lon}&radius=15")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["data"]) > 0

    distances = [h.get("distance_km") for h in body["data"] if "distance_km" in h]
    assert len(distances) > 0
    for d in distances:
        assert d <= 15.0
    assert distances == sorted(distances)


def test_list_hospitals_pagination(client):
    """Verify page and limit query parameters partition results correctly."""
    res_p1 = client.get("/api/hospitals?page=1&limit=5")
    res_p2 = client.get("/api/hospitals?page=2&limit=5")

    assert res_p1.status_code == 200
    assert res_p2.status_code == 200

    body1 = res_p1.get_json()
    body2 = res_p2.get_json()

    assert len(body1["data"]) <= 5
    assert len(body2["data"]) <= 5

    ids_p1 = {h["id"] for h in body1["data"]}
    ids_p2 = {h["id"] for h in body2["data"]}
    assert ids_p1.isdisjoint(ids_p2)


def test_list_hospitals_invalid_coordinates(client):
    """Verify invalid coordinate inputs return 400 validation error."""
    response = client.get("/api/hospitals?latitude=invalid&longitude=77.5")
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_hospital_details_success(client):
    """Verify GET /api/hospitals/1 returns full facility profile with departments, equipment, and capabilities."""
    response = client.get("/api/hospitals/1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True

    data = body["data"]
    assert str(data["id"]) == "1"
    assert "departments" in data
    assert "equipment" in data
    assert "capabilities" in data
    assert isinstance(data["departments"], list)
    assert isinstance(data["equipment"], list)
    assert isinstance(data["capabilities"], list)
    assert data["capacity_metadata"]["source"] == "seeded_baseline"


def test_get_hospital_details_not_found(client):
    """Verify requesting an unrecorded hospital ID returns 404 NOT_FOUND."""
    response = client.get("/api/hospitals/999999")
    assert response.status_code == 404
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_get_hospital_departments(client):
    """Verify GET /api/hospitals/<id>/departments returns department readiness for that facility."""
    response = client.get("/api/hospitals/1/departments")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0


def test_get_network_departments(client):
    """Verify GET /api/departments returns network-wide distinct departments."""
    response = client.get("/api/departments")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert "Emergency & Casualty" in body["data"] or "Cardiology" in body["data"]

