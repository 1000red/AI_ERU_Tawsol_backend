"""Individual Function-by-Function QA Verification for Challenge Arena & Department Material Uploads."""

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
from app.models.content.material_file import MaterialFile


@pytest.fixture
def arena_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    prev = app.dependency_overrides.get(get_db)

    def _db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    db = TestingSession()
    db.add_all([
        UserType(code="DR", description="Doctor"),
        UserType(code="TA", description="Engineer / TA"),
        UserType(code="STU", description="Student"),
        User(user_id=2, uni_code="ENG02", name="Eng. Khaled", email="eng@we.edu.eg", password=hash_password("EngPass#2026!"), type_code="TA", level=0, department="IT & Networks"),
        User(user_id=3, uni_code="STU03", name="Nour Student", email="nour@we.edu.eg", password=hash_password("StuPass#2026!"), type_code="STU", level=2, department="IT & Networks"),
        Material(material_id="C1", name="Networking Fundamentals", description="OSI & TCP/IP", duration=40),
        Material(material_id="C5", name="Programming C5", description="Python Software Engineering", duration=48),
        Material(material_id="B3", name="AI Systems", description="Machine Learning & Data", duration=36),
        MaterialTeacher(material_id="C1", user_id=2),
        MaterialStudent(material_id="C1", user_id=3),
    ])
    db.commit()
    db.close()

    try:
        yield TestingSession
    finally:
        if prev is not None:
            app.dependency_overrides[get_db] = prev
        else:
            app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def test_01_arena_courses_and_department_filtering(arena_db):
    client = TestClient(app)

    all_res = client.get("/api/v1/games/courses")
    assert all_res.status_code == 200
    all_courses = all_res.json()
    assert len(all_courses) == 3
    assert all("department" in c for c in all_courses)

    # Filter IT & Networks
    it_res = client.get("/api/v1/games/courses", params={"department": "IT & Networks"})
    assert it_res.status_code == 200
    assert [c["material_id"] for c in it_res.json()] == ["C1"]

    # Switch to Programming & Software
    prog_res = client.get("/api/v1/games/courses", params={"department": "Programming & Software"})
    assert prog_res.status_code == 200
    assert [c["material_id"] for c in prog_res.json()] == ["C5"]

    # Switch to AI & Data Science
    ai_res = client.get("/api/v1/games/courses", params={"department": "AI & Data Science"})
    assert ai_res.status_code == 200
    assert [c["material_id"] for c in ai_res.json()] == ["B3"]


def test_02_arena_upload_course_file_for_engineer_department_and_rbac(arena_db):
    client = TestClient(app)
    eng_hdr = {"Authorization": f"Bearer {create_access_token({'sub': '2', 'type': 'TA'})}"}
    stu_hdr = {"Authorization": f"Bearer {create_access_token({'sub': '3', 'type': 'STU'})}"}

    sample_py = b"def subnet_mask(cidr: int) -> str:\n    return '255.255.255.0'\n"

    # Student rejected 403
    r_stu = client.post(
        "/api/v1/games/upload-course-file",
        data={"material_id": "C5", "title": "Rogue Lab"},
        files={"file": ("lab.py", sample_py, "text/x-python")},
        headers=stu_hdr,
    )
    assert r_stu.status_code == 403

    # Engineer uploads .py material to selected department course C5
    with patch("app.routers.content._helpers.neon_storage.endpoint_url", ""):
        r_ok = client.post(
            "/api/v1/games/upload-course-file",
            data={"material_id": "C5", "title": "Python Lab 1"},
            files={"file": ("lab1.py", sample_py, "text/x-python")},
            headers=eng_hdr,
        )
    assert r_ok.status_code == 201
    created = r_ok.json()
    assert created["material_id"] == "C5"
    assert created["title"] == "Python Lab 1"

    # Verify it appears immediately in /api/v1/games/files/C5
    files_res = client.get("/api/v1/games/files/C5")
    assert files_res.status_code == 200
    titles = [f["title"] for f in files_res.json()]
    assert "Python Lab 1" in titles


def test_03_arena_all_game_modes_and_material_all_generation(arena_db):
    client = TestClient(app)
    db = arena_db()
    db.add(MaterialFile(
        material_id="C1",
        author_id=2,
        title="OSI Layers Lecture",
        description="OSI model defines 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, Application. TCP ensures reliable delivery.",
        file_type="text",
        file_path="",
        file_size=120,
    ))
    db.commit()
    db.close()

    for mode in ("speed_challenge", "rapid_tf", "step_order", "bug_lab", "deep_mastery"):
        res = client.post(
            "/api/v1/games/generate-from-file",
            data={"material_id": "C1", "num_questions": 4, "difficulty": "applied", "mode": mode},
        )
        assert res.status_code == 200, f"Mode {mode} failed: {res.text}"
        qs = res.json()["pack"]["questions"]
        assert len(qs) >= 1


def test_04_arena_students_attempts_and_ledger_flow(arena_db):
    client = TestClient(app)

    stu_res = client.get("/api/v1/games/students/C1")
    assert stu_res.status_code == 200
    assert any(s["name"] == "Nour Student" for s in stu_res.json())

    att_res = client.post(
        "/api/v1/games/attempts",
        json={
            "student_name": "Nour Student",
            "topic": "OSI 7-Layers",
            "points_earned": 1250,
            "accuracy": 95,
            "awarded_crown": True,
            "course_id": "C1",
        },
    )
    assert att_res.status_code == 200
    assert att_res.json()["crown_awarded"] is True

    led_res = client.get("/api/v1/games/ledger")
    assert led_res.status_code == 200
    assert led_res.json()["status"] == "success"
    assert any(row["name"] == "Nour Student" and row["totalPoints"] >= 1250 for row in led_res.json()["ledger"])
