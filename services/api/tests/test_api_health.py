"""Basic endpoint tests for Content Repurposing API."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

def test_root_endpoint():
    """Verify service root returns 200 and running status."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "content-repurposing-api"
    assert data["status"] == "running"

def test_api_health_endpoint():
    """Verify simple health check returns healthy status."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "api"
