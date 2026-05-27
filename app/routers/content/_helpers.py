import os, uuid, shutil
from fastapi import UploadFile

UPLOAD_DIR = "uploads/content"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_file(file: UploadFile) -> tuple[str, int] | tuple[None, None]:
    """Save an uploaded file and return (path, size_bytes). Both None if no file."""
    if not file:
        return None, None
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    size = os.path.getsize(path)
    return path, size
