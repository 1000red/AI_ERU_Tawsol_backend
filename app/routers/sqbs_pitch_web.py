"""SQBS Master Competition Pitch Deck Web Router for WE School Suez.

Serves the 12-slide interactive competition pitch presentation for the judging committee.
"""

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["SQBS Master Competition Pitch Deck"])

_HTML_FILE = os.path.join(os.path.dirname(__file__), "sqbs_pitch.html")
if os.path.exists(_HTML_FILE):
    with open(_HTML_FILE, "r", encoding="utf-8") as _f:
        SQBS_PITCH_HTML = _f.read()
else:
    SQBS_PITCH_HTML = "<!DOCTYPE html><html><body><h1>SQBS Competition Pitch</h1></body></html>"


@router.get("/pitch", response_class=HTMLResponse)
@router.get("/pitch-deck", response_class=HTMLResponse)
@router.get("/sqbs", response_class=HTMLResponse)
@router.get("/competition", response_class=HTMLResponse)
def get_sqbs_pitch_deck():
    """Serve the 12-slide interactive competition pitch presentation."""
    return HTMLResponse(content=SQBS_PITCH_HTML)
