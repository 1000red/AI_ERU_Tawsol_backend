import uuid
from pathlib import Path
from datetime import datetime


def generate_unique_filename(original_filename: str) -> str:
    """Generate a UUID-based filename while preserving the file extension."""
    ext = Path(original_filename).suffix.lower() or ".bin"
    return f"{uuid.uuid4().hex}{ext}"


def build_s3_key(category: str, user_id: int, filename: str) -> str:
    """
    Build an S3 object key.
    Format: <category>/<user_id>/<uuid>.<ext>
    Example: chat/42/a1b2c3d4.jpg
    """
    unique_name = generate_unique_filename(filename)
    return f"{category}/{user_id}/{unique_name}"


def paginate(query, skip: int = 0, limit: int = 100):
    """Apply offset/limit pagination to a SQLAlchemy query."""
    return query.offset(skip).limit(limit)


def format_datetime(dt: datetime | None) -> str | None:
    """Return ISO 8601 string or None."""
    return dt.isoformat() if dt else None


def is_valid_university_code(code: str) -> bool:
    """Basic validation: non-empty, alphanumeric, max 20 chars."""
    return bool(code) and code.isalnum() and len(code) <= 20
