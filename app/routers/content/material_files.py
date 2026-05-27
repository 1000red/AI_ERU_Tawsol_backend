from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import MaterialFileCreate, MaterialFileUpdate, MaterialFileOut
from app.services import content_service as svc
from app.routers.content._helpers import save_file

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


@router.get("/{material_id}", response_model=list[MaterialFileOut])
def get_files(
    material_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.get_material_files(db, material_id)


@router.post("", response_model=MaterialFileOut, status_code=201)
def create_file(
    material_id:     Optional[str]  = Form(None),
    title:           str            = Form(...),
    description:     Optional[str]  = Form(None),
    file_type:       str            = Form(...),
    link_url:        Optional[str]  = Form(None),
    text_content:    Optional[str]  = Form(None),
    announcement_id: Optional[int]  = Form(None),
    file:            Optional[UploadFile] = File(None),
    user_id: int  = Depends(get_current_user_id),
    db: Session   = Depends(get_db),
):
    file_path, file_size = save_file(file)
    data = MaterialFileCreate(
        material_id=material_id,
        title=title,
        description=description,
        file_type=file_type,
        link_url=link_url,
        text_content=text_content,
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
