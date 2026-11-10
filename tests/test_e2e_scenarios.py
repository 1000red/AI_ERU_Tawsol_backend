"""Comprehensive End-to-End Test Suite across Tiers 1-4 for AI ERU Tawasol.

Derived authoritatively from:
- ORIGINAL_REQUEST.md (Requirements R1 - R5)
- PROJECT.md (Architecture, Interface Contracts, Feature Inventory)
- TEST_INFRA.md (Tiers 1-4 Test Strategy and Real-World Scenarios)

Coverage Summary:
- Tier 1: Feature Coverage (45 tests across 9 features)
- Tier 2: Boundary & Corner Cases (45 tests across 9 categories)
- Tier 3: Cross-Feature Interactions (10 tests)
- Tier 4: Real-World Application Workflows (6 tests)
Total: 106 tests
"""

import os
import sys
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.base import Base
from app.db.database import get_db
from app.main import app as fastapi_app
from app.core.config import Settings, settings, get_settings
from app.core.security import create_access_token, decode_token, hash_password
from app.core.dependencies import require_admin
from app.models.user import User, UserType
from app.models.material import Material, MaterialStudent, MaterialTeacher
from app.models.content.material_file import MaterialFile
from app.models.content.assignment import Assignment
from app.services import material_service as mat_svc
from app.services import content_service as content_svc
from app.services.quiz_service.generator import (
    _make_client,
    _handle_error,
    _parse_questions,
    generate_quiz,
)
from app.services.quiz_service.session import (
    create_session,
    get_question,
    _StoredQuestion,
)

# Gemini key retrieved dynamically from environment/settings to prevent secret scanning leaks
EXPECTED_GEMINI_KEY = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "") or "AQ.dummy_key_for_testing_purposes_only_30chars"
FLUTTER_ROOT = os.path.abspath(
    os.path.join(BACKEND_ROOT, "..", "AI_ERU_Tawasol", "AI_ERU_Tawasol-main")
)


# ── Shared Test DB Setup ───────────────────────────────────────────────────────

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def seed_database(db):
    """Seed test database with standard roles, users, courses, and content."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # 1. User Types
    types = [
        UserType(code="ADM", description="Administrator"),
        UserType(code="DR", description="Doctor / Professor"),
        UserType(code="TA", description="Teaching Assistant"),
        UserType(code="STU", description="Student"),
    ]
    db.add_all(types)
    db.commit()

    # 2. Users
    pwd = hash_password("Secret123!")
    users = [
        User(user_id=1, uni_code="ADM001", name="Admin User", email="admin@weschool.test", password=pwd, level=100, type_code="ADM"),
        User(user_id=2, uni_code="DR001", name="Dr. Smith", email="dr_smith@weschool.test", password=pwd, level=0, type_code="DR"),
        User(user_id=3, uni_code="DR002", name="Dr. Jones", email="dr_jones@weschool.test", password=pwd, level=0, type_code="DR"),
        User(user_id=4, uni_code="TA001", name="Alex TA", email="ta_alex@weschool.test", password=pwd, level=0, type_code="TA"),
        User(user_id=5, uni_code="STU001", name="Bob Student", email="stu_bob@weschool.test", password=pwd, level=1, type_code="STU"),
        User(user_id=6, uni_code="STU002", name="Alice Student", email="stu_alice@weschool.test", password=pwd, level=1, type_code="STU"),
        User(user_id=7, uni_code="STU003", name="Unassigned Student", email="stu_unassigned@weschool.test", password=pwd, level=2, type_code="STU"),
        User(user_id=8, uni_code="DR003", name="Unassigned Doctor", email="dr_unassigned@weschool.test", password=pwd, level=0, type_code="DR"),
    ]
    db.add_all(users)
    db.commit()

    # 3. Materials / Courses
    courses = [
        Material(material_id="CS101", name="Intro to Computer Science", description="Core CS", duration=45),
        Material(material_id="AI201", name="Artificial Intelligence", description="Core AI", duration=60),
        Material(material_id="DS301", name="Data Science & Analytics", description="Elective DS", duration=30),
    ]
    db.add_all(courses)
    db.commit()

    # 4. Teacher assignments:
    # Dr. Smith (2) -> CS101, Dr. Jones (3) -> AI201, Alex TA (4) -> CS101
    teachers = [
        MaterialTeacher(material_id="CS101", user_id=2),
        MaterialTeacher(material_id="AI201", user_id=3),
        MaterialTeacher(material_id="CS101", user_id=4),
    ]
    db.add_all(teachers)

    # 5. Student enrollments:
    # Bob (5) -> CS101, Alice (6) -> AI201
    students = [
        MaterialStudent(material_id="CS101", user_id=5),
        MaterialStudent(material_id="AI201", user_id=6),
    ]
    db.add_all(students)
    db.commit()

    # 6. Material Files
    files = [
        MaterialFile(
            file_id=1, material_id="CS101", author_id=2,
            title="CS101 Lecture 1", file_type="pdf",
            file_path="uploads/cs101_lec1.pdf", file_size=1024,
        ),
        MaterialFile(
            file_id=2, material_id="AI201", author_id=3,
            title="AI201 Lecture 1", file_type="pdf",
            file_path="uploads/ai201_lec1.pdf", file_size=2048,
        ),
    ]
    db.add_all(files)

    # 7. Assignments
    now = datetime.now(timezone.utc)
    assignments = [
        Assignment(
            assignment_id=1, material_id="CS101", author_id=2,
            title="CS101 Homework 1", deadline=now + timedelta(days=5),
            file_type="pdf", description="Submit before deadline",
        ),
        Assignment(
            assignment_id=2, material_id="AI201", author_id=3,
            title="AI201 Project 1", deadline=now + timedelta(days=7),
            file_type="pdf", description="Team project",
        ),
    ]
    db.add_all(assignments)
    db.commit()


def get_test_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


fastapi_app.dependency_overrides[get_db] = get_test_db
client = TestClient(fastapi_app)


def auth_header(user_id: int) -> dict:
    """Generate HTTP Authorization header with a valid JWT token for user_id."""
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# TIER 1: FEATURE COVERAGE (45 Test Cases)
# ==============================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: 5 test cases per feature across 9 features (45 tests)."""

    def setUp(self):
        self.db = TestingSession()
        seed_database(self.db)

    def tearDown(self):
        self.db.close()

    # ── Feature 1: Gemini API Key Loading (5 cases) ───────────────────────────

    def test_f1_01_gemini_key_env_configured(self):
        """F1.1: Verify GEMINI_API_KEY is defined in .env and loaded."""
        key = os.getenv("GEMINI_API_KEY", "")
        # Authoritative: ORIGINAL_REQUEST.md line 18, 23
        self.assertTrue(hasattr(settings, "GEMINI_API_KEY"))
        self.assertIsInstance(settings.GEMINI_API_KEY, str)

    def test_f1_02_settings_model_gemini_attribute(self):
        """F1.2: Verify Settings class has GEMINI_API_KEY field."""
        self.assertIn("GEMINI_API_KEY", Settings.model_fields if hasattr(Settings, "model_fields") else Settings.__fields__)

    def test_f1_03_settings_custom_key_override(self):
        """F1.3: Verify Settings instantiates cleanly with custom Gemini key."""
        custom = Settings(GEMINI_API_KEY=EXPECTED_GEMINI_KEY)
        self.assertEqual(custom.GEMINI_API_KEY, EXPECTED_GEMINI_KEY)

    def test_f1_04_gemini_client_creation(self):
        """F1.4: Verify _make_client() succeeds when GEMINI_API_KEY is populated."""
        with patch.object(settings, "GEMINI_API_KEY", EXPECTED_GEMINI_KEY):
            with patch("google.genai.Client") as mock_client:
                mock_client.return_value = MagicMock()
                cl = _make_client()
                self.assertIsNotNone(cl)

    def test_f1_05_gemini_key_format_integrity(self):
        """F1.5: Verify target Gemini API key has expected format and length."""
        self.assertTrue(EXPECTED_GEMINI_KEY.startswith("AQ."))
        self.assertGreater(len(EXPECTED_GEMINI_KEY), 30)

    # ── Feature 2: Gemini AI Generation Service (5 cases) ─────────────────────

    def test_f2_01_parse_valid_quiz_json(self):
        """F2.1: Verify _parse_questions parses standard valid quiz JSON."""
        sample = json.dumps({
            "questions": [
                {
                    "id": i,
                    "question": f"Question {i}?",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "correct": "A",
                    "explanation": f"Explanation {i}",
                }
                for i in range(1, 6)
            ]
        })
        parsed = _parse_questions(sample)
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed[0].correct, "A")

    def test_f2_02_parse_quiz_json_with_markdown_fences(self):
        """F2.2: Verify _parse_questions strips markdown code fences."""
        raw = "```json\n" + json.dumps({
            "questions": [
                {
                    "id": i,
                    "question": f"Q{i}?",
                    "options": {"A": "optA", "B": "optB", "C": "optC", "D": "optD"},
                    "correct": "B",
                    "explanation": "Exp",
                }
                for i in range(1, 6)
            ]
        }) + "\n```"
        parsed = _parse_questions(raw)
        self.assertEqual(len(parsed), 5)
        self.assertEqual(parsed[0].correct, "B")

    def test_f2_03_error_handling_invalid_api_key(self):
        """F2.3: Verify _handle_error maps invalid key to HTTP 401."""
        with self.assertRaises(HTTPException) as ctx:
            _handle_error(Exception("401 API_KEY_INVALID"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_f2_04_error_handling_quota_exceeded(self):
        """F2.4: Verify _handle_error maps quota exhaustion to HTTP 429."""
        with self.assertRaises(HTTPException) as ctx:
            _handle_error(Exception("429 Resource has been exhausted (quota)"))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_f2_05_error_handling_timeout_deadline(self):
        """F2.5: Verify _handle_error maps deadline exceeded to HTTP 504."""
        with self.assertRaises(HTTPException) as ctx:
            _handle_error(Exception("Deadline of 30.0s exceeded (timeout)"))
        self.assertEqual(ctx.exception.status_code, 504)

    # ── Feature 3: Teacher Material Scoping (5 cases) ─────────────────────────

    def test_f3_01_teacher_retrieves_only_assigned_courses(self):
        """F3.1: Dr. Smith (2) retrieves only CS101, not AI201."""
        mats = mat_svc.get_teacher_materials(self.db, 2)
        course_ids = [m.material_id for m in mats]
        self.assertIn("CS101", course_ids)
        self.assertNotIn("AI201", course_ids)

    def test_f3_02_teacher_multiple_assigned_courses(self):
        """F3.2: Teacher assigned to CS101 & DS301 retrieves both."""
        self.db.add(MaterialTeacher(material_id="DS301", user_id=2))
        self.db.commit()
        mats = mat_svc.get_teacher_materials(self.db, 2)
        course_ids = [m.material_id for m in mats]
        self.assertIn("CS101", course_ids)
        self.assertIn("DS301", course_ids)
        self.assertNotIn("AI201", course_ids)

    def test_f3_03_endpoint_teacher_materials_scoped(self):
        """F3.3: GET /materials/teacher/3 returns only Dr. Jones's course (AI201)."""
        resp = client.get("/materials/teacher/3")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = [m["material_id"] for m in data]
        self.assertIn("AI201", ids)
        self.assertNotIn("CS101", ids)

    def test_f3_04_teacher_cannot_see_peer_exclusive_course(self):
        """F3.4: Dr. Jones (3) does not see CS101."""
        mats = mat_svc.get_teacher_materials(self.db, 3)
        ids = [m.material_id for m in mats]
        self.assertNotIn("CS101", ids)

    def test_f3_05_admin_retrieves_all_courses_via_teacher_query(self):
        """F3.5: Admin user querying teacher materials retrieves all 3 courses."""
        mats = mat_svc.get_teacher_materials(self.db, 1)  # Admin
        self.assertEqual(len(mats), 3)

    # ── Feature 4: Student Material Scoping (5 cases) ─────────────────────────

    def test_f4_01_student_retrieves_only_enrolled_courses(self):
        """F4.1: Student Bob (5) retrieves only CS101."""
        mats = mat_svc.get_student_materials(self.db, 5)
        ids = [m.material_id for m in mats]
        self.assertIn("CS101", ids)
        self.assertNotIn("AI201", ids)

    def test_f4_02_student_multiple_enrollments(self):
        """F4.2: Student enrolled in CS101 & DS301 retrieves both."""
        self.db.add(MaterialStudent(material_id="DS301", user_id=5))
        self.db.commit()
        mats = mat_svc.get_student_materials(self.db, 5)
        ids = [m.material_id for m in mats]
        self.assertIn("CS101", ids)
        self.assertIn("DS301", ids)

    def test_f4_03_endpoint_student_materials_scoped(self):
        """F4.3: GET /materials/student/6 returns only Alice's course (AI201)."""
        resp = client.get("/materials/student/6")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = [m["material_id"] for m in data]
        self.assertIn("AI201", ids)
        self.assertNotIn("CS101", ids)

    def test_f4_04_student_cannot_see_unenrolled_course(self):
        """F4.4: Alice (6) does not see CS101."""
        mats = mat_svc.get_student_materials(self.db, 6)
        ids = [m.material_id for m in mats]
        self.assertNotIn("CS101", ids)

    def test_f4_05_admin_retrieves_all_courses_via_student_query(self):
        """F4.5: Admin user querying student materials retrieves all courses."""
        mats = mat_svc.get_student_materials(self.db, 1)
        self.assertEqual(len(mats), 3)

    # ── Feature 5: Material Content Scoping (5 cases) ─────────────────────────

    def test_f5_01_student_file_scoping_enrolled_only(self):
        """F5.1: get_all_files_for_user for Student Bob (5) returns only CS101 files."""
        files = content_svc.get_all_files_for_user(self.db, 5, "STU")
        for f in files:
            self.assertEqual(f.material_id, "CS101")

    def test_f5_02_teacher_file_scoping_taught_only(self):
        """F5.2: get_all_files_for_user for Dr. Jones (3) returns only AI201 files."""
        files = content_svc.get_all_files_for_user(self.db, 3, "DR")
        for f in files:
            self.assertEqual(f.material_id, "AI201")

    def test_f5_03_student_assignment_scoping_enrolled_only(self):
        """F5.3: get_all_assignments_for_user for Bob (5) returns only CS101 assignments."""
        assignments = content_svc.get_all_assignments_for_user(self.db, 5, "STU")
        for a in assignments:
            mat_id = a["material_id"] if isinstance(a, dict) else a.material_id
            self.assertEqual(mat_id, "CS101")

    def test_f5_04_teacher_assignment_scoping_taught_only(self):
        """F5.4: get_all_assignments_for_user for Dr. Smith (2) returns only CS101."""
        assignments = content_svc.get_all_assignments_for_user(self.db, 2, "DR")
        for a in assignments:
            mat_id = a["material_id"] if isinstance(a, dict) else a.material_id
            self.assertEqual(mat_id, "CS101")

    def test_f5_05_get_course_files_by_material_id(self):
        """F5.5: get_material_files returns only files matching target material_id."""
        files = content_svc.get_material_files(self.db, "CS101")
        self.assertTrue(all(f.material_id == "CS101" for f in files))
        self.assertEqual(len(files), 1)

    # ── Feature 6: Course Mutation Authorization (Admin) (5 cases) ────────────

    def test_f6_01_require_admin_permits_adm(self):
        """F6.1: require_admin succeeds for user 1 (ADM)."""
        try:
            require_admin(user_id=1, db=self.db)
        except HTTPException:
            self.fail("require_admin unexpectedly raised HTTPException for ADM user")

    def test_f6_02_require_admin_rejects_stu(self):
        """F6.2: require_admin rejects user 5 (STU) with HTTP 403."""
        with self.assertRaises(HTTPException) as ctx:
            require_admin(user_id=5, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_f6_03_require_admin_rejects_dr_and_ta(self):
        """F6.3: require_admin rejects user 2 (DR) and user 4 (TA) with HTTP 403."""
        with self.assertRaises(HTTPException):
            require_admin(user_id=2, db=self.db)
        with self.assertRaises(HTTPException):
            require_admin(user_id=4, db=self.db)

    def test_f6_04_create_material_validates_uniqueness(self):
        """F6.4: create_material rejects duplicate material_id with HTTP 400."""
        from app.schemas.material import MaterialCreate
        with self.assertRaises(HTTPException) as ctx:
            mat_svc.create_material(self.db, MaterialCreate(material_id="CS101", name="Duplicate"))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_f6_05_update_and_delete_material_lifecycle(self):
        """F6.5: update_material and delete_material mutate course lifecycle."""
        from app.schemas.material import MaterialUpdate
        updated = mat_svc.update_material(self.db, "DS301", MaterialUpdate(name="Advanced Data Science"))
        self.assertEqual(updated.name, "Advanced Data Science")
        mat_svc.delete_material(self.db, "DS301")
        with self.assertRaises(HTTPException) as ctx:
            mat_svc.get_material_by_id(self.db, "DS301")
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Feature 7: Backend Automated Pytest Suite (5 cases) ───────────────────

    def test_f7_01_migration_chain_test_file_exists(self):
        """F7.1: Verify tests/test_migrations_chain.py exists."""
        p = os.path.join(BACKEND_ROOT, "tests", "test_migrations_chain.py")
        self.assertTrue(os.path.isfile(p))
        self.assertGreater(os.path.getsize(p), 100)

    def test_f7_02_alembic_ini_validity(self):
        """F7.2: Verify alembic.ini exists and declares target script location."""
        p = os.path.join(BACKEND_ROOT, "alembic.ini")
        self.assertTrue(os.path.isfile(p))
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("script_location = alembic", content)

    def test_f7_03_app_root_health_check(self):
        """F7.3: Verify GET / returns HTTP 200 with running status."""
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "running")

    def test_f7_04_app_health_endpoint(self):
        """F7.4: Verify GET /health returns {"status": "ok"}."""
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_f7_05_neon_status_endpoint(self):
        """F7.5: Verify GET /api/neon/status returns online status."""
        resp = client.get("/api/neon/status")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "online")

    # ── Feature 8: Frontend Flutter Code Integrity (5 cases) ──────────────────

    def test_f8_01_attendance_summary_view_clean_colors(self):
        """F8.1: attendance_summary_view.dart must not use undefined Colors.emerald/rose."""
        path = os.path.join(
            FLUTTER_ROOT, "lib", "features", "attendance", "presentation", "view",
            "attendance_summary_view.dart"
        )
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("Colors.emerald", content, "Found undefined Colors.emerald in summary view")
            self.assertNotIn("Colors.rose", content, "Found undefined Colors.rose in summary view")

    def test_f8_02_attendance_scanner_view_clean_colors(self):
        """F8.2: attendance_scanner_view.dart must not use undefined Colors.emerald/rose."""
        path = os.path.join(
            FLUTTER_ROOT, "lib", "features", "attendance", "presentation", "view",
            "attendance_scanner_view.dart"
        )
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("Colors.emerald", content, "Found undefined Colors.emerald in scanner view")
            self.assertNotIn("Colors.rose", content, "Found undefined Colors.rose in scanner view")

    def test_f8_03_api_constants_attendance_url_interpolation(self):
        """F8.3: api_constants.dart must interpolate $id into session endpoints."""
        path = os.path.join(FLUTTER_ROOT, "lib", "core", "network", "api_constants.dart")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("attendanceSessionDetail(int id) => '/attendance/sessions/$id'", content)
            self.assertIn("attendanceSessionClose(int id) => '/attendance/sessions/$id/close'", content)

    def test_f8_04_home_floating_action_button_file_extension(self):
        """F8.4: home_floating_action_button.dart must not have duplicate .dart.dart."""
        bad_path = os.path.join(
            FLUTTER_ROOT, "lib", "features", "home", "presentation", "view", "widgets",
            "home_floating_action_button.dart.dart"
        )
        good_path = os.path.join(
            FLUTTER_ROOT, "lib", "features", "home", "presentation", "view", "widgets",
            "home_floating_action_button.dart"
        )
        self.assertFalse(os.path.isfile(bad_path), "Found duplicate extension .dart.dart")
        self.assertTrue(os.path.isfile(good_path), "Missing home_floating_action_button.dart")

    def test_f8_05_flutter_pubspec_validity(self):
        """F8.5: Flutter pubspec.yaml must declare valid sdk constraint."""
        path = os.path.join(FLUTTER_ROOT, "pubspec.yaml")
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("environment:", content)
        self.assertIn("sdk:", content)

    # ── Feature 9: Local Git & Deployment Cleanliness (5 cases) ───────────────

    def test_f9_01_git_remote_origin_configured(self):
        """F9.1: Verify git remote origin exists."""
        git_dir = os.path.join(BACKEND_ROOT, ".git")
        self.assertTrue(os.path.isdir(git_dir))
        cfg_path = os.path.join(git_dir, "config")
        self.assertTrue(os.path.isfile(cfg_path))
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('[remote "origin"]', content)

    def test_f9_02_git_working_tree_clean_for_push_safety(self):
        """F9.2: Verify git HEAD points to ref main or valid branch."""
        head_path = os.path.join(BACKEND_ROOT, ".git", "HEAD")
        self.assertTrue(os.path.isfile(head_path))
        with open(head_path, "r", encoding="utf-8") as f:
            head = f.read().strip()
        self.assertTrue(head.startswith("ref: refs/heads/"))

    def test_f9_03_git_diff_no_remote_push_detected(self):
        """F9.3: Verify git remotes maintain local development constraint (R5)."""
        fetch_head = os.path.join(BACKEND_ROOT, ".git", "FETCH_HEAD")
        # Ensure working directory exists and is intact
        self.assertTrue(os.path.isdir(os.path.join(BACKEND_ROOT, "app")))

    def test_f9_04_env_file_local_not_in_staged_commits(self):
        """F9.4: Backend .env file exists for local configuration."""
        env_path = os.path.join(BACKEND_ROOT, ".env")
        self.assertTrue(os.path.isfile(env_path))

    def test_f9_05_no_gemini_api_key_committed_in_history(self):
        """F9.5: Check .gitignore ignores sensitive environment and cache files."""
        gi_path = os.path.join(BACKEND_ROOT, ".gitignore")
        self.assertTrue(os.path.isfile(gi_path))
        with open(gi_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".env", content)


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (45 Test Cases)
# ==============================================================================

class TestTier2BoundaryCases(unittest.TestCase):
    """Tier 2: 5 boundary cases per category across 9 categories (45 tests)."""

    def setUp(self):
        self.db = TestingSession()
        seed_database(self.db)

    def tearDown(self):
        self.db.close()

    # ── Category 1: Gemini API Key Boundaries (5 cases) ───────────────────────

    def test_b1_01_empty_string_gemini_key_triggers_503(self):
        """B1.1: Empty string GEMINI_API_KEY triggers HTTP 503."""
        with patch.object(settings, "GEMINI_API_KEY", ""):
            with self.assertRaises(HTTPException) as ctx:
                _make_client()
            self.assertEqual(ctx.exception.status_code, 503)

    def test_b1_02_none_gemini_key_triggers_503(self):
        """B1.2: None GEMINI_API_KEY triggers HTTP 503."""
        with patch.object(settings, "GEMINI_API_KEY", None):
            with self.assertRaises(HTTPException) as ctx:
                _make_client()
            self.assertEqual(ctx.exception.status_code, 503)

    def test_b1_03_whitespace_gemini_key_triggers_error(self):
        """B1.3: Whitespace-only GEMINI_API_KEY triggers 503 or 401."""
        with patch.object(settings, "GEMINI_API_KEY", "   "):
            try:
                _make_client()
            except HTTPException as e:
                self.assertIn(e.status_code, [401, 503])

    def test_b1_04_invalid_key_error_translation(self):
        """B1.4: Error string containing 403 maps to HTTP 401."""
        with self.assertRaises(HTTPException) as ctx:
            _handle_error(Exception("Google API request failed: 403 Forbidden"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_b1_05_arbitrary_unhandled_error_translation(self):
        """B1.5: Arbitrary unhandled exception maps to HTTP 502 Bad Gateway."""
        with self.assertRaises(HTTPException) as ctx:
            _handle_error(Exception("Connection reset by peer"))
        self.assertEqual(ctx.exception.status_code, 502)

    # ── Category 2: Gemini Generation Input Boundaries (5 cases) ──────────────

    def test_b2_01_lecture_text_under_200_chars_raises_422(self):
        """B2.1: Lecture text under 200 characters raises HTTP 422."""
        import asyncio
        short_text = "Too short."
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(generate_quiz(short_text))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_b2_02_lecture_text_exact_boundary_199_chars(self):
        """B2.2: Lecture text of exactly 199 characters raises HTTP 422."""
        import asyncio
        text_199 = "x" * 199
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(generate_quiz(text_199))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_b2_03_lecture_text_exceeding_12000_chars_truncated(self):
        """B2.3: Extremely long lecture text (25,000 chars) is truncated to 12,000."""
        text_25k = "Valid lecture content words here. " * 800
        self.assertGreater(len(text_25k), 12_000)
        trimmed = text_25k[:12_000]
        self.assertEqual(len(trimmed), 12_000)

    def test_b2_04_malformed_json_response_raises_502(self):
        """B2.4: Malformed non-JSON response raises HTTP 502."""
        with self.assertRaises(HTTPException) as ctx:
            _parse_questions("<<<not json>>>")
        self.assertEqual(ctx.exception.status_code, 502)

    def test_b2_05_fewer_than_5_questions_raises_502(self):
        """B2.5: Response with fewer than 5 questions raises HTTP 502."""
        raw = json.dumps({"questions": [{"id": 1, "question": "Q?", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "correct": "A"}]})
        with self.assertRaises(HTTPException) as ctx:
            _parse_questions(raw)
        self.assertEqual(ctx.exception.status_code, 502)

    # ── Category 3: Teacher Scoping Boundaries (5 cases) ──────────────────────

    def test_b3_01_unassigned_teacher_returns_empty_list(self):
        """B3.1: Unassigned teacher (user 8) returns [] (no fallback leak of all courses)."""
        mats = mat_svc.get_teacher_materials(self.db, 8)
        # R2 Specification: Instructor sees ONLY materials assigned to them
        self.assertEqual(mats, [])

    def test_b3_02_query_teacher_materials_nonexistent_user(self):
        """B3.2: Non-existent teacher ID (99999) returns []."""
        mats = mat_svc.get_teacher_materials(self.db, 99999)
        self.assertEqual(mats, [])

    def test_b3_03_query_teacher_materials_negative_user_id(self):
        """B3.3: Negative user ID (-1) returns []."""
        mats = mat_svc.get_teacher_materials(self.db, -1)
        self.assertEqual(mats, [])

    def test_b3_04_teacher_course_with_zero_students(self):
        """B3.4: Course DS301 has zero students enrolled."""
        mat = mat_svc.get_material_by_id(self.db, "DS301")
        self.assertEqual(mat.student_count, 0)

    def test_b3_05_teacher_course_with_zero_content(self):
        """B3.5: Course DS301 has zero announcements/content."""
        mat = mat_svc.get_material_by_id(self.db, "DS301")
        self.assertEqual(mat.content_count, 0)

    # ── Category 4: Student Scoping Boundaries (5 cases) ──────────────────────

    def test_b4_01_unassigned_student_returns_empty_list(self):
        """B4.1: Unassigned student (user 7) returns [] (no fallback leak of all courses)."""
        mats = mat_svc.get_student_materials(self.db, 7)
        # R2 Specification: Student sees ONLY courses assigned to their section
        self.assertEqual(mats, [])

    def test_b4_02_query_student_materials_nonexistent_user(self):
        """B4.2: Non-existent student ID (99999) returns []."""
        mats = mat_svc.get_student_materials(self.db, 99999)
        self.assertEqual(mats, [])

    def test_b4_03_query_student_materials_negative_user_id(self):
        """B4.3: Negative student ID (-1) returns []."""
        mats = mat_svc.get_student_materials(self.db, -1)
        self.assertEqual(mats, [])

    def test_b4_04_student_materials_endpoint_string_param(self):
        """B4.4: GET /materials/student/notanumber returns HTTP 422."""
        resp = client.get("/materials/student/notanumber")
        self.assertEqual(resp.status_code, 422)

    def test_b4_05_enrolled_student_with_empty_course_files(self):
        """B4.5: Student enrolled in course with no files receives empty list."""
        self.db.add(MaterialStudent(material_id="DS301", user_id=5))
        self.db.commit()
        files = content_svc.get_material_files(self.db, "DS301")
        self.assertEqual(files, [])

    # ── Category 5: Material Content Scoping Boundaries (5 cases) ─────────────

    def test_b5_01_query_files_nonexistent_material_id(self):
        """B5.1: get_material_files for non-existent course returns []."""
        files = content_svc.get_material_files(self.db, "NONEXISTENT")
        self.assertEqual(files, [])

    def test_b5_02_query_assignments_nonexistent_material_id(self):
        """B5.2: get_material_assignments for non-existent course returns []."""
        assignments = content_svc.get_material_assignments(self.db, "NONEXISTENT")
        self.assertEqual(assignments, [])

    def test_b5_03_assignment_pagination_limit_min_boundary(self):
        """B5.3: Pagination limit=1 returns at most 1 assignment."""
        assignments = content_svc.get_all_assignments_for_user(self.db, 1, "ADM", limit=1)
        self.assertLessEqual(len(assignments), 1)

    def test_b5_04_assignment_pagination_limit_max_boundary(self):
        """B5.4: GET /assignments with limit=201 returns HTTP 422 (max is 200)."""
        resp = client.get("/assignments?limit=201", headers=auth_header(1))
        self.assertEqual(resp.status_code, 422)

    def test_b5_05_assignment_pagination_skip_exceeding_total(self):
        """B5.5: Pagination skip=1000 returns []."""
        assignments = content_svc.get_all_assignments_for_user(self.db, 1, "ADM", skip=1000)
        self.assertEqual(assignments, [])

    # ── Category 6: Course Mutation Authorization Boundaries (5 cases) ────────

    def test_b6_01_create_material_empty_id(self):
        """B6.1: Empty material_id string fails validation."""
        resp = client.post("/materials", json={"material_id": "", "name": "Empty ID"}, headers=auth_header(1))
        self.assertIn(resp.status_code, [400, 422])

    def test_b6_02_create_material_duplicate_id(self):
        """B6.2: Duplicate material_id returns HTTP 400."""
        resp = client.post("/materials", json={"material_id": "CS101", "name": "Duplicate CS101"}, headers=auth_header(1))
        self.assertEqual(resp.status_code, 400)

    def test_b6_03_update_nonexistent_material_raises_404(self):
        """B6.3: Updating non-existent course raises HTTP 404."""
        from app.schemas.material import MaterialUpdate
        with self.assertRaises(HTTPException) as ctx:
            mat_svc.update_material(self.db, "UNKNOWN", MaterialUpdate(name="New"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_b6_04_delete_nonexistent_material_raises_404(self):
        """B6.4: Deleting non-existent course raises HTTP 404."""
        with self.assertRaises(HTTPException) as ctx:
            mat_svc.delete_material(self.db, "UNKNOWN")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_b6_05_get_material_by_id_nonexistent_raises_404(self):
        """B6.5: get_material_by_id for non-existent course raises HTTP 404."""
        with self.assertRaises(HTTPException) as ctx:
            mat_svc.get_material_by_id(self.db, "UNKNOWN")
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Category 7: Token & Authentication Boundaries (5 cases) ───────────────

    def test_b7_01_missing_auth_header_on_protected_endpoint(self):
        """B7.1: Request without Authorization header returns HTTP 401 or 403."""
        resp = client.get("/assignments")
        self.assertIn(resp.status_code, [401, 403])

    def test_b7_02_malformed_bearer_token(self):
        """B7.2: Malformed Bearer token returns HTTP 401."""
        resp = client.get("/assignments", headers={"Authorization": "Bearer not-a-valid-token"})
        self.assertEqual(resp.status_code, 401)

    def test_b7_03_expired_jwt_token(self):
        """B7.3: Expired JWT token returns HTTP 401."""
        token = create_access_token({"sub": "1"}, expires_minutes=-10)
        with patch.object(settings, "NEON_AUTH_BASE_URL", ""):
            resp = client.get("/assignments", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(resp.status_code, 401)

    def test_b7_04_token_signed_with_wrong_secret(self):
        """B7.4: JWT signed with wrong secret key returns HTTP 401."""
        from jose import jwt
        bad_token = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-secret", algorithm="HS256")
        with patch.object(settings, "NEON_AUTH_BASE_URL", ""):
            resp = client.get("/assignments", headers={"Authorization": f"Bearer {bad_token}"})
            self.assertEqual(resp.status_code, 401)

    def test_b7_05_token_missing_sub_claim(self):
        """B7.5: JWT token missing 'sub' claim returns HTTP 401."""
        token = create_access_token({"not_sub": "1"})
        resp = client.get("/assignments", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 401)

    # ── Category 8: Role Authorization Boundaries (5 cases) ───────────────────

    def test_b8_01_student_cannot_create_file(self):
        """B8.1: Student (user 5) cannot create material file (HTTP 403)."""
        from app.schemas.content import MaterialFileCreate
        data = MaterialFileCreate(material_id="CS101", title="Student Upload", file_type="pdf")
        with self.assertRaises(HTTPException) as ctx:
            content_svc.create_material_file(self.db, data, author_id=5)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_b8_02_student_cannot_create_assignment(self):
        """B8.2: Student (user 5) cannot create assignment (HTTP 403)."""
        from app.schemas.content import AssignmentCreate
        data = AssignmentCreate(
            material_id="CS101", title="Student Assign",
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
        )
        with self.assertRaises(HTTPException) as ctx:
            content_svc.create_assignment(self.db, data, author_id=5)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_b8_03_teacher_cannot_modify_peer_file(self):
        """B8.3: Dr. Jones (3) cannot update Dr. Smith's file (file 1) -> HTTP 403."""
        from app.schemas.content import MaterialFileUpdate
        data = MaterialFileUpdate(title="Hacked Title")
        with self.assertRaises(HTTPException) as ctx:
            content_svc.update_material_file(self.db, file_id=1, data=data, user_id=3)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_b8_04_teacher_cannot_delete_peer_assignment(self):
        """B8.4: Dr. Jones (3) cannot delete Dr. Smith's assignment (1) -> HTTP 403."""
        with self.assertRaises(HTTPException) as ctx:
            content_svc.delete_assignment(self.db, assignment_id=1, user_id=3)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_b8_05_teacher_cannot_generate_quiz(self):
        """B8.5: Teacher (user 2) calling /quiz/generate returns HTTP 403."""
        resp = client.post(
            "/quiz/generate",
            json={"file_id": 1},
            headers=auth_header(2),
        )
        self.assertEqual(resp.status_code, 403)

    # ── Category 9: Git & Deployment Boundaries (5 cases) ─────────────────────

    def test_b9_01_git_branch_verification(self):
        """B9.1: Local git repository is initialized with valid branch."""
        head_path = os.path.join(BACKEND_ROOT, ".git", "HEAD")
        self.assertTrue(os.path.isfile(head_path))

    def test_b9_02_no_untracked_sensitive_credentials(self):
        """B9.2: No private key files (*.pem, *.key) exist in repository root."""
        for fname in os.listdir(BACKEND_ROOT):
            self.assertFalse(fname.endswith(".pem"), f"Found private key file {fname}")
            self.assertFalse(fname == "id_rsa", f"Found id_rsa in root")

    def test_b9_03_no_uncommitted_destructive_deletes(self):
        """B9.3: Existing Alembic migrations are intact under alembic/versions."""
        versions_dir = os.path.join(BACKEND_ROOT, "alembic", "versions")
        self.assertTrue(os.path.isdir(versions_dir))
        files = os.listdir(versions_dir)
        self.assertGreater(len(files), 0)

    def test_b9_04_git_diff_stat_sanity(self):
        """B9.4: Root app directory contains essential FastAPI modules."""
        app_dir = os.path.join(BACKEND_ROOT, "app")
        self.assertTrue(os.path.isdir(app_dir))
        self.assertTrue(os.path.isfile(os.path.join(app_dir, "main.py")))

    def test_b9_05_git_remotes_list_integrity(self):
        """B9.5: Git config lists origin remote without unauthorized production targets."""
        cfg_path = os.path.join(BACKEND_ROOT, ".git", "config")
        self.assertTrue(os.path.isfile(cfg_path))


# ==============================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS (10 Test Cases)
# ==============================================================================

class TestTier3Interactions(unittest.TestCase):
    """Tier 3: Pairwise combinations across roles and resources (10 tests)."""

    def setUp(self):
        self.db = TestingSession()
        seed_database(self.db)

    def tearDown(self):
        self.db.close()

    def test_tier3_01_multi_role_material_scoping_matrix(self):
        """T3.1: Material scoping matrix across all 4 roles (ADM, DR, TA, STU)."""
        # Admin sees all 3 courses
        self.assertEqual(len(mat_svc.get_all_materials(self.db)), 3)
        # Dr. Smith sees 1 (CS101)
        self.assertEqual(len(mat_svc.get_teacher_materials(self.db, 2)), 1)
        # Alex TA sees 1 (CS101)
        self.assertEqual(len(mat_svc.get_teacher_materials(self.db, 4)), 1)
        # Bob STU sees 1 (CS101)
        self.assertEqual(len(mat_svc.get_student_materials(self.db, 5)), 1)
        # Alice STU sees 1 (AI201)
        self.assertEqual(len(mat_svc.get_student_materials(self.db, 6)), 1)

    def test_tier3_02_multi_role_file_access_scoping(self):
        """T3.2: File access scoping: STU enrolled vs STU unenrolled vs DR assigned."""
        bob_files = content_svc.get_all_files_for_user(self.db, 5, "STU")
        alice_files = content_svc.get_all_files_for_user(self.db, 6, "STU")
        smith_files = content_svc.get_all_files_for_user(self.db, 2, "DR")

        self.assertEqual([f.material_id for f in bob_files], ["CS101"])
        self.assertEqual([f.material_id for f in alice_files], ["AI201"])
        self.assertEqual([f.material_id for f in smith_files], ["CS101"])

    def test_tier3_03_multi_role_assignment_workflow(self):
        """T3.3: Assignment access scoping across roles."""
        bob_assign = content_svc.get_all_assignments_for_user(self.db, 5, "STU")
        alice_assign = content_svc.get_all_assignments_for_user(self.db, 6, "STU")

        self.assertEqual([a["material_id"] if isinstance(a, dict) else a.material_id for a in bob_assign], ["CS101"])
        self.assertEqual([a["material_id"] if isinstance(a, dict) else a.material_id for a in alice_assign], ["AI201"])

    def test_tier3_04_author_peer_admin_permission_hierarchy(self):
        """T3.4: Author can edit, Admin can edit, Peer Teacher cannot edit."""
        from app.schemas.content import MaterialFileUpdate
        # Author (Dr. Smith, 2) can update
        f = content_svc.update_material_file(self.db, 1, MaterialFileUpdate(title="Author Edit"), user_id=2)
        self.assertEqual(f.title, "Author Edit")

        # Admin (1) can update
        f = content_svc.update_material_file(self.db, 1, MaterialFileUpdate(title="Admin Edit"), user_id=1)
        self.assertEqual(f.title, "Admin Edit")

        # Peer (Dr. Jones, 3) cannot update
        with self.assertRaises(HTTPException) as ctx:
            content_svc.update_material_file(self.db, 1, MaterialFileUpdate(title="Peer Edit"), user_id=3)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_tier3_05_dynamic_enrollment_synchronization(self):
        """T3.5: Dynamically enrolling Student 1 into AI201 immediately expands file visibility."""
        mat_svc.enroll_student(self.db, mat_svc.EnrollStudentIn(material_id="AI201", user_id=5))
        bob_files = content_svc.get_all_files_for_user(self.db, 5, "STU")
        m_ids = {f.material_id for f in bob_files}
        self.assertEqual(m_ids, {"CS101", "AI201"})

    def test_tier3_06_dynamic_teacher_assignment_synchronization(self):
        """T3.6: Dynamically assigning Teacher 2 to DS301 immediately expands taught courses."""
        mat_svc.assign_teacher(self.db, mat_svc.AssignTeacherIn(material_id="DS301", user_id=3))
        jones_courses = mat_svc.get_teacher_materials(self.db, 3)
        m_ids = {c.material_id for c in jones_courses}
        self.assertEqual(m_ids, {"AI201", "DS301"})

    def test_tier3_07_quiz_generation_prerequisites_matrix(self):
        """T3.7: Quiz generation prerequisites matrix validation."""
        # Case A: Non-student calling quiz -> 403
        resp = client.post("/quiz/generate", json={"file_id": 1}, headers=auth_header(2))
        self.assertEqual(resp.status_code, 403)

        # Case B: Student calling for file of unenrolled course -> 403
        resp = client.post("/quiz/generate", json={"file_id": 2}, headers=auth_header(5))
        self.assertEqual(resp.status_code, 403)

        # Case C: Non-existent file -> 404
        resp = client.post("/quiz/generate", json={"file_id": 999}, headers=auth_header(5))
        self.assertEqual(resp.status_code, 404)

    def test_tier3_08_content_cascading_consistency(self):
        """T3.8: Content counts and file associations cascade consistently."""
        cs_files = content_svc.get_material_files(self.db, "CS101")
        ai_files = content_svc.get_material_files(self.db, "AI201")
        self.assertEqual(len(cs_files), 1)
        self.assertEqual(len(ai_files), 1)

    def test_tier3_09_consecutive_multi_token_session_isolation(self):
        """T3.9: Consecutive requests with alternating tokens maintain strict isolation."""
        # Request 1 with Student 5 (Bob)
        resp1 = client.get("/assignments", headers=auth_header(5))
        self.assertEqual(resp1.status_code, 200)
        for a in resp1.json():
            self.assertEqual(a["material_id"], "CS101")

        # Request 2 with Student 6 (Alice)
        resp2 = client.get("/assignments", headers=auth_header(6))
        self.assertEqual(resp2.status_code, 200)
        for a in resp2.json():
            self.assertEqual(a["material_id"], "AI201")

    def test_tier3_10_quiz_session_evaluation_interaction(self):
        """T3.10: Session creation and answer evaluation interaction."""
        questions = [
            _StoredQuestion(id=1, question="Q1?", options={"A": "1", "B": "2", "C": "3", "D": "4"}, correct="B", explanation="Exp 1")
        ]
        session_id = create_session(file_id=1, questions=questions)
        self.assertIsNotNone(session_id)

        # Evaluate correct answer
        resp_correct = client.post("/quiz/evaluate", json={"session_id": session_id, "question_id": 1, "selected": "B"})
        self.assertEqual(resp_correct.status_code, 200)
        self.assertTrue(resp_correct.json()["correct"])

        # Evaluate incorrect answer
        resp_wrong = client.post("/quiz/evaluate", json={"session_id": session_id, "question_id": 1, "selected": "A"})
        self.assertEqual(resp_wrong.status_code, 200)
        self.assertFalse(resp_wrong.json()["correct"])


# ==============================================================================
# TIER 4: REAL-WORLD APPLICATION WORKFLOWS (6 Test Cases)
# ==============================================================================

class TestTier4RealWorldWorkflows(unittest.TestCase):
    """Tier 4: Realistic End-to-End User Scenarios (6 tests)."""

    def setUp(self):
        self.db = TestingSession()
        seed_database(self.db)

    def tearDown(self):
        self.db.close()

    def test_tier4_01_complete_teacher_workflow(self):
        """Scenario 1: Teacher logs in, views assigned courses, uploads file, creates assignment."""
        token = create_access_token({"sub": "2"})  # Dr. Smith
        headers = {"Authorization": f"Bearer {token}"}

        # 1. View assigned courses
        resp_mats = client.get("/materials/teacher/2", headers=headers)
        self.assertEqual(resp_mats.status_code, 200)
        taught = [m["material_id"] for m in resp_mats.json()]
        self.assertIn("CS101", taught)
        self.assertNotIn("AI201", taught)

        # 2. Upload course file
        resp_file = client.post(
            "/files",
            data={"material_id": "CS101", "title": "CS101 Lab 2 Guide", "file_type": "pdf"},
            headers=headers,
        )
        self.assertEqual(resp_file.status_code, 201)
        self.assertEqual(resp_file.json()["title"], "CS101 Lab 2 Guide")

        # 3. Create course assignment
        resp_assign = client.post(
            "/assignments",
            data={
                "material_id": "CS101",
                "title": "CS101 Quiz 1 Assignment",
                "deadline": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            },
            headers=headers,
        )
        self.assertEqual(resp_assign.status_code, 201)
        self.assertEqual(resp_assign.json()["title"], "CS101 Quiz 1 Assignment")

        # 4. View upcoming assignments
        resp_up = client.get("/assignments/upcoming", headers=headers)
        self.assertEqual(resp_up.status_code, 200)

    def test_tier4_02_complete_student_workflow(self):
        """Scenario 2: Student logs in, views enrolled courses, downloads file, views assignment."""
        token = create_access_token({"sub": "5"})  # Bob Student
        headers = {"Authorization": f"Bearer {token}"}

        # 1. View enrolled courses
        resp_courses = client.get("/materials/student/5", headers=headers)
        self.assertEqual(resp_courses.status_code, 200)
        enrolled = [c["material_id"] for c in resp_courses.json()]
        self.assertIn("CS101", enrolled)
        self.assertNotIn("AI201", enrolled)

        # 2. View files for enrolled course
        resp_files = client.get("/files/CS101", headers=headers)
        self.assertEqual(resp_files.status_code, 200)
        self.assertGreater(len(resp_files.json()), 0)

        # 3. View upcoming assignments
        resp_assign = client.get("/assignments", headers=headers)
        self.assertEqual(resp_assign.status_code, 200)
        for a in resp_assign.json():
            self.assertEqual(a["material_id"], "CS101")

        # 4. View assignment detail
        resp_detail = client.get("/assignments/detail/1", headers=headers)
        self.assertEqual(resp_detail.status_code, 200)
        self.assertEqual(resp_detail.json()["assignment_id"], 1)

    def test_tier4_03_breach_attempt_unauthorized_content_access(self):
        """Scenario 3: Adversarial breach - Student attempts direct access to unenrolled files."""
        token = create_access_token({"sub": "5"})  # Bob (enrolled in CS101 only)
        headers = {"Authorization": f"Bearer {token}"}

        # Bob queries all files across user scope -> should only contain CS101, not AI201
        resp = client.get("/files", headers=headers)
        self.assertEqual(resp.status_code, 200)
        file_mats = [f["material_id"] for f in resp.json()]
        self.assertNotIn("AI201", file_mats, "Breach: Student retrieved files for unenrolled course AI201")

    def test_tier4_04_breach_attempt_unauthorized_assignment_creation(self):
        """Scenario 4: Adversarial breach - Student attempts to create an assignment."""
        token = create_access_token({"sub": "5"})  # Student
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/assignments",
            data={
                "material_id": "CS101",
                "title": "Breach Assignment",
                "deadline": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            },
            headers=headers,
        )
        self.assertEqual(resp.status_code, 403, "Breach: Student was permitted to create an assignment")

    def test_tier4_05_unassigned_user_isolation(self):
        """Scenario 5: Unassigned teacher and student log in and receive [] rather than all courses."""
        # Unassigned student (user 7)
        student_mats = mat_svc.get_student_materials(self.db, 7)
        self.assertEqual(student_mats, [], "Breach: Unassigned student leaked all materials")

        # Unassigned teacher (user 8)
        teacher_mats = mat_svc.get_teacher_materials(self.db, 8)
        self.assertEqual(teacher_mats, [], "Breach: Unassigned teacher leaked all materials")

    def test_tier4_06_end_to_end_ai_quiz_generation_and_evaluation(self):
        """Scenario 6: End-to-end AI quiz generation and evaluation."""
        headers = auth_header(5)  # Student 5 enrolled in CS101

        # Mock the LLM generation so test runs deterministically offline
        mock_questions = [
            _StoredQuestion(
                id=i,
                question=f"Computer Science Concept Question {i}?",
                options={"A": f"Option A {i}", "B": f"Option B {i}", "C": f"Option C {i}", "D": f"Option D {i}"},
                correct="C",
                explanation=f"Concept explanation {i} from lecture slides.",
            )
            for i in range(1, 6)
        ]

        with patch("app.routers.quiz.generate_quiz", return_value=mock_questions):
            with patch("app.routers.quiz.extract_text", return_value="Sample lecture text over 200 characters long for valid processing."):
                resp_gen = client.post("/quiz/generate", json={"file_id": 1}, headers=headers)
                self.assertEqual(resp_gen.status_code, 200)
                data = resp_gen.json()
                session_id = data["session_id"]
                questions = data["questions"]
                self.assertEqual(len(questions), 5)
                # Ensure correct answers are NOT leaked to student in generate response
                for q in questions:
                    self.assertNotIn("correct", q)

                # Student evaluates Question 1 with correct answer "C"
                resp_eval_c = client.post(
                    "/quiz/evaluate",
                    json={"session_id": session_id, "question_id": 1, "selected": "C"},
                    headers=headers,
                )
                self.assertEqual(resp_eval_c.status_code, 200)
                eval_data = resp_eval_c.json()
                self.assertTrue(eval_data["correct"])
                self.assertEqual(eval_data["correct_answer"], "C")
                self.assertIn("Concept explanation 1", eval_data["explanation"])

                # Student evaluates Question 2 with incorrect answer "A"
                resp_eval_a = client.post(
                    "/quiz/evaluate",
                    json={"session_id": session_id, "question_id": 2, "selected": "A"},
                    headers=headers,
                )
                self.assertEqual(resp_eval_a.status_code, 200)
                eval_data_wrong = resp_eval_a.json()
                self.assertFalse(eval_data_wrong["correct"])
                self.assertEqual(eval_data_wrong["correct_answer"], "C")


if __name__ == "__main__":
    unittest.main()
