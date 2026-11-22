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


def test_admin_html_endpoints():
    res = client.get("/admin")
    assert res.status_code == 200
    assert "لوحة التحكم" in res.text

    res_users = client.get("/users-management")
    assert res_users.status_code == 200
    assert "لوحة التحكم" in res_users.text
