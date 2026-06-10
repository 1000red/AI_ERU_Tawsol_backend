from fastapi import APIRouter
from app.routers.content import announcements, material_files, assignments

router = APIRouter()

router.include_router(announcements.router)
router.include_router(material_files.router)
router.include_router(assignments.router)
