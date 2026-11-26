"""QA Critical Regression Suite (Red -> Green) for P0/P1 findings in WeConnect."""

import os
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
from app.models.material import Material
from app.services.quiz_service.session import create_session, _StoredQuestion
from app.services.neon_storage import neon_storage


@pytest.fixture
def isolated_db():
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
        User(
            user_id=1,
            uni_code="STU001_ID1",
            name="NonAdmin User1",
            email="stu1@weschool.edu.eg",
            password=hash_password("Pass#2026!"),
            type_code="STU",
            level=1,
        ),
        User(
            user_id=10,
            uni_code="ADM010",
            name="Real Admin",
            email="adm10@weschool.edu.eg",
            password=hash_password("AdminPass#2026!"),
            type_code="ADM",
            level=100,
        ),
        User(
            user_id=20,
            uni_code="DR020",
            name="Dr Teacher",
            email="dr20@weschool.edu.eg",
            password=hash_password("DrPass#2026!"),
            type_code="DR",
            level=0,
        ),
        User(
            user_id=30,
            uni_code="STU030",
            name="Ahmed Student",
            email="stu30@weschool.edu.eg",
            password=hash_password("StuPass#2026!"),
            type_code="STU",
            level=2,
        ),
        Material(material_id="CS101", name="Computer Science", description="Core", duration=30),
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


def test_neon_storage_exposes_get_object_contract(monkeypatch):
    """P0 Bug #2: NeonStorageService must implement get_object(key) returning (bytes|None, content_type)."""
    assert hasattr(neon_storage, "get_object"), "NeonStorageService missing get_object()"
    monkeypatch.setattr(neon_storage, "endpoint_url", "")
    data, ctype = neon_storage.get_object("nonexistent/sample.pdf")
    assert data is None
    assert isinstance(ctype, str)


def test_quiz_multiformat_grading_reads_question_type(isolated_db):
    """P0 Bug #3: /quiz/evaluate & /quiz/submit must honor question_type='short_answer' & 'matching'."""
    qs = [
        _StoredQuestion(
            id=1,
            question="ما هو أمر إنشاء فرع في Git؟",
            options={"A": "git checkout -b", "B": "git pull", "C": "git log", "D": "git init"},
            correct="git checkout -b feature-exam",
            explanation="يُستخدم لإنشاء فرع والانتقال إليه",
            question_type="short_answer",
        ),
        _StoredQuestion(
            id=2,
            question="صل الطبقات",
            options={"A": "1:A,2:B", "B": "1:B,2:A", "C": "-", "D": "-"},
            correct="1:A, 2:B",
            explanation="مطابقة صحيحة",
            question_type="matching",
        ),
    ]
    sid = create_session(file_id=0, questions=qs)
    client = TestClient(app)

    r_eval = client.post("/quiz/evaluate", json={"session_id": sid, "question_id": 1, "selected": "git checkout"})
    assert r_eval.status_code == 200
    assert r_eval.json()["correct"] is True, "short_answer grading downgraded to MCQ!"

    r_sub = client.post("/quiz/submit", json={"session_id": sid, "answers": {"1": "git checkout", "2": "2:B, 1:A"}})
    assert r_sub.status_code == 200
    assert r_sub.json()["correct_count"] == 2


def test_assignment_invalid_deadline_returns_422_not_500(isolated_db):
    """P1 Bug #7: Invalid ISO deadline on POST /assignments must return 422, not 500."""
    dr_hdr = {"Authorization": f"Bearer {create_access_token({'sub': '20', 'type': 'DR'})}"}
    client = TestClient(app, raise_server_exceptions=False)
    res = client.post(
        "/assignments",
        data={
            "material_id": "CS101",
            "title": "Bad Deadline Test",
            "deadline": "not-a-valid-date",
        },
        headers=dr_hdr,
    )
    assert res.status_code == 422


def test_attendance_teacher_actions_reject_student_role(isolated_db):
    """P0 Bug #4: Student role MUST be rejected (403) from teacher attendance & gradebook endpoints."""
    stu_hdr = {"Authorization": f"Bearer {create_access_token({'sub': '30', 'type': 'STU'})}"}
    client = TestClient(app)

    r1 = client.post("/attendance/sessions", json={"material_id": "CS101", "title": "Rogue"}, headers=stu_hdr)
    assert r1.status_code == 403

    r2 = client.get("/attendance/courses/CS101/export-gradebook", headers=stu_hdr)
    assert r2.status_code == 403

    r3 = client.get("/attendance/courses/CS101/analytics/weakness-heatmap", headers=stu_hdr)
    assert r3.status_code == 403

    r4 = client.get("/attendance/sessions/1/live-qr", headers=stu_hdr)
    assert r4.status_code == 403


def test_attendance_public_summary_no_partial_name_enumeration(isolated_db):
    """P0 Bug #5: /attendance/public-summary/{id} must NOT enumerate users via partial name like 'a'."""
    client = TestClient(app)
    res = client.get("/attendance/public-summary/Ahmed")
    assert res.status_code == 404
    res_exact = client.get("/attendance/public-summary/STU030")
    assert res_exact.status_code == 200


def test_require_admin_role_rejects_user_id_1_when_not_adm(isolated_db):
    """P0 Bug #4: user_id == 1 with type_code='STU' must NOT bypass require_admin_role."""
    stu1_hdr = {"Authorization": f"Bearer {create_access_token({'sub': '1', 'type': 'STU'})}"}
    client = TestClient(app)
    res = client.post("/materials", json={"material_id": "X999", "name": "Hacked"}, headers=stu1_hdr)
    assert res.status_code == 403


def test_storage_sync_purge_and_cron_require_auth(isolated_db, monkeypatch):
    """P0 Bug #5: Anonymous callers cannot trigger /admin/api/storage/sync, purge, or /api/cron/quarantine-purge when CRON_SECRET is set."""
    client = TestClient(app)
    assert client.post("/admin/api/storage/sync").status_code == 403
    assert client.post("/admin/api/storage/quarantine/purge").status_code == 403

    monkeypatch.setenv("CRON_SECRET", "super-cron-secret-2026")
    assert client.get("/api/cron/quarantine-purge").status_code == 401
    assert client.post("/api/cron/quarantine-purge", headers={"Authorization": "Bearer super-cron-secret-2026"}).status_code == 200


def test_storage_command_center_includes_csrf_and_xss_escape():
    """P1 Bug #6: storage_command_center.html must attach X-CSRF-Token cookie and escapeHtml()."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "app", "templates", "storage_command_center.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "X-CSRF-Token" in html
    assert "escapeHtml" in html


def test_logout_revokes_bearer_token(isolated_db):
    """P1 Bug #8: Logging out with a Bearer token blacklists it for subsequent /users/me calls."""
    token = create_access_token({"sub": "30", "type": "STU"})
    hdr = {"Authorization": f"Bearer {token}"}
    client = TestClient(app)
    assert client.get("/users/me", headers=hdr).status_code == 200
    assert client.post("/auth/logout", headers=hdr).status_code == 200
    assert client.get("/users/me", headers=hdr).status_code == 401
