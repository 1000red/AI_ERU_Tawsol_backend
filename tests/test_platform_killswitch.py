"""Comprehensive tests for the Admin Panel Platform Kill-Switch / Maintenance Mode."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.platform_control import DEFAULT_MAINTENANCE_MESSAGE
from app.models.user import User, UserType
from app.services.platform_service import clear_platform_status_cache


@pytest.fixture()
def test_ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.add_all([
        UserType(code="ADM", description="Admin"),
        UserType(code="DR", description="Doctor"),
        UserType(code="STU", description="Student"),
    ])
    pwd = hash_password("TestPass123!")
    db.add_all([
        User(
            user_id=1,
            uni_code="ADM001",
            name="Admin WE",
            email="admin@weschool.test",
            password=pwd,
            level=0,
            type_code="ADM",
        ),
        User(
            user_id=2,
            uni_code="DR001",
            name="Dr. Ahmed",
            email="teacher@weschool.test",
            password=pwd,
            level=0,
            type_code="DR",
        ),
        User(
            user_id=3,
            uni_code="STU001",
            name="Student Ali",
            email="student@weschool.test",
            password=pwd,
            level=2,
            type_code="STU",
        ),
    ])
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    clear_platform_status_cache()

    client = TestClient(app)
    tokens = {
        "adm": create_access_token({"sub": "1", "type": "ADM"}),
        "dr": create_access_token({"sub": "2", "type": "DR"}),
        "stu": create_access_token({"sub": "3", "type": "STU"}),
    }

    try:
        yield client, tokens
    finally:
        clear_platform_status_cache()
        if prev_override is not None:
            app.dependency_overrides[get_db] = prev_override
        else:
            app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_default_platform_is_active(test_ctx):
    client, tokens = test_ctx

    res = client.get("/platform/status")
    assert res.status_code == 200
    body = res.json()
    assert body["is_active"] is True
    assert body["maintenance_mode"] is False
    assert body["stopped_at"] is None
    assert "updated_by" not in body
    assert "updated_by_name" not in body

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    # Normal endpoints work
    assert client.get("/").status_code == 200
    assert client.get("/users/me", headers={"Authorization": f"Bearer {tokens['stu']}"}).status_code == 200


def test_killswitch_authorization_guards(test_ctx):
    client, tokens = test_ctx

    # Unauthenticated blocked
    assert client.get("/admin/api/platform/status").status_code == 403
    assert client.put("/admin/api/platform/status", json={"is_active": False}).status_code == 403
    assert client.post("/admin/api/platform/status", json={"is_active": False}).status_code == 403

    # Student blocked
    assert client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['stu']}"},
        json={"is_active": False},
    ).status_code == 403

    # Teacher blocked
    assert client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['dr']}"},
        json={"is_active": False},
    ).status_code == 403

    # Admin JWT allowed
    res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": "صيانة مجدولة"},
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False
    assert res.json()["updated_by"] == 1
    assert res.json()["updated_by_name"] == "Admin WE"

    # Admin X-Admin-Key via POST allowed to resume
    res2 = client.post(
        "/admin/api/platform/status",
        headers={"X-Admin-Key": settings.SECRET_KEY},
        json={"is_active": True},
    )
    assert res2.status_code == 200
    assert res2.json()["is_active"] is True
    assert res2.json()["stopped_at"] is None


def test_stop_blocks_non_admin_and_allows_admin_and_resumes_cleanly(test_ctx):
    client, tokens = test_ctx
    custom_msg = "المنصة متوقفة مؤقتاً للصيانة الطارئة حتى الساعة 6 مساءً"

    # 1. Admin stops platform
    stop_res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": custom_msg},
    )
    assert stop_res.status_code == 200
    stop_data = stop_res.json()
    assert stop_data["is_active"] is False
    assert stop_data["maintenance_mode"] is True
    assert stop_data["maintenance_message"] == custom_msg
    assert stop_data["stopped_at"] is not None

    # 2. Public status & health remain accessible and reflect stopped state
    pub = client.get("/platform/status")
    assert pub.status_code == 200
    assert pub.json()["is_active"] is False
    assert pub.json()["maintenance_mode"] is True
    assert pub.json()["maintenance_message"] == custom_msg
    assert "updated_by_name" not in pub.json()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    # 3. JSON API endpoints return 503 with maintenance metadata
    for path in ["/", "/users/me", "/courses", "/materials"]:
        r = client.get(
            path,
            headers={
                "Authorization": f"Bearer {tokens['stu']}",
                "Accept": "application/json",
            },
        )
        assert r.status_code == 503, f"Expected 503 on {path}, got {r.status_code}"
        payload = r.json()
        assert payload["maintenance_mode"] is True
        assert payload["is_active"] is False
        assert payload["error"] == "platform_stopped"
        assert payload["detail"] == custom_msg
        assert r.headers.get("retry-after") == "60"

    # 4. Browser HTML portals return branded 503 Maintenance HTML page
    for portal_path in ["/teacher", "/checkin", "/"]:
        r = client.get(portal_path, headers={"Accept": "text/html"})
        assert r.status_code == 503, f"Expected 503 HTML on {portal_path}, got {r.status_code}"
        assert "text/html" in r.headers.get("content-type", "")
        assert custom_msg in r.text
        assert "مدرسة WE للتكنولوجيا التطبيقية بالسويس" in r.text

    # 5. Login rules while stopped:
    # - Admin CAN still log in (so admin is never locked out!)
    adm_login = client.post(
        "/auth/login",
        json={"email": "admin@weschool.test", "password": "TestPass123!"},
    )
    assert adm_login.status_code == 200
    assert adm_login.json()["user"]["type_code"] == "ADM"

    # - Student CANNOT log in -> 503 with full maintenance metadata & headers
    stu_login = client.post(
        "/auth/login",
        json={"email": "student@weschool.test", "password": "TestPass123!"},
    )
    assert stu_login.status_code == 503
    stu_payload = stu_login.json()
    assert stu_payload["detail"] == custom_msg
    assert stu_payload["error"] == "platform_stopped"
    assert stu_payload["maintenance_mode"] is True
    assert stu_payload["is_active"] is False
    assert stu_payload["stopped_at"] is not None
    assert stu_login.headers.get("retry-after") == "60"
    assert stu_login.headers.get("cache-control") == "no-store"

    # - Teacher CANNOT log in via /login alias either -> 503 with full metadata
    dr_login = client.post(
        "/login",
        json={"email": "teacher@weschool.test", "password": "TestPass123!"},
    )
    assert dr_login.status_code == 503
    assert dr_login.json()["maintenance_mode"] is True
    assert dr_login.json()["error"] == "platform_stopped"

    # - Bad credentials still return 401 (no role/user enumeration)
    bad_login = client.post(
        "/auth/login",
        json={"email": "student@weschool.test", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # 6. Admin panel & admin APIs stay 100% accessible while stopped
    assert client.get("/admin", headers={"Accept": "text/html"}).status_code == 200
    assert client.get("/dashboard", headers={"Accept": "text/html"}).status_code == 200
    assert client.get("/users-management", headers={"Accept": "text/html"}).status_code == 200
    assert client.get("/users", headers={"Accept": "text/html"}).status_code == 200
    assert client.get(
        "/admin/api/stats",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
    ).status_code == 200

    # 7. Vercel __orig_path rewrite still allows admin API and blocks non-admin API
    v_admin = client.get(
        "/api/index.py?__orig_path=/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
    )
    assert v_admin.status_code == 200
    assert v_admin.json()["is_active"] is False

    v_blocked = client.get(
        "/api/index.py?__orig_path=/users/me",
        headers={"Authorization": f"Bearer {tokens['stu']}", "Accept": "application/json"},
    )
    assert v_blocked.status_code == 503

    # 8. CORS preflight OPTIONS bypasses maintenance middleware
    opt = client.options(
        "/users/me",
        headers={
            "Origin": "https://ai-eru-tawsol-backend-weschool.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert opt.status_code in (200, 204)

    # 9. Admin resumes platform -> everything works again!
    resume_res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": True},
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["is_active"] is True
    assert resume_res.json()["stopped_at"] is None

    assert client.get("/").status_code == 200
    assert client.get("/teacher", headers={"Accept": "text/html"}).status_code == 200
    assert client.get("/checkin", headers={"Accept": "text/html"}).status_code == 200
    assert client.get("/users/me", headers={"Authorization": f"Bearer {tokens['stu']}"}).status_code == 200
    assert client.post(
        "/auth/login",
        json={"email": "student@weschool.test", "password": "TestPass123!"},
    ).status_code == 200


def test_maintenance_html_escapes_xss_and_handles_blank_message(test_ctx):
    client, tokens = test_ctx

    # XSS attempt in maintenance message must be escaped in HTML response
    xss_msg = '<script>alert("xss")</script> صيانة'
    res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": xss_msg},
    )
    assert res.status_code == 200

    html_res = client.get("/teacher", headers={"Accept": "text/html"})
    assert html_res.status_code == 503
    assert '<script>alert("xss")</script>' not in html_res.text
    assert "&lt;script&gt;" in html_res.text

    # Blank message falls back to default message
    res_blank = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": "   "},
    )
    assert res_blank.status_code == 200
    assert res_blank.json()["maintenance_message"] == DEFAULT_MAINTENANCE_MESSAGE

    # Over-length message (>1000 chars) rejected with 422
    res_long = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": "a" * 1001},
    )
    assert res_long.status_code == 422


def test_websockets_blocked_when_platform_stopped(test_ctx):
    client, tokens = test_ctx

    # Stop platform
    res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": "إيقاف فوري للشات"},
    )
    assert res.status_code == 200

    # Student chat WebSocket receives maintenance error and closes with 1013
    with client.websocket_connect(f"/chat/ws/3?token={tokens['stu']}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["maintenance_mode"] is True
        assert msg["detail"] == "إيقاف فوري للشات"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
        assert exc_info.value.code == 1013

    # Student announcements WebSocket receives maintenance JSON and closes with 1013
    with client.websocket_connect(f"/announcements/ws/3?token={tokens['stu']}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["error"] == "platform_stopped"
        assert msg["maintenance_mode"] is True
        assert msg["detail"] == "إيقاف فوري للشات"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
        assert exc_info.value.code == 1013


def test_path_traversal_and_encoded_bypasses_blocked(test_ctx):
    client, tokens = test_ctx

    # Stop platform
    res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {tokens['adm']}"},
        json={"is_active": False, "maintenance_message": "صيانة أمنية"},
    )
    assert res.status_code == 200

    bypass_attempts = [
        "/admin/../users/me",
        "/api/index.py?__orig_path=/admin/../users/me",
        "/api/index.py?__orig_path=/admin/..//users/me",
        "/admin/%2e%2e/users/me",
        "/admin/..",
        "//users/me",
        "/uploads/secret.txt",
        "/docs",
        "/openapi.json",
    ]
    for path in bypass_attempts:
        r = client.get(
            path,
            headers={"Authorization": f"Bearer {tokens['stu']}", "Accept": "application/json"},
        )
        assert r.status_code == 503, f"Path {path} bypassed maintenance middleware with {r.status_code}"
        assert r.json()["maintenance_mode"] is True


def test_announcements_ws_mid_session_stop_and_disconnect_all(test_ctx):
    import asyncio
    from unittest.mock import AsyncMock
    from app.services.chat_service import ConnectionManager
    from app.websockets.announcement_ws import AnnouncementConnectionManager

    client, tokens = test_ctx

    # 1. Connect student to announcements WS while platform is active, then stop mid-session
    with client.websocket_connect(f"/announcements/ws/3?token={tokens['stu']}") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"

        # Stop platform via DB directly (simulating another serverless instance)
        from app.services.platform_service import set_platform_status, resolve_db_session_for_app
        with resolve_db_session_for_app(app) as db:
            set_platform_status(db, is_active=False, maintenance_message="إيقاف أثناء الجلسة", admin_id=1)

        # Next message from student triggers maintenance error + 1013 close
        ws.send_text("ping")
        msg = ws.receive_json()
        assert msg["maintenance_mode"] is True
        assert msg["detail"] == "إيقاف أثناء الجلسة"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
        assert exc_info.value.code == 1013

    # 2. disconnect_all() sends maintenance payload and closes non-admin sockets while sparing admins
    async def _check_managers():
        cm = ConnectionManager()
        am = AnnouncementConnectionManager()
        stu_ws1, adm_ws1 = AsyncMock(), AsyncMock()
        stu_ws2, adm_ws2 = AsyncMock(), AsyncMock()
        cm.connect(3, stu_ws1, is_admin=False)
        cm.connect(1, adm_ws1, is_admin=True)
        am.connect(3, stu_ws2, is_admin=False)
        am.connect(1, adm_ws2, is_admin=True)

        c1 = await cm.disconnect_all(maintenance_message="إيقاف فوري")
        c2 = await am.disconnect_all(maintenance_message="إيقاف فوري")
        assert c1 == 1 and c2 == 1
        stu_ws1.send_json.assert_awaited_once()
        stu_ws1.close.assert_awaited_once_with(code=1013, reason="Platform temporarily stopped")
        adm_ws1.close.assert_not_awaited()
        stu_ws2.send_json.assert_awaited_once()
        stu_ws2.close.assert_awaited_once_with(code=1013, reason="Platform temporarily stopped")
        adm_ws2.close.assert_not_awaited()

    asyncio.run(_check_managers())


def test_html_portals_include_killswitch_and_lockout_ui(test_ctx):
    client, _ = test_ctx

    admin_html = client.get("/admin").text
    assert "platform-killswitch-card" in admin_html
    assert "modal-platform-killswitch" in admin_html
    assert "submitPlatformStatusChange" in admin_html

    dash_html = client.get("/dashboard").text
    assert "platform-control-card" in dash_html
    assert "togglePlatformStatus" in dash_html
    assert "/admin/api/platform/status" in dash_html
    assert "!window.location.origin.includes('localhost')" not in dash_html

    teacher_html = client.get("/teacher").text
    assert "platform-stopped-overlay" in teacher_html
    assert "checkPlatformOperationalStatus" in teacher_html
    assert "installPlatformMaintenanceInterceptor" in teacher_html
    assert "function escapeHtml(" in teacher_html
    assert "this.dataset.fileTitle" in teacher_html
    assert "'${escapeHtml(f.title)}'" not in teacher_html
    assert "'${escapeHtml(fileTitle)}'" not in teacher_html

    checkin_html = client.get("/checkin").text
    assert "platform-stopped-overlay" in checkin_html
    assert "checkPlatformOperationalStatus" in checkin_html
    assert "installPlatformMaintenanceInterceptor" in checkin_html
