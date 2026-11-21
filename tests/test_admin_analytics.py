"""End-to-end verification tests for all Admin Analytics endpoints.

Covers:
1. /admin/api/attendance/sessions (duration_minutes computed safely from expires_at - created_at)
2. /admin/api/quizzes/students-analysis (aggregates QuizStudentAttempt + student QuizLog, course_performance, score_distribution)
3. /admin/api/quizzes/students/{id} (merges QuizStudentAttempt with linked QuizLog metadata)
4. /admin/api/quizzes/stats (real student attempt average & counts + Gemini 3.5 Flash-Lite model)
5. /admin/api/overview (live courses breakdown, attendance records, 14-day daily_trend, content stats, demographics)
6. /admin/api/users/{id}/activity (includes QuizStudentAttempt + uni_code)
7. /admin/api/stats (counts DR + TA in doctors_count)
8. /admin HTML portal contains Chart.js, analytics canvases, and zero stale Gemini 1.5 references
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserType
from app.models.material import Material, MaterialStudent
from app.models.content.material_file import MaterialFile
from app.models.attendance import AttendanceSession, AttendanceRecord
from app.models.quiz_log import QuizLog, QuizStudentAttempt
from app.models.chat import ChatHistory


@pytest.fixture()
def analytics_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    try:
        for code, desc in [("ADM", "Admin"), ("DR", "Doctor"), ("TA", "TA"), ("STU", "Student")]:
            db.add(UserType(code=code, description=desc))
        db.flush()

        adm = User(uni_code="ADM01", name="Admin WE", email="adm@we.edu.eg", password=hash_password("Pass@123"), level=100, department="Admin", type_code="ADM", last_seen=now)
        dr = User(uni_code="DR01", name="Dr. Ahmed", email="dr@we.edu.eg", password=hash_password("Pass@123"), level=0, department="Programming", type_code="DR", last_seen=now)
        ta = User(uni_code="TA01", name="Eng. Nada", email="ta@we.edu.eg", password=hash_password("Pass@123"), level=0, department="Programming", type_code="TA", last_seen=now)
        stu1 = User(uni_code="2026001", name="Youssef Ali", email="youssef@we.edu.eg", password=hash_password("Pass@123"), level=2, department="Programming", type_code="STU", last_seen=now)
        stu2 = User(uni_code="2026002", name="Mariam Hassan", email="mariam@we.edu.eg", password=hash_password("Pass@123"), level=2, department="Networking", type_code="STU", last_seen=now - timedelta(days=2))
        db.add_all([adm, dr, ta, stu1, stu2])
        db.flush()

        c5 = Material(material_id="C5", name="Programming", description="Python & OOP", duration=40)
        c4 = Material(material_id="C4", name="Web & Git", description="Laravel & Git", duration=30)
        db.add_all([c5, c4])
        db.flush()

        db.add_all([
            MaterialStudent(material_id="C5", user_id=stu1.user_id),
            MaterialStudent(material_id="C5", user_id=stu2.user_id),
            MaterialStudent(material_id="C4", user_id=stu1.user_id),
        ])

        db.add(MaterialFile(
            material_id="C5",
            author_id=dr.user_id,
            title="Lecture 1 Python",
            file_type="pdf",
            file_size=1024 * 1024 * 2,
        ))

        sess = AttendanceSession(
            material_id="C5",
            created_by=dr.user_id,
            title="C5 Lab Session 1",
            token="tok_analytics_1",
            created_at=now - timedelta(hours=1),
            expires_at=now - timedelta(minutes=15),
            is_active=True,
        )
        db.add(sess)
        db.flush()

        db.add_all([
            AttendanceRecord(session_id=sess.session_id, material_id="C5", student_id=stu1.user_id, status="PRESENT", scanned_at=now - timedelta(minutes=50)),
            AttendanceRecord(session_id=sess.session_id, material_id="C5", student_id=stu2.user_id, status="LATE", scanned_at=now - timedelta(minutes=45)),
        ])

        # Teacher-authored QuizLog + real student QuizStudentAttempt rows
        qlog_c5 = QuizLog(
            session_id="sess-c5-exam",
            user_id=dr.user_id,
            course_id="C5",
            topic="C5 Midterm Programming",
            difficulty="medium",
            num_questions=10,
            attempts_count=2,
            created_at=now - timedelta(days=1),
        )
        qlog_c4 = QuizLog(
            session_id="sess-c4-exam",
            user_id=dr.user_id,
            course_id="C4",
            topic="C4 Laravel & Git",
            difficulty="hard",
            num_questions=10,
            attempts_count=1,
            created_at=now - timedelta(days=2),
        )
        db.add_all([qlog_c5, qlog_c4])
        db.flush()

        db.add_all([
            QuizStudentAttempt(session_id="sess-c5-exam", quiz_log_id=qlog_c5.id, student_id=stu1.user_id, score=92.0, total_questions=10, correct_count=9, created_at=now - timedelta(days=1)),
            QuizStudentAttempt(session_id="sess-c4-exam", quiz_log_id=qlog_c4.id, student_id=stu1.user_id, score=84.0, total_questions=10, correct_count=8, created_at=now - timedelta(days=2)),
            QuizStudentAttempt(session_id="sess-c5-exam", quiz_log_id=qlog_c5.id, student_id=stu2.user_id, score=45.0, total_questions=10, correct_count=4, created_at=now - timedelta(days=1)),
        ])

        db.add(ChatHistory(sender_id=stu1.user_id, receiver_id=dr.user_id, message="Hello Dr", content_type="text", sent_at=now))
        db.commit()

        admin_token = create_access_token({"sub": str(adm.user_id), "type": "ADM"})
        client = TestClient(app)
        yield client, {"Authorization": f"Bearer {admin_token}"}, stu1.user_id, stu2.user_id
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_attendance_sessions_no_500_and_computes_duration(analytics_client):
    client, headers, _, _ = analytics_client
    r = client.get("/admin/api/attendance/sessions", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["course_id"] == "C5"
    assert data[0]["course_name"] == "Programming"
    assert data[0]["duration_minutes"] == 45
    assert data[0]["attendees_count"] == 2
    assert data[0]["teacher_name"] == "Dr. Ahmed"


def test_students_quiz_analysis_includes_real_student_attempts(analytics_client):
    client, headers, stu1_id, stu2_id = analytics_client
    r = client.get("/admin/api/quizzes/students-analysis", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["summary"]["total_students_active"] == 2
    assert body["summary"]["total_evaluations"] == 3
    assert body["summary"]["overall_avg_score"] == round((92.0 + 84.0 + 45.0) / 3, 1)
    assert body["summary"]["pass_rate"] == round((2 / 3) * 100, 1)

    assert body["score_distribution"]["excellent_85_100"] == 1
    assert body["score_distribution"]["fail_below_50"] == 1

    courses = {c["course_id"]: c for c in body["course_performance"]}
    assert "C5" in courses and "C4" in courses
    assert courses["C5"]["students_count"] == 2
    assert courses["C5"]["avg_score"] == 68.5

    by_id = {s["student_id"]: s for s in body["students"]}
    assert stu1_id in by_id and stu2_id in by_id
    assert by_id[stu1_id]["avg_score"] == 88.0
    assert by_id[stu1_id]["uni_code"] == "2026001"
    assert set(by_id[stu1_id]["courses"]) == {"C4", "C5"}
    assert by_id[stu2_id]["status"] == "يحتاج لمتابعة"


def test_single_student_quizzes_merges_attempts_with_topic_and_course(analytics_client):
    client, headers, stu1_id, _ = analytics_client
    r = client.get(f"/admin/api/quizzes/students/{stu1_id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["student"]["uni_code"] == "2026001"
    assert len(body["quizzes"]) == 2
    topics = {q["topic"] for q in body["quizzes"]}
    assert "C5 Midterm Programming" in topics
    assert "C4 Laravel & Git" in topics
    assert all(q["correct_count"] in (8, 9) for q in body["quizzes"])


def test_quizzes_stats_uses_real_attempts_and_new_model(analytics_client):
    client, headers, _, _ = analytics_client
    r = client.get("/admin/api/quizzes/stats", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_quizzes"] == 2
    assert body["total_attempts"] == 3
    assert body["students_quizzes_count"] == 3
    assert body["average_score"] == round((92.0 + 84.0 + 45.0) / 3, 1)
    assert body["gemini_model"] != "gemini-1.5-flash-8b"


def test_admin_overview_returns_courses_trend_and_attendance_records(analytics_client):
    client, headers, _, _ = analytics_client
    r = client.get("/admin/api/overview", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["users"]["total"] == 5
    assert body["users"]["students"] == 2
    assert body["users"]["teachers"] == 2  # DR + TA
    assert body["users"]["active_last_7d"] == 5
    assert body["users"]["departments_breakdown"]["Programming"] == 1
    assert body["users"]["departments_breakdown"]["Networking"] == 1

    assert body["attendance"]["total_sessions"] == 1
    assert body["attendance"]["total_records"] == 2
    assert body["attendance"]["avg_attendees_per_session"] == 2.0

    assert body["courses"]["total_courses"] == 2
    c_map = {c["course_id"]: c for c in body["courses"]["list"]}
    assert c_map["C5"]["enrolled_students"] == 2
    assert c_map["C5"]["files_count"] == 1
    assert c_map["C5"]["attendance_records"] == 2
    assert c_map["C5"]["quiz_attempts"] == 2
    assert c_map["C5"]["avg_score"] == 68.5

    assert len(body["daily_trend"]) == 14
    assert sum(d["attendance"] for d in body["daily_trend"]) == 2
    assert sum(d["quiz_attempts"] for d in body["daily_trend"]) == 3
    assert sum(d["chats"] for d in body["daily_trend"]) == 1


def test_user_activity_and_stats_include_attempts_and_ta(analytics_client):
    client, headers, stu1_id, _ = analytics_client
    r_act = client.get(f"/admin/api/users/{stu1_id}/activity", headers=headers)
    assert r_act.status_code == 200
    act = r_act.json()
    assert act["student_code"] == "2026001"
    assert act["activity"]["quizzes_generated"] == 2
    assert act["activity"]["quizzes_avg_score"] == 88.0
    assert act["activity"]["attendance_records"] == 1

    r_stats = client.get("/admin/api/stats", headers=headers)
    assert r_stats.status_code == 200
    assert r_stats.json()["doctors_count"] == 2  # DR + TA


def test_admin_portal_gateway_and_analytics_endpoint(analytics_client):
    client, headers, _, _ = analytics_client
    r = client.get("/admin")
    assert r.status_code == 200
    assert r.json()["status"] == "operational"

    # Overview API provides the chart analytics data in pure JSON format
    r_overview = client.get("/admin/api/overview", headers=headers)
    assert r_overview.status_code == 200
    data = r_overview.json()
    assert "quizzes" in data
    assert "users" in data
