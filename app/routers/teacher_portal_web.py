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

_GATEWAY_FILE = os.path.join(os.path.dirname(__file__), "teacher_gateway.html")
if os.path.exists(_GATEWAY_FILE):
    with open(_GATEWAY_FILE, "r", encoding="utf-8") as _f:
        TEACHER_GATEWAY_HTML = _f.read()
else:
    TEACHER_GATEWAY_HTML = "<!DOCTYPE html><html><body><h1>Teacher Gateway</h1></body></html>"


@router.get("/teacher", response_class=HTMLResponse)
@router.get("/teachers", response_class=HTMLResponse)
@router.get("/teacher-portal", response_class=HTMLResponse)
@router.get("/teachers-portal", response_class=HTMLResponse)
def get_teacher_portal():
    """Serve the interactive Teacher Portal Web Application."""
    if os.path.exists(_HTML_FILE):
        try:
            with open(_HTML_FILE, "r", encoding="utf-8") as _f:
                return HTMLResponse(content=_f.read())
        except Exception:
            pass
    return HTMLResponse(content=TEACHER_PORTAL_HTML)


@router.get("/teacher-gateway", response_class=HTMLResponse)
@router.get("/gateway", response_class=HTMLResponse)
@router.get("/classroom-arena", response_class=HTMLResponse)
@router.get("/interactive-classroom", response_class=HTMLResponse)
def get_teacher_gateway():
    """Serve the Teacher Interactive Gateway and Live Classroom Arena."""
    if os.path.exists(_GATEWAY_FILE):
        try:
            with open(_GATEWAY_FILE, "r", encoding="utf-8") as _f:
                return HTMLResponse(content=_f.read())
        except Exception:
            pass
    return HTMLResponse(content=TEACHER_GATEWAY_HTML)
