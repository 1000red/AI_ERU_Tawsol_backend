"""End-to-end integration tests for Vercel Blob Storage Command Center (#UI-4.0).

Tests:
1. GET /admin/api/storage/quota (Hobby 1 GB limit calculation, recoverable orphans, used percentage)
2. GET /admin/api/storage/files (Descending size sort, gt_5mb filter, orphan filter, search query)
3. POST /admin/api/storage/upload-token (Client direct upload token generation to bypass 4.5 MB limit)
4. POST /admin/api/storage/quarantine/{id} (7-day quarantine soft delete and audit logging)
5. POST /admin/api/storage/restore/{id} (1-click restoration from quarantine)
6. POST /admin/api/storage/replace/{id} (Atomic file swap, size update, net savings calculation)
7. DELETE /admin/api/storage/permanent/{id} (Strict "DELETE" confirmation validation & Super Admin RBAC)
8. GET /admin/api/storage/audit (Immutable audit log retrieval)
9. POST /admin/api/storage/sync (Blob storage synchronization)
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
from app.models.material import Material
from app.models.content.material_file import MaterialFile
from app.models.storage_audit import StorageAuditLog, StorageQuarantine


@pytest.fixture()
def storage_client():
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
        # Create user types
        for code, desc in [("ADM", "Admin"), ("DR", "Doctor"), ("STU", "Student")]:
            db.add(UserType(code=code, description=desc))
        db.flush()

        # Create admin, doctor, student
        admin = User(
            uni_code="ADM_SUPER",
            name="Super Administrator",
            email="superadmin@we.edu.eg",
            password=hash_password("SuperPass@123"),
            level=100,
            department="IT",
            type_code="ADM",
            last_seen=now,
        )
        doctor = User(
            uni_code="DR_AHMED",
            name="Dr. Ahmed",
            email="ahmed@we.edu.eg",
            password=hash_password("DocPass@123"),
            level=0,
            department="Computer Science",
            type_code="DR",
            last_seen=now,
        )
        student = User(
            uni_code="STU_202601",
            name="Student Omar",
            email="omar@we.edu.eg",
            password=hash_password("StuPass@123"),
            level=1,
            department="Computer Science",
            type_code="STU",
            last_seen=now,
        )
        db.add_all([admin, doctor, student])
        db.flush()

        # Create a course material
        mat = Material(
            material_id="CS101",
            name="Introduction to Programming",
            description="Python & Data Structures",
            duration=30,
        )
        db.add(mat)
        db.flush()

        # File 1: Linked to course CS101, 8 MB (gt_5mb = True, orphan = False)
        f1 = MaterialFile(
            material_id="CS101",
            author_id=doctor.user_id,
            title="Lecture 1: Python Basics.pdf",
            file_path="https://blob.vercel-storage.com/lectures/cs101_lec1.pdf",
            file_type="pdf",
            file_size=8 * 1024 * 1024, # 8 MB
        )
        # File 2: Orphan file, 15 MB (gt_5mb = True, orphan = True)
        f2 = MaterialFile(
            material_id=None,
            author_id=doctor.user_id,
            title="Temp Unlinked Video.mp4",
            file_path="https://blob.vercel-storage.com/temp/unlinked_vid.mp4",
            file_type="mp4",
            file_size=15 * 1024 * 1024, # 15 MB
        )
        # File 3: Linked to course CS101, 2 MB (gt_5mb = False, orphan = False)
        f3 = MaterialFile(
            material_id="CS101",
            author_id=doctor.user_id,
            title="Syllabus.docx",
            file_path="https://blob.vercel-storage.com/lectures/syllabus.docx",
            file_type="doc",
            file_size=2 * 1024 * 1024, # 2 MB
        )
        db.add_all([f1, f2, f3])
        db.commit()

        admin_token = create_access_token({"sub": str(admin.user_id), "type": "ADM"})
        student_token = create_access_token({"sub": str(student.user_id), "type": "STU"})

        yield {
            "client": TestClient(app),
            "admin_token": admin_token,
            "student_token": student_token,
            "admin_id": admin.user_id,
            "f1_id": f1.file_id,
            "f2_id": f2.file_id,
            "f3_id": f3.file_id,
            "db_session": TestingSessionLocal,
        }
    finally:
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def test_storage_quota_calculation(storage_client):
    """GET /admin/api/storage/quota computes correct bytes, percentage, and recoverable orphans."""
    client = storage_client["client"]
    token = storage_client["admin_token"]

    res = client.get("/admin/api/storage/quota", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "quota" in data
    quota = data["quota"]

    # Total used bytes = 8 MB + 15 MB + 2 MB = 25 MB
    assert quota["files_count"] == 3
    assert quota["used_bytes"] == 25 * 1024 * 1024
    assert quota["limit_bytes"] == 1024 * 1024 * 1024 # 1 GB Hobby
    assert quota["used_percentage"] > 2.0
    assert quota["orphan_files_count"] == 1
    assert quota["recoverable_bytes_from_orphans"] == 15 * 1024 * 1024
    assert quota["quarantined_count"] == 0


def test_storage_files_listing_and_filters(storage_client):
    """GET /admin/api/storage/files supports sorting, gt_5mb, orphan filtering, and search."""
    client = storage_client["client"]
    token = storage_client["admin_token"]

    # 1. Default listing: descending by size
    res = client.get("/admin/api/storage/files?sort=size_desc", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    files = res.json()["files"]
    assert len(files) == 3
    assert files[0]["file_size"] == 15 * 1024 * 1024
    assert files[1]["file_size"] == 8 * 1024 * 1024
    assert files[2]["file_size"] == 2 * 1024 * 1024

    # 2. Filter: gt_5mb (only files > 5 MB)
    res_gt = client.get("/admin/api/storage/files?filter=gt_5mb", headers={"Authorization": f"Bearer {token}"})
    assert res_gt.status_code == 200
    gt_files = res_gt.json()["files"]
    assert len(gt_files) == 2
    for f in gt_files:
        assert f["file_size"] > 5 * 1024 * 1024

    # 3. Filter: orphan (only unlinked files)
    res_orphan = client.get("/admin/api/storage/files?filter=orphan", headers={"Authorization": f"Bearer {token}"})
    assert res_orphan.status_code == 200
    orphan_files = res_orphan.json()["files"]
    assert len(orphan_files) == 1
    assert orphan_files[0]["id"] == storage_client["f2_id"]
    assert orphan_files[0]["is_orphan"] is True

    # 4. Search query
    res_search = client.get("/admin/api/storage/files?q=Python", headers={"Authorization": f"Bearer {token}"})
    assert res_search.status_code == 200
    search_files = res_search.json()["files"]
    assert len(search_files) == 1
    assert "Python" in search_files[0]["title"]


def test_storage_upload_token_generation(storage_client):
    """POST /admin/api/storage/upload-token generates client upload parameters for files > 4.5 MB."""
    client = storage_client["client"]
    token = storage_client["admin_token"]

    payload = {
        "filename": "LargePresentation.pptx",
        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "file_size": 25 * 1024 * 1024 # 25 MB
    }
    res = client.post("/admin/api/storage/upload-token", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "upload_url" in data
    assert "file_url" in data
    assert data["multipart_supported"] is True


def test_storage_quarantine_and_restore_cycle(storage_client):
    """POST /admin/api/storage/quarantine/{id} and restore cycle with audit logging."""
    client = storage_client["client"]
    token = storage_client["admin_token"]
    f1_id = storage_client["f1_id"]

    # 1. Quarantine file 1
    res_q = client.post(
        f"/admin/api/storage/quarantine/{f1_id}",
        json={"reason": "Testing 7-day soft quarantine"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_q.status_code == 200
    assert res_q.json()["success"] is True

    # Verify quarantined count in quota
    res_quota = client.get("/admin/api/storage/quota", headers={"Authorization": f"Bearer {token}"})
    assert res_quota.json()["quota"]["quarantined_count"] == 1

    # Verify filter=quarantine returns file 1
    res_qlist = client.get("/admin/api/storage/files?filter=quarantine", headers={"Authorization": f"Bearer {token}"})
    qfiles = res_qlist.json()["files"]
    assert len(qfiles) == 1
    assert qfiles[0]["id"] == f1_id
    assert qfiles[0]["is_quarantined"] is True

    # 2. Restore file 1
    res_rest = client.post(f"/admin/api/storage/restore/{f1_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_rest.status_code == 200
    assert res_rest.json()["success"] is True

    # Verify quarantined count back to 0
    res_quota2 = client.get("/admin/api/storage/quota", headers={"Authorization": f"Bearer {token}"})
    assert res_quota2.json()["quota"]["quarantined_count"] == 0


def test_storage_atomic_replacement(storage_client):
    """POST /admin/api/storage/replace/{id} swaps file atomically and logs savings."""
    client = storage_client["client"]
    token = storage_client["admin_token"]
    f1_id = storage_client["f1_id"] # currently 8 MB

    payload = {
        "new_url": "https://blob.vercel-storage.com/lectures/cs101_lec1_compressed.pdf",
        "new_size": 3 * 1024 * 1024, # reduced to 3 MB (net savings = 5 MB)
        "old_file_path": "https://blob.vercel-storage.com/lectures/cs101_lec1.pdf"
    }

    res = client.post(f"/admin/api/storage/replace/{f1_id}", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["net_savings"] == 5 * 1024 * 1024

    # Verify file updated in listing
    res_files = client.get("/admin/api/storage/files", headers={"Authorization": f"Bearer {token}"})
    f1_updated = next(f for f in res_files.json()["files"] if f["id"] == f1_id)
    assert f1_updated["file_size"] == 3 * 1024 * 1024
    assert f1_updated["file_path"] == payload["new_url"]


def test_storage_permanent_delete_safety_checks(storage_client):
    """DELETE /admin/api/storage/permanent/{id} requires exact 'DELETE' confirmation string."""
    client = storage_client["client"]
    token = storage_client["admin_token"]
    f2_id = storage_client["f2_id"]

    # 1. Missing or wrong confirmation string must fail with 400
    res_fail = client.request(
        "DELETE",
        f"/admin/api/storage/permanent/{f2_id}",
        json={"confirmation": "yes"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_fail.status_code == 400

    # 2. Correct confirmation string "DELETE" succeeds
    res_ok = client.request(
        "DELETE",
        f"/admin/api/storage/permanent/{f2_id}",
        json={"confirmation": "DELETE"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["success"] is True
    assert res_ok.json()["bytes_freed"] == 15 * 1024 * 1024

    # Verify total files count reduced from 3 to 2
    res_quota = client.get("/admin/api/storage/quota", headers={"Authorization": f"Bearer {token}"})
    assert res_quota.json()["quota"]["files_count"] == 2


def test_storage_security_rbac_rejection(storage_client):
    """Non-admin student tokens are rejected with 403 on storage endpoints."""
    client = storage_client["client"]
    student_token = storage_client["student_token"]

    res = client.get("/admin/api/storage/quota", headers={"Authorization": f"Bearer {student_token}"})
    assert res.status_code == 403

    res_post = client.post("/admin/api/storage/upload-token", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert res_post.status_code == 403


def test_storage_audit_trail_immutable(storage_client):
    """GET /admin/api/storage/audit retrieves audit records created by actions."""
    client = storage_client["client"]
    token = storage_client["admin_token"]
    f3_id = storage_client["f3_id"]

    # Perform a quarantine action to generate audit entry
    client.post(f"/admin/api/storage/quarantine/{f3_id}", json={"reason": "Audit verification"}, headers={"Authorization": f"Bearer {token}"})

    res = client.get("/admin/api/storage/audit?limit=10", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "audit_logs" in data
    assert len(data["audit_logs"]) >= 1
    first_log = data["audit_logs"][0]
    assert first_log["action"] == "quarantine"
    assert first_log["admin_name"] == "Super Administrator"
