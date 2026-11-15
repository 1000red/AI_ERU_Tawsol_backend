"""User Management Web Portal Router for WE School Suez."""

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["User Management Web Portal"])

_HTML_FILE = os.path.join(os.path.dirname(__file__), "user_management.html")
if os.path.exists(_HTML_FILE):
    with open(_HTML_FILE, "r", encoding="utf-8") as _f:
        USER_MANAGEMENT_HTML = _f.read()
else:
    USER_MANAGEMENT_HTML = "<!DOCTYPE html><html><body><h1>User Management Portal</h1></body></html>"


@router.get("/users-management", response_class=HTMLResponse)
@router.get("/users", response_class=HTMLResponse)
@router.get("/users-portal", response_class=HTMLResponse)
@router.get("/admin/users", response_class=HTMLResponse)
def get_user_management_portal():
    """Serve the interactive User Management Web Portal."""
    return HTMLResponse(content=USER_MANAGEMENT_HTML)
