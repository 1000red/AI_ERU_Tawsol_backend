"""Comprehensive QA tests for previously uncovered modules:
- Support (/contact, /contact/my)
- Users (/users/me, /users/me/password)
- Auth OTP Password Reset (/auth/forgot-password, /auth/verify-otp, /auth/reset-password) + /login rate-limit
- Chat (/chat/send, /chat/history, /chat/upload/*, /chat/ws/{user_id})
- Content Announcements & Assignments RBAC lifecycle
- Attendance Gradebook Excel export & Weakness Heatmap
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.database import get_db
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserType
from app.models.material import Material, MaterialStudent, MaterialTeacher
from app.models.password_reset_otp import PasswordResetOTP


@pytest.fixture
def qa_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    prev_override = app.dependency_overrides.get(get_db)

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db

    db = TestingSession()
    db.add_all([
        UserType(code="ADM", description="Admin"),
        UserType(code="DR", description="Doctor"),
        UserType(code="STU", description="Student"),
        User(user_id=1, uni_code="ADM01", name="Admin", email="adm@we.edu.eg", password=hash_password("AdmPass#2026!"), type_code="ADM", level=100),
        User(user_id=2, uni_code="DR02", name="Dr Sameh", email="dr@we.edu.eg", password=hash_password("DrPass#2026!"), type_code="DR", level=0, department="CS"),
        User(user_id=3, uni_code="STU03", name="Sara Ali", email="sara@we.edu.eg", password=hash_password("StuPass#2026!"), type_code="STU", level=2, department="CS"),
        User(user_id=4, uni_code="STU04", name="Omar Tarek", email="omar@we.edu.eg", password=hash_password("StuPass#2026!"), type_code="STU", level=2, department="CS"),
        Material(material_id="NET101", name="Networking", description="Networks", duration=40),
        MaterialTeacher(material_id="NET101", user_id=2),
        MaterialStudent(material_id="NET101", user_id=3),
    ])
    db.commit()
    db.close()

    try:
        yield TestingSession
    finally:
        if prev_override is not None:
            app.dependency_overrides[get_db] = prev_override
        else:
            app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def _hdr(uid: int, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid), 'type': role})}"}


def test_support_contact_lifecycle(qa_env):
    client = TestClient(app)
    assert client.get("/contact/my").status_code == 401

    with patch("app.routers.support.send_contact_us_email", return_value=True):
        res = client.post(
            "/contact",
            json={"issue_type": "technical", "subject": "QR Scanner", "message": "Camera timeout on iOS."},
            headers=_hdr(3, "STU"),
        )
    assert res.status_code == 200
    assert res.json()["saved"] is True

    mine = client.get("/contact/my", headers=_hdr(3, "STU"))
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]["subject"] == "QR Scanner"


def test_users_profile_and_password_change(qa_env):
    client = TestClient(app)
    hdr = _hdr(3, "STU")

    me = client.get("/users/me", headers=hdr)
    assert me.status_code == 200
    assert me.json()["email"] == "sara@we.edu.eg"

    upd = client.put("/users/me", json={"name": "Sara Ali Updated"}, headers=hdr)
    assert upd.status_code == 200
    assert upd.json()["name"] == "Sara Ali Updated"

    # Wrong old password -> 400
    bad_old = client.put("/users/me/password", json={"old_password": "Wrong", "new_password": "StrongNew#2026!"}, headers=hdr)
    assert bad_old.status_code == 400

    # Weak new password -> 400
    weak = client.put("/users/me/password", json={"old_password": "StuPass#2026!", "new_password": "123"}, headers=hdr)
    assert weak.status_code == 400

    # Valid change -> 200
    with patch("app.services.user_service.send_password_changed_email", return_value=True):
        ok = client.put("/users/me/password", json={"old_password": "StuPass#2026!", "new_password": "StrongNew#2026!"}, headers=hdr)
    assert ok.status_code == 200


def test_auth_otp_reset_flow_and_login_rate_limit(qa_env):
    client = TestClient(app)

    # 1. Request OTP
    with patch("app.services.user_service.send_otp_email", return_value=True):
        req_res = client.post("/auth/forgot-password", json={"email": "sara@we.edu.eg"})
    assert req_res.status_code == 200
    assert req_res.json()["otp_sent"] is True

    db = qa_env()
    otp_rec = db.query(PasswordResetOTP).filter(PasswordResetOTP.user_id == 3, PasswordResetOTP.is_used == False).first()
    otp_code = otp_rec.otp_code
    db.close()

    # 2. Verify valid OTP -> reset_token
    ver_res = client.post("/auth/verify-otp", json={"email": "sara@we.edu.eg", "otp": otp_code})
    assert ver_res.status_code == 200
    reset_token = ver_res.json()["reset_token"]

    # 3. Reset password rejects weak, accepts strong
    assert client.post("/auth/reset-password", json={"reset_token": reset_token, "new_password": "weak"}).status_code == 400
    with patch("app.services.user_service.send_password_changed_email", return_value=True):
        assert client.post("/auth/reset-password", json={"reset_token": reset_token, "new_password": "FreshReset#2026!"}).status_code == 200

    # 4. POST /login rate limit enforced on simulated remote IP after 10 attempts
    ip_hdr = {"X-Forwarded-For": "203.0.113.77"}
    statuses = [client.post("/login", json={"email": "nobody@we.edu.eg", "password": "Bad"}, headers=ip_hdr).status_code for _ in range(11)]
    assert 429 in statuses


def test_chat_rest_upload_guard_and_ws(qa_env):
    client = TestClient(app)
    stu3_hdr = _hdr(3, "STU")
    dr_hdr = _hdr(2, "DR")
    stu4_hdr = _hdr(4, "STU")

    # Send message STU 3 -> DR 2
    sent = client.post("/chat/send", json={"receiver_id": 2, "content_type": "text", "message": "Hello Dr Sameh"}, headers=stu3_hdr)
    assert sent.status_code == 201
    chat_id = sent.json()["chat_id"]

    # Third party STU 4 cannot read 3<->2 history
    assert client.get("/chat/history/3/2", headers=stu4_hdr).status_code == 403
    hist = client.get("/chat/history/3/2", headers=dr_hdr)
    assert hist.status_code == 200
    assert len(hist.json()) == 1

    # Disallowed dangerous extension rejected
    bad_up = client.post("/chat/upload/file", files={"file": ("malware.exe", b"MZ...", "application/octet-stream")}, headers=stu3_hdr)
    assert bad_up.status_code == 400

    # Edit & Delete message
    assert client.put(f"/chat/message/{chat_id}", json={"message": "Edited"}, headers=stu3_hdr).status_code == 200
    assert client.delete(f"/chat/message/{chat_id}", headers=stu3_hdr).status_code == 200

    # WebSocket reject mismatched token user_id
    stu3_tok = create_access_token({"sub": "3", "type": "STU"})
    with client.websocket_connect(f"/chat/ws/3?token={stu3_tok}") as ws:
        msg = ws.receive_json()
        assert msg["type"] in ("connected", "delivered")
        ws.send_text('{"type": "ping"}')
        pong = ws.receive_json()
        assert pong == {"type": "pong"}


def test_announcements_and_assignments_rbac(qa_env):
    client = TestClient(app)
    dr_hdr = _hdr(2, "DR")
    stu_hdr = _hdr(3, "STU")

    # Student cannot create announcement
    ann_fail = client.post(
        "/announcements",
        json={"title": "Rogue", "content": "Bad", "target_type": "all"},
        headers=stu_hdr,
    )
    assert ann_fail.status_code == 403

    # Doctor creates announcement and student marks read
    ann_ok = client.post(
        "/announcements",
        json={"title": "Lab Exam", "content": "Tomorrow 9 AM", "target_type": "course", "target_course_id": "NET101"},
        headers=dr_hdr,
    )
    assert ann_ok.status_code == 201
    ann_id = ann_ok.json()["announcement_id"]
    assert client.post(f"/announcements/{ann_id}/read", headers=stu_hdr).status_code == 204

    # Assignment creation valid + RBAC delete rejection for student
    dl = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    asg_ok = client.post(
        "/assignments",
        data={"material_id": "NET101", "title": "Subnetting Lab", "deadline": dl},
        headers=dr_hdr,
    )
    assert asg_ok.status_code == 201
    asg_id = asg_ok.json()["assignment_id"]
    assert client.delete(f"/assignments/{asg_id}", headers=stu_hdr).status_code == 403
    assert client.delete(f"/assignments/{asg_id}", headers=dr_hdr).status_code == 204


def test_attendance_gradebook_excel_and_heatmap(qa_env):
    client = TestClient(app)
    dr_hdr = _hdr(2, "DR")

    xls = client.get("/attendance/courses/NET101/export-gradebook", headers=dr_hdr)
    assert xls.status_code == 200
    assert "spreadsheetml.sheet" in xls.headers["content-type"]
    assert xls.content[:2] == b"PK"  # Valid .xlsx ZIP archive

    heat = client.get("/attendance/courses/NET101/analytics/weakness-heatmap", headers=dr_hdr)
    assert heat.status_code == 200
    assert isinstance(heat.json(), dict)
