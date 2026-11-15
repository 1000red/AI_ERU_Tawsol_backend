"""Teacher Portal Web Application Router for WE School Suez."""

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Teacher Portal Web Application"])

_HTML_FILE = os.path.join(os.path.dirname(__file__), "teacher_portal.html")
if os.path.exists(_HTML_FILE):
    with open(_HTML_FILE, "r", encoding="utf-8") as _f:
        TEACHER_PORTAL_HTML = _f.read()
else:
    TEACHER_PORTAL_HTML = "<!DOCTYPE html><html><body><h1>Teacher Portal</h1></body></html>"


@router.get("/teacher", response_class=HTMLResponse)
@router.get("/teachers", response_class=HTMLResponse)
@router.get("/teacher-portal", response_class=HTMLResponse)
@router.get("/teachers-portal", response_class=HTMLResponse)
def get_teacher_portal():
    """Serve the interactive Teacher Portal Web Application."""
    return HTMLResponse(content=TEACHER_PORTAL_HTML)
