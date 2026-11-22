"""Student Attendance QR Check-In Web Application Router for WE School Suez.

Serves the mobile-friendly student QR scanner & manual token entry portal.
"""

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Student QR Attendance Check-In"])

_HTML_FILE = os.path.join(os.path.dirname(__file__), "student_checkin.html")
if os.path.exists(_HTML_FILE):
    with open(_HTML_FILE, "r", encoding="utf-8") as _f:
        STUDENT_CHECKIN_HTML = _f.read()
else:
    STUDENT_CHECKIN_HTML = "<!DOCTYPE html><html><body><h1>Student Attendance Check-In</h1></body></html>"


@router.get("/checkin", response_class=HTMLResponse)
@router.get("/check-in", response_class=HTMLResponse)
@router.get("/attendance/scan", response_class=HTMLResponse)
@router.get("/scan", response_class=HTMLResponse)
@router.get("/student-checkin", response_class=HTMLResponse)
@router.get("/student/checkin", response_class=HTMLResponse)
def get_student_checkin_portal():
    """Serve the interactive mobile-first Student QR Check-In Web Application."""
    return HTMLResponse(content=STUDENT_CHECKIN_HTML)
