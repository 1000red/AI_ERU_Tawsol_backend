import pytest
from unittest.mock import MagicMock
from app.models.content import MaterialFile
from app.schemas.content import MaterialFileCreate
from app.services.content_service import material_files as mf_svc


def test_create_material_file_sanitization():
    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = MagicMock(user_id=1, type_code="DR")

    data = MaterialFileCreate(
        material_id="C1",
        title="Lecture 1 - Operating Systems",
        file_type="pdf",
        description="First lecture slides",
    )

    created = mf_svc.create_material_file(
        mock_db,
        data,
        author_id=1,
        file_path="uploads/content/test.pdf",
        file_size=1024,
    )

    assert mock_db.add.called
    assert mock_db.commit.called
    assert mock_db.refresh.called


def test_create_material_file_rejects_student():
    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = MagicMock(user_id=10, type_code="STU")

    data = MaterialFileCreate(
        material_id="C1",
        title="Student Notes",
        file_type="pdf",
    )

    with pytest.raises(Exception) as excinfo:
        mf_svc.create_material_file(mock_db, data, author_id=10)

    assert "Students cannot create content" in str(excinfo.value)
