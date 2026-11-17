import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from app.models.attendance import AttendanceSession, AttendanceRecord
from app.models.material import Material, MaterialStudent
from app.models.user import User
from app.schemas.attendance import AttendanceSessionCreate, AttendanceMarkRequest
from app.services.attendance_service import (
    create_attendance_session,
    get_session_attendance_sheet,
    mark_student_attendance,
    batch_mark_attendance,
    student_public_check_in,
)


class TestAttendanceSheetService(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.teacher_user = User(user_id=1, name="Dr. Ahmed", type_code="DR")
        self.student_1 = User(user_id=10, name="Ali Hassan", uni_code="WE-2026-001", email="ali@we.edu.eg")
        self.student_2 = User(user_id=11, name="Sara Omar", uni_code="WE-2026-002", email="sara@we.edu.eg")
        self.material = Material(material_id="CS101", name="Computer Science Intro")

    def test_01_create_attendance_session(self):
        self.mock_db.query.return_value.filter.return_value.first.return_value = self.material
        def mock_refresh(obj):
            obj.session_id = 100
            obj.created_at = datetime.now(timezone.utc)
        self.mock_db.refresh.side_effect = mock_refresh
        data = AttendanceSessionCreate(material_id="CS101", title="Lecture 1", duration_minutes=30)
        
        session_out = create_attendance_session(self.mock_db, self.teacher_user, data)
        self.assertEqual(session_out.material_id, "CS101")
        self.assertTrue(session_out.token.startswith("WE-ATT-"))
        self.assertTrue(session_out.qr_payload.startswith("eru_attendance:"))
        self.assertTrue(session_out.is_active)

    def test_02_get_session_attendance_sheet(self):
        session = AttendanceSession(
            session_id=100,
            material_id="CS101",
            created_by=1,
            title="Lecture 1",
            token="WE-ATT-TOKEN123",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        record = AttendanceRecord(
            record_id=1,
            session_id=100,
            material_id="CS101",
            student_id=10,
            status="PRESENT",
            scanned_at=datetime.now(timezone.utc),
        )

        # Mock queries for session, material, enrolled students, records
        def mock_query_side_effect(model):
            q = MagicMock()
            if model == AttendanceSession:
                q.filter.return_value.first.return_value = session
            elif model == Material:
                q.filter.return_value.first.return_value = self.material
            elif model == User:
                # Enrolled students query
                q.join.return_value.filter.return_value.order_by.return_value.all.return_value = [self.student_1, self.student_2]
            elif model == AttendanceRecord:
                q.filter.return_value.all.return_value = [record]
            return q

        self.mock_db.query.side_effect = mock_query_side_effect

        sheet = get_session_attendance_sheet(self.mock_db, 100)
        self.assertEqual(sheet.session_id, 100)
        self.assertEqual(sheet.summary.total_enrolled, 2)
        self.assertEqual(sheet.summary.present_count, 1)
        self.assertEqual(sheet.summary.absent_count, 1)
        self.assertEqual(len(sheet.students), 2)
        self.assertEqual(sheet.students[0].status, "PRESENT")
        self.assertEqual(sheet.students[1].status, "ABSENT")

    def test_03_mark_student_attendance(self):
        session = AttendanceSession(
            session_id=100,
            material_id="CS101",
            created_by=1,
            title="Lecture 1",
            token="WE-ATT-TOKEN123",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        
        # Test marking student 11 as LATE
        def mock_query_side_effect(model):
            q = MagicMock()
            if model == AttendanceSession:
                q.filter.return_value.first.return_value = session
            elif model == AttendanceRecord:
                q.filter.return_value.first.return_value = None  # no existing record
                q.filter.return_value.all.return_value = []
            elif model == Material:
                q.filter.return_value.first.return_value = self.material
            elif model == User:
                q.join.return_value.filter.return_value.order_by.return_value.all.return_value = [self.student_1, self.student_2]
            return q

        self.mock_db.query.side_effect = mock_query_side_effect
        sheet = mark_student_attendance(self.mock_db, 100, 11, "LATE")
        self.mock_db.add.assert_called()
        self.mock_db.commit.assert_called()

    def test_04_student_public_check_in_success(self):
        session = AttendanceSession(
            session_id=200,
            material_id="CS101",
            created_by=1,
            title="Interactive Session",
            token="WE-ATT-ABC123",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        enrollment = MaterialStudent(material_id="CS101", user_id=10)

        def mock_query_side_effect(model):
            q = MagicMock()
            if model == AttendanceSession:
                q.filter.return_value.first.return_value = session
            elif model == User:
                q.filter.return_value.first.return_value = self.student_1
            elif model == MaterialStudent:
                q.filter.return_value.first.return_value = enrollment
            elif model == AttendanceRecord:
                q.filter.return_value.first.return_value = None
            elif model == Material:
                q.filter.return_value.first.return_value = self.material
            return q

        self.mock_db.query.side_effect = mock_query_side_effect
        res = student_public_check_in(self.mock_db, "WE-ATT-ABC123", "WE-2026-001")
        self.assertTrue(res.success)
        self.assertEqual(res.status, "PRESENT")
        self.assertEqual(res.student_name, "Ali Hassan")
        self.assertEqual(res.course_name, "Computer Science Intro")

    def test_05_student_public_check_in_with_qr_prefix(self):
        session = AttendanceSession(
            session_id=200,
            material_id="CS101",
            created_by=1,
            title="Interactive Session",
            token="WE-ATT-ABC123",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        enrollment = MaterialStudent(material_id="CS101", user_id=10)

        def mock_query_side_effect(model):
            q = MagicMock()
            if model == AttendanceSession:
                q.filter.return_value.first.return_value = session
            elif model == User:
                q.filter.return_value.first.return_value = self.student_1
            elif model == MaterialStudent:
                q.filter.return_value.first.return_value = enrollment
            elif model == AttendanceRecord:
                q.filter.return_value.first.return_value = None
            elif model == Material:
                q.filter.return_value.first.return_value = self.material
            return q

        self.mock_db.query.side_effect = mock_query_side_effect
        # Test full QR code payload with prefix eru_attendance:
        res = student_public_check_in(self.mock_db, "eru_attendance:WE-ATT-ABC123", "WE-2026-001")
        self.assertTrue(res.success)
        self.assertEqual(res.student_uni_code, "WE-2026-001")


if __name__ == "__main__":
    unittest.main()
