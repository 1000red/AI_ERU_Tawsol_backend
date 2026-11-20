import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.core.config import settings
from app.models.content import MaterialFile
from app.schemas.content import MaterialFileCreate, MaterialFileUpdate, MaterialFileOut
from app.services import content_service as svc
from app.routers.content._helpers import save_file
from app.services.neon_storage import neon_storage

router = APIRouter(prefix="/files", tags=["Material Files"])


@router.get("", response_model=list[MaterialFileOut])
def get_all_files(
    file_type: Optional[str] = Query(None, description="pdf | word | ppt | image | video | link …"),
    skip:      int           = Query(0, ge=0),
    limit:     int           = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    """Return all material files across the current user's enrolled / taught courses."""
    user = svc.get_user_info(db, user_id)
    return svc.get_all_files_for_user(
        db, user_id, user.type_code,
        file_type=file_type, skip=skip, limit=limit,
    )


@router.get("/download/{file_id}")
@router.get("/{file_id}/download")
def download_material_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    """Download or redirect to the material file content."""
    mf = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
    if not mf:
        raise HTTPException(status_code=404, detail="File not found")

    if mf.link_url:
        return RedirectResponse(url=mf.link_url, status_code=302)

    if mf.file_path and mf.file_path.startswith("http"):
        return RedirectResponse(url=mf.file_path, status_code=302)

    # If stored in Neon S3 storage
    if mf.file_path and neon_storage.is_configured:
        key = mf.file_path.strip("/")
        if key.startswith("tmp/"):
            key = key[4:]
        if key.startswith("uploads/"):
            key = key[8:]

        # Public HTTPS URL from Neon storage bucket
        public_url = f"{settings.AWS_ENDPOINT_URL_S3.rstrip('/')}/{settings.NEON_STORAGE_BUCKET}/{key}"

        # Fetch object content to serve directly or redirect
        try:
            data, ctype = neon_storage.get_object(key)
            if data:
                filename = mf.title or os.path.basename(key)
                if not any(filename.lower().endswith(ext) for ext in [".pdf", ".pptx", ".ppt", ".docx", ".doc", ".png", ".jpg"]):
                    ext = os.path.splitext(key)[1]
                    if ext:
                        filename = f"{filename}{ext}"
                return Response(
                    content=data,
                    media_type=ctype or "application/octet-stream",
                    headers={
                        "Content-Disposition": f'inline; filename="{filename}"',
                        "Cache-Control": "public, max-age=86400",
                    },
                )
        except Exception:
            pass

        return RedirectResponse(url=public_url, status_code=302)

    # Check local disk with directory traversal defense
    if mf.file_path:
        allowed_bases = [
            os.path.realpath(os.getcwd()),
            os.path.realpath("/tmp"),
            os.path.realpath("uploads"),
        ]
        for candidate in (
            mf.file_path,
            os.path.join(os.getcwd(), mf.file_path.lstrip("/")),
            os.path.join("/tmp", mf.file_path.lstrip("/")),
            os.path.join("uploads", mf.file_path.lstrip("/")),
        ):
            try:
                resolved = os.path.realpath(candidate)
                if any(resolved.startswith(base) for base in allowed_bases):
                    if os.path.exists(resolved) and os.path.isfile(resolved):
                        return FileResponse(resolved, filename=mf.title or os.path.basename(resolved))
            except Exception:
                continue

    raise HTTPException(status_code=404, detail="File content not found on server or storage.")


@router.get("/{material_id}", response_model=list[MaterialFileOut])
def get_files(
    material_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    if user.type_code == "STU":
        from app.models.material import MaterialStudent
        is_enrolled = db.query(MaterialStudent).filter(
            MaterialStudent.material_id == material_id,
            MaterialStudent.user_id == user_id,
        ).first()
        if not is_enrolled:
            raise HTTPException(status_code=403, detail="Not enrolled in this course")

    return svc.get_material_files(db, material_id)


@router.post("", response_model=MaterialFileOut, status_code=201)
def create_file(
    material_id:     Optional[str]  = Form(None),
    title:           str            = Form(...),
    description:     Optional[str]  = Form(None),
    file_type:       Optional[str]  = Form(None),
    link_url:        Optional[str]  = Form(None),
    text_content:    Optional[str]  = Form(None),
    announcement_id: Optional[int]  = Form(None),
    file:            Optional[UploadFile] = File(None),
    user_id: int  = Depends(get_current_user_id),
    db: Session   = Depends(get_db),
):
    # Sanitize material_id: treat empty string / "null" / "undefined" as None to prevent Postgres FK violation
    clean_material_id = None
    if material_id:
        m_str = str(material_id).strip()
        if m_str and m_str.lower() not in ("null", "undefined", "none", ""):
            clean_material_id = m_str

    file_path, file_size = save_file(file)

    # Auto-detect or normalize file_type if not provided or unknown
    valid_content_types = {
        "text", "image", "voice", "video", "pdf", "word", "ppt", "python", "jupyter",
        "c", "cpp", "java", "javascript", "typescript", "html", "css", "sql", "r", "matlab",
        "zip", "rar", "7z", "link", "file"
    }
    clean_file_type = file_type.strip().lower() if file_type and str(file_type).strip() else None
    if not clean_file_type or clean_file_type not in valid_content_types:
        if file and getattr(file, "filename", None) and file.filename.strip():
            ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
            ext_map = {
                "pdf": "pdf", "doc": "word", "docx": "word", "ppt": "ppt", "pptx": "ppt",
                "xls": "file", "xlsx": "file", "txt": "text", "csv": "file",
                "png": "image", "jpg": "image", "jpeg": "image", "webp": "image",
                "mp4": "video", "mov": "video", "zip": "zip", "rar": "rar", "7z": "7z"
            }
            clean_file_type = ext_map.get(ext, "file")
        elif link_url and str(link_url).strip():
            clean_file_type = "link"
        else:
            clean_file_type = "file"

    data = MaterialFileCreate(
        material_id=clean_material_id,
        title=title.strip(),
        description=description.strip() if description else None,
        file_type=clean_file_type,
        link_url=link_url.strip() if link_url else None,
        text_content=text_content.strip() if text_content else None,
        announcement_id=announcement_id,
    )
    return svc.create_material_file(db, data, user_id, file_path, file_size)


@router.put("/{file_id}", response_model=MaterialFileOut)
def update_file(
    file_id:      int,
    title:        Optional[str]  = Form(None),
    description:  Optional[str]  = Form(None),
    link_url:     Optional[str]  = Form(None),
    text_content: Optional[str]  = Form(None),
    file:         Optional[UploadFile] = File(None),
    user_id: int  = Depends(get_current_user_id),
    db: Session   = Depends(get_db),
):
    file_path, file_size = save_file(file)
    fields = {k: v for k, v in {
        "title": title, "description": description,
        "link_url": link_url, "text_content": text_content,
    }.items() if v is not None}
    data = MaterialFileUpdate(**fields)
    return svc.update_material_file(db, file_id, data, user_id, file_path, file_size)


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    svc.delete_material_file(db, file_id, user_id)
