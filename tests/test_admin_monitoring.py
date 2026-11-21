import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_admin_endpoints_require_admin():
    # Attempting to call without admin token or key should return 403
    endpoints = [
        "/admin/api/overview",
        "/admin/api/chats/stats",
        "/admin/api/chats/conversations",
        "/admin/api/quizzes/stats",
        "/admin/api/quizzes/logs",
        "/admin/api/attendance/sessions",
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 403, f"Endpoint {ep} should require admin access"


def test_admin_gateway_endpoint():
    res = client.get("/admin")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "operational"
    assert "/admin/api" in data["api_endpoints"]
    assert client.get("/users-management").status_code in (404, 503)
