from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import MaterialFileCreate, MaterialFileUpdate, MaterialFileOut
from app.services import content_service as svc
from app.routers.content._helpers import save_file

router = APIRouter(prefix="/files", tags=["Material Files"])


@router.get("/{material_id}", response_model=list[MaterialFileOut])
def get_files(
    material_id: str,
    db: Session = Depends(get_db),
):
    return svc.get_material_files(db, material_id)


@router.post("", response_model=MaterialFileOut, status_code=201)
def create_file(
    material_id: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    file_type: str = Form(...),
    link_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)
    data = MaterialFileCreate(
        material_id=material_id,
        title=title,
        description=description,
        file_type=file_type,
        link_url=link_url,
    )
    return svc.create_material_file(db, data, user_id, file_path)


@router.put("/{file_id}", response_model=MaterialFileOut)
def update_file(
    file_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)
    data = MaterialFileUpdate(
        title=title,
        description=description,
        link_url=link_url,
    )
    return svc.update_material_file(db, file_id, data, user_id, file_path)


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_material_file(db, file_id, user_id)
