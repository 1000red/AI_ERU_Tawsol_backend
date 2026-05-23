from fastapi import APIRouter
from app.routers.content import announcements, material_files, assignments, submissions

router = APIRouter(prefix="/content", tags=["Content"])

router.include_router(announcements.router)
router.include_router(material_files.router)
router.include_router(assignments.router)
router.include_router(submissions.router)
