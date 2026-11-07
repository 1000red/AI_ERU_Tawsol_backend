import os, uuid, shutil
from fastapi import UploadFile
from app.services.neon_storage import neon_storage

is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
UPLOAD_DIR = "/tmp/uploads/content" if is_serverless else "uploads/content"
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except Exception:
    pass


def save_file(file: UploadFile) -> tuple[str, int] | tuple[None, None]:
    """Save an uploaded file to local disk and Neon Object Storage if enabled."""
    if not file:
        return None, None
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    except Exception:
        pass
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    size = os.path.getsize(path)

    # If Neon Object Storage is configured, sync to Neon bucket
    if neon_storage.is_configured:
        try:
            with open(path, "rb") as f:
                neon_storage.upload_file(
                    file_obj=f,
                    object_key=f"content/{filename}",
                    content_type=file.content_type or "application/octet-stream",
                )
        except Exception:
            pass

    return path, size
