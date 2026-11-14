import os, uuid, shutil
from fastapi import UploadFile, HTTPException
from app.services.neon_storage import neon_storage

ALLOWED_CONTENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".mp3", ".m4a", ".ogg", ".wav",
    ".mp4", ".mov", ".m4v",
    ".zip", ".rar", ".7z",
}

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
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_CONTENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"نوع الملف غير مسموح به لأسباب أمنية. الامتدادات المصرح بها: {', '.join(sorted(ALLOWED_CONTENT_EXTENSIONS))}",
        )

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    except Exception:
        pass
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    size = os.path.getsize(path)

    # If Neon Object Storage is configured, sync to Neon bucket and return permanent public URL
    if neon_storage.is_configured:
        try:
            with open(path, "rb") as f:
                ok, s3_url = neon_storage.upload_file(
                    file_obj=f,
                    object_key=f"content/{filename}",
                    content_type=file.content_type or "application/octet-stream",
                )
                if ok and s3_url:
                    return s3_url, size
        except Exception:
            pass

    return path, size
