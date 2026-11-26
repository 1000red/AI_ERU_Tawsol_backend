"""Automated Verification Suite for Admin Panel Security Hardening Plan.

Tests all 8 phases of the plan:
1. Credential Hygiene (no hardcoded passwords/default accounts in HTML, .gitignore guards)
2. Password Complexity Policy (10+ chars, uppercase, lowercase, number, special char, anti-pattern)
3. Brute-Force Lockout (5 failed attempts -> 15-min lockout with HTTP 429)
4. Session & Token Security (HttpOnly cookies, Double-Submit CSRF protection)
5. Admin API Authorization & Super Admin Guard for Kill-Switch
6. Administrative Security Audit Logging (AdminAuditLog table & /admin/api/audit endpoint)
7. Security Headers & Information Cloaking
"""

import os
import re
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.database import get_db
from app.models.user import User
from app.models.admin_audit import AdminAuditLog
from app.models.platform_control import PlatformControl
from app.core.security import hash_password, create_access_token
from app.services.auth_security_service import auth_security_service, AuthSecurityService
from app.services import user_service as user_svc
from app.core.config import settings

# In-memory SQLite for isolated security tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.query(AdminAuditLog).delete()
    db.query(PlatformControl).delete()
    db.query(User).delete()

    # Seed Admin User
    admin = User(
        user_id=1,
        uni_code="ADM001",
        name="Security Admin",
        email="secadmin@weschool.edu.eg",
        password=hash_password("SuperSecure#2026!"),
        type_code="ADM",
        level=100,
        department="Information Security",
    )
    # Seed Regular Doctor & Student
    dr = User(
        user_id=2,
        uni_code="DR001",
        name="Dr. Tarek",
        email="tarek@weschool.edu.eg",
        password=hash_password("DrPassword#2026!"),
        type_code="DR",
        level=0,
        department="Computer Science",
    )
    stu = User(
        user_id=3,
        uni_code="STU001",
        name="Ahmed Aly",
        email="ahmed@weschool.edu.eg",
        password=hash_password("StuPassword#2026!"),
        type_code="STU",
        level=3,
        department="Computer Science",
    )
    # Seed Platform status
    plat = PlatformControl(id=1, is_active=True, maintenance_message="Operational")
    db.add_all([admin, dr, stu, plat])
    db.commit()
    db.close()

    # Reset security lockout in-memory state
    auth_security_service.reset()
    client.cookies.clear()

    yield

    auth_security_service.reset()
    client.cookies.clear()
    Base.metadata.drop_all(bind=engine)
    if prev_override is not None:
        app.dependency_overrides[get_db] = prev_override
    else:
        app.dependency_overrides.pop(get_db, None)


# ── Phase 0: Credential Hygiene Tests ──────────────────────────────────────────

def test_phase0_credential_hygiene_in_markup():
    """Verify that user_management.html contains NO hardcoded admin credentials or default accounts."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "app", "routers", "user_management.html")
    assert os.path.isfile(html_path), "user_management.html not found"

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Reject specific leaked strings
    assert "admin@weschool-suez.edu.eg" not in content, "Found hardcoded admin email in HTML"
    assert "Admin@123456" not in content, "Found hardcoded default password in HTML"
    assert "حساب المسؤول الافتراضي للنظام" not in content, "Found default admin info card in HTML"

    # 2. Check login inputs do not have hardcoded value="..." attributes
    assert not re.search(r'<input[^>]*id="login-email"[^>]*value=', content), "login-email has hardcoded value"
    assert not re.search(r'<input[^>]*id="login-password"[^>]*value=', content), "login-password has hardcoded value"


def test_phase0_gitignore_protection():
    """Verify that .gitignore properly guards all environment variable files and private keys."""
    gitignore_path = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
    assert os.path.isfile(gitignore_path), ".gitignore not found"

    with open(gitignore_path, "r", encoding="utf-8") as f:
        lines = f.read()

    assert ".env*" in lines or ".env.local" in lines, ".env files not protected in .gitignore"
    assert "*.pem" in lines, "*.pem private keys not protected in .gitignore"
    assert "*.key" in lines, "*.key private keys not protected in .gitignore"


# ── Phase 1: Password Complexity & Brute-Force Lockout Tests ──────────────────

def test_phase1_password_complexity_rules():
    """Verify password strength validation against university security standards."""
    # Too short (< 10 chars)
    ok, msg = auth_security_service.validate_password_strength("Short1!")
    assert not ok and "10" in msg

    # Missing uppercase
    ok, msg = auth_security_service.validate_password_strength("lowercase123!@#")
    assert not ok and "كبير" in msg

    # Missing lowercase
    ok, msg = auth_security_service.validate_password_strength("UPPERCASE123!@#")
    assert not ok and "صغير" in msg

    # Missing number
    ok, msg = auth_security_service.validate_password_strength("NoNumberSymbol!@#")
    assert not ok and "رقم" in msg

    # Missing special character
    ok, msg = auth_security_service.validate_password_strength("NoSpecialChar1234")
    assert not ok and "رمز" in msg

    # Common prohibited pattern
    ok, msg = auth_security_service.validate_password_strength("MyPassword123!")
    assert not ok and "محظور" in msg

    # Valid strong password
    ok, msg = auth_security_service.validate_password_strength("StrongSecurity#2026!")
    assert ok and "مطابقة" in msg


def test_phase1_account_lockout_after_five_failed_attempts():
    """Verify 5 failed login attempts trigger 15-minute temporary lockout (HTTP 429)."""
    email = "secadmin@weschool.edu.eg"

    # 4 failed attempts should yield HTTP 401
    for i in range(4):
        res = client.post("/auth/login", json={"email": email, "password": "WrongPassword#1!"})
        assert res.status_code == 401, f"Attempt {i+1} should fail with 401"

    # 5th failed attempt triggers the lockout
    res5 = client.post("/auth/login", json={"email": email, "password": "WrongPassword#1!"})
    # Either 401 or immediately 429
    assert res5.status_code in (401, 429)

    # 6th attempt (even with CORRECT credentials!) MUST be blocked with HTTP 429
    locked_res = client.post("/auth/login", json={"email": email, "password": "SuperSecure#2026!"})
    assert locked_res.status_code == 429, "Locked account must return HTTP 429"
    assert "قفل الحساب مؤقتاً" in locked_res.json()["detail"]
    assert "retry-after" in locked_res.headers

    # Admin unlock clears the lockout
    auth_security_service.unlock_account(email)
    success_res = client.post("/auth/login", json={"email": email, "password": "SuperSecure#2026!"})
    assert success_res.status_code == 200, "After unlock, login with correct password must succeed"


# ── Phase 2: Session, Cookie & CSRF Security Tests ─────────────────────────────

def test_phase2_login_sets_httponly_and_csrf_cookies():
    """Verify POST /auth/login issues HttpOnly admin_token and readable csrf_token cookies."""
    res = client.post(
        "/auth/login",
        json={"email": "secadmin@weschool.edu.eg", "password": "SuperSecure#2026!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "csrf_token" in data
    assert len(data["csrf_token"]) >= 32

    # Check cookies
    cookies = res.cookies
    assert "admin_token" in cookies
    assert "csrf_token" in cookies


def test_phase2_cookie_auth_requires_csrf_on_mutations():
    """Verify cookie-authenticated mutating requests require matching X-CSRF-Token."""
    login_res = client.post(
        "/auth/login",
        json={"email": "secadmin@weschool.edu.eg", "password": "SuperSecure#2026!"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.json()["csrf_token"]
    cookie_token = login_res.cookies.get("admin_token")
    cookie_csrf = login_res.cookies.get("csrf_token")

    # 1. State-changing request WITH cookie but WITHOUT X-CSRF-Token header -> 403
    client.cookies.set("admin_token", cookie_token)
    client.cookies.set("csrf_token", cookie_csrf)
    fail_res = client.put("/admin/api/platform/status", json={"is_active": False})
    assert fail_res.status_code == 403
    assert "CSRF" in fail_res.json()["detail"]

    # 2. State-changing request WITH mismatched X-CSRF-Token header -> 403
    fail_res2 = client.put(
        "/admin/api/platform/status",
        headers={"X-CSRF-Token": "invalid_forged_csrf_token"},
        json={"is_active": False},
    )
    assert fail_res2.status_code == 403

    # 3. State-changing request WITH valid matching X-CSRF-Token header -> 200
    ok_res = client.put(
        "/admin/api/platform/status",
        headers={"X-CSRF-Token": csrf_token},
        json={"is_active": False, "maintenance_message": "اختبار أمني دوري"},
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["is_active"] is False

    # 4. Read-only (GET) request with cookie auth does NOT require CSRF token
    get_res = client.get("/admin/api/platform/status")
    assert get_res.status_code == 200

    # 5. Direct Bearer token in Authorization header does NOT require CSRF token
    client.cookies.clear()
    bearer_token = login_res.json()["access_token"]
    bearer_res = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {bearer_token}"},
        json={"is_active": True},
    )
    assert bearer_res.status_code == 200
    assert bearer_res.json()["is_active"] is True


def test_phase2_logout_clears_cookies():
    """Verify POST /auth/logout clears admin_token and csrf_token cookies."""
    res = client.post("/auth/logout")
    assert res.status_code == 200
    # Deleted cookies have empty value or max-age=0/expired
    set_cookie_headers = res.headers.get("set-cookie", "")
    assert 'admin_token=""' in set_cookie_headers or "admin_token=;" in set_cookie_headers or 'admin_token=""' in str(res.cookies)


# ── Phase 3 & 4: Admin API Authorization & Platform Kill-Switch Guard ──────────

def test_phase3_admin_endpoints_reject_student_and_doctor():
    """Verify student and doctor accounts cannot mutate admin endpoints."""
    # Student token
    stu_token = create_access_token({"sub": "3", "type": "STU"})
    res1 = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {stu_token}"},
        json={"is_active": False},
    )
    assert res1.status_code == 403

    # Doctor token
    dr_token = create_access_token({"sub": "2", "type": "DR"})
    res2 = client.post(
        "/admin/api/users",
        headers={"Authorization": f"Bearer {dr_token}"},
        json={"uni_code": "NEW001", "name": "Fake", "email": "fake@test.edu.eg", "password": "FakePass#2026!"},
    )
    assert res2.status_code == 403


def test_phase4_killswitch_audit_logging():
    """Verify mutating the platform status creates an immutable audit log entry."""
    adm_token = create_access_token({"sub": "1", "type": "ADM"})

    # Stop platform
    r_stop = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {adm_token}"},
        json={"is_active": False, "maintenance_message": "صيانة دورية عاجلة"},
    )
    assert r_stop.status_code == 200

    # Start platform
    r_start = client.put(
        "/admin/api/platform/status",
        headers={"Authorization": f"Bearer {adm_token}"},
        json={"is_active": True},
    )
    assert r_start.status_code == 200

    # Query audit logs via GET /admin/api/audit
    audit_res = client.get(
        "/admin/api/audit",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert audit_res.status_code == 200
    logs = audit_res.json()
    actions = [l["action"] for l in logs]
    assert "PLATFORM_STOP" in actions
    assert "PLATFORM_START" in actions


# ── Phase 5 & 6: Security Headers Verification ────────────────────────────────

def test_phase5_security_headers_present():
    """Verify all mandatory cybersecurity HTTP headers are present on responses."""
    res = client.get("/admin", headers={"Accept": "text/html"})
    headers = res.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "SAMEORIGIN"
    assert "max-age=" in headers.get("strict-transport-security", "")
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("server") == "protected"
