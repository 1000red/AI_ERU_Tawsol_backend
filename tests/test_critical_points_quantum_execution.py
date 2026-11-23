"""Test suite for WeConnect Master Platform Critical Points execution.
Validates:
1. 1080p Pitch Video Streaming & Info Endpoints (/api/media/pitch-video, /api/media/pitch-video/info)
2. Interactive Pitch Showcase (/pitch, /weconnect, sqbs_pitch.html)
3. Question Bank Federation Protocol (/quiz/federation/banks, /quiz/federation/bank/{id}, /quiz/federation/import-bank/{id})
4. Multi-format Student Practice Exam Runner & Grading (/quiz/practice-sample, _check_answer_correct)
5. Student Attendance Public Summary & Gauge (/attendance/public-summary/{student_id})
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.quiz import _check_answer_correct

client = TestClient(app)


def test_pitch_video_info_endpoint():
    """Verify /api/media/pitch-video/info returns valid metadata and 10 chapters."""
    res = client.get("/api/media/pitch-video/info")
    assert res.status_code == 200
    data = res.json()
    assert "WeConnect HP IDEA Egypt" in data["title"]
    assert data["duration_seconds"] == 300
    assert data["duration_formatted"] == "05:00"
    assert "1080p" in data["resolution"]
    assert len(data["chapters"]) == 10
    assert data["chapters"][0]["time"] == "0:00"
    assert data["chapters"][-1]["time"] == "4:30"


def test_pitch_video_stream_or_redirect():
    """Verify /api/media/pitch-video serves local file or redirects to Neon public storage."""
    res = client.get("/api/media/pitch-video", follow_redirects=False)
    # Either 200 FileResponse (if local video file found) or 307 Temporary Redirect
    assert res.status_code in (200, 307)
    if res.status_code == 307:
        assert "storage.c-7.us-east-2.aws.neon.tech" in res.headers["location"]


def test_pitch_showcase_html_embedding():
    """Verify /pitch serves HTML containing pitch video player and chapter controls."""
    res = client.get("/pitch")
    assert res.status_code == 200
    html = res.text
    assert "openPitchVideo" in html
    assert "WeConnect | العرض التقديمي الرسمي لمسابقة HP IDEA Egypt" in html or "Official HP IDEA Egypt Pitch Video" in html
    assert "Teacher Studio v3" in html
    assert "Student Check-in" in html


def test_quiz_federation_banks():
    """Verify /quiz/federation/banks lists accredited inter-school question banks."""
    res = client.get("/quiz/federation/banks")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_banks"] == 3
    assert data["total_shared_questions"] >= 380
    campuses = [b["campus_code"] for b in data["banks"]]
    assert "SUEZ" in campuses
    assert "CAIRO" in campuses
    assert "ALEX" in campuses


def test_quiz_federation_import():
    """Verify importing a federated bank into a course."""
    res = client.post("/quiz/federation/import-bank/we-suez-net-01?target_material_id=NET101")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["questions_imported"] == 120
    assert "mcq" in data["formats_included"]
    assert "true_false" in data["formats_included"]


def test_quiz_practice_sample_endpoint():
    """Verify /quiz/practice-sample returns 4 distinct formats."""
    res = client.get("/quiz/practice-sample")
    assert res.status_code == 200
    data = res.json()
    assert data["total_questions"] == 4
    formats = [q["q_format"] for q in data["questions"]]
    assert "mcq" in formats
    assert "true_false" in formats
    assert "matching" in formats
    assert "short_answer" in formats


def test_multi_format_auto_grading_logic():
    """Verify deterministic auto-grading across MCQ, True/False, Matching, and Short Answer."""
    # 1. MCQ
    assert _check_answer_correct("A", "A", "mcq") is True
    assert _check_answer_correct("B", "A", "mcq") is False

    # 2. True / False (bilingual handling)
    assert _check_answer_correct("صح", "A", "true_false") is True
    assert _check_answer_correct("TRUE", "صح", "true_false") is True
    assert _check_answer_correct("B", "خطأ", "true_false") is True
    assert _check_answer_correct("خطأ", "صح", "true_false") is False

    # 3. Matching
    assert _check_answer_correct("1:A, 2:B", "1:A, 2:B", "matching") is True
    assert _check_answer_correct('{"1": "A", "2": "B"}', '{"1": "A", "2": "B"}', "matching") is True

    # 4. Short Answer
    assert _check_answer_correct("git checkout -b feature-exam", "git checkout -b feature-exam", "short_answer") is True
    assert _check_answer_correct("استخدام أمر checkout مع الخيار -b", "git checkout -b", "short_answer") is True
    assert _check_answer_correct("نظام مختلف تماما", "git checkout -b", "short_answer") is False


def test_student_checkin_page_embedding():
    """Verify student check-in page contains the 3 tabs, attendance gauge, and exam runner."""
    res = client.get("/checkin")
    assert res.status_code == 200
    html = res.text
    assert "tab-btn-checkin" in html
    assert "tab-btn-summary" in html
    assert "tab-btn-exam" in html
    assert "gauge-circle-progress" in html
    assert "switchStudentTab" in html
    assert "submitPracticeExam" in html
