import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_analyze_uploaded_code_file(client):
    code_content = """
def network_diagnostics(host: str, port: int) -> bool:
    # Check socket connection to remote host
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0
"""
    response = client.post(
        "/api/v1/games/analyze-file",
        files={"file": ("diagnostics.py", code_content.encode("utf-8"), "text/x-python")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "diagnostics.py"
    components = data["components"]
    assert components["word_count"] > 10
    assert len(components["topics"]) >= 1
    assert "network_diagnostics" in components["topics"] or "socket" in components["topics"] or len(components["topics"]) > 0
    assert components["can_generate_questions"] is True


def test_generate_from_uploaded_file_speed_challenge(client):
    text_sample = """
نموذج OSI يتكون من سبع طبقات تبدأ من الطبقة الفيزيائية وحتى طبقة التطبيقات.
بروتوكول TCP يوفر اتصالاً موثوقاً مع آلية المصافحة الثلاثية Three-way Handshake.
بروتوكول UDP أسرع ولا يتطلب تأكيد الوصول ويستخدم في البث الحي والصوتيات.
تشفير SSL/TLS يعمل في طبقة العرض Presentation Layer لحماية البيانات المتبادلة.
"""
    response = client.post(
        "/api/v1/games/generate-from-file",
        files={"file": ("osi_summary.txt", text_sample.encode("utf-8"), "text/plain")},
        data={"num_questions": 4, "difficulty": "applied", "mode": "speed_challenge"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "pack" in data
    questions = data["pack"]["questions"]
    assert len(questions) == 4
    for q in questions:
        assert len(q["options"]) == 4
        assert 0 <= q["correct_index"] <= 3
        assert q["topic"] == "osi_summary.txt"
        assert len(q["explanation"]) > 5


def test_generate_from_uploaded_file_rapid_tf(client):
    text_sample = """
قواعد البيانات العلائقية تعتمد على الجداول والمفاتيح الأساسية والأجنبية لربط الكيانات.
معاملات قاعدة البيانات تلتزم بمبادئ ACID لضمان الاتساق وعدم فقدان البيانات.
الفهرسة تسرع عمليات البحث والاستعلام ولكنها قد تزيد من زمن الإدراج والتحديث.
"""
    response = client.post(
        "/api/v1/games/generate-from-file",
        files={"file": ("db_lesson.txt", text_sample.encode("utf-8"), "text/plain")},
        data={"num_questions": 3, "difficulty": "applied", "mode": "rapid_tf"}
    )
    assert response.status_code == 200
    data = response.json()
    questions = data["pack"]["questions"]
    assert len(questions) == 3
    for q in questions:
        assert len(q["options"]) == 2
        assert "صحيح" in q["options"][0] or "True" in q["options"][0]
        assert 0 <= q["correct_index"] <= 1
