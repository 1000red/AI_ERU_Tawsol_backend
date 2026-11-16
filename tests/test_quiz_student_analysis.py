import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.services.quiz_service.session import create_session, _StoredQuestion

client = TestClient(app)


def get_admin_token() -> str:
    return create_access_token({"sub": "1", "type": "ADM"})


def get_student_token(user_id: int = 5) -> str:
    return create_access_token({"sub": str(user_id), "type": "STU"})


def test_quizzes_stats_endpoint():
    token = get_admin_token()
    resp = client.get("/admin/api/quizzes/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "total_quizzes" in data
    assert "total_questions" in data
    assert "today_quizzes" in data
    assert "students_quizzes_count" in data
    assert "teachers_quizzes_count" in data
    assert data["gemini_model"] == "Gemini 2.5 Flash"


def test_students_quiz_analysis_endpoint():
    token = get_admin_token()
    resp = client.get("/admin/api/quizzes/students-analysis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "summary" in data
    assert "students" in data
    assert "total_students_active" in data["summary"]
    assert "overall_avg_score" in data["summary"]
    assert "pass_rate" in data["summary"]


def test_quiz_submit_endpoint():
    # 1. Create a dummy session
    questions = [
        _StoredQuestion(id=1, question="What is TCP?", options={"A": "Protocol", "B": "Cable", "C": "Device", "D": "None"}, correct="A", explanation="TCP is a transport layer protocol."),
        _StoredQuestion(id=2, question="What is IP?", options={"A": "Format", "B": "Protocol", "C": "Router", "D": "None"}, correct="B", explanation="IP is network protocol."),
    ]
    session_id = create_session(file_id=1, questions=questions)

    # 2. Submit answers as student
    payload = {
        "session_id": session_id,
        "answers": {"1": "A", "2": "C"},  # 1 correct, 1 wrong
        "student_id": 5
    }
    resp = client.post("/quiz/submit", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_questions"] == 2
    assert data["correct_count"] == 1
    assert data["score_percentage"] == 50.0
    assert data["passed"] is True
    assert len(data["details"]) == 2
    assert data["details"][0]["is_correct"] is True
    assert data["details"][1]["is_correct"] is False
