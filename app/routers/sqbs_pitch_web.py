"""WeConnect — HP IDEA Egypt Competition Pitch Deck Web Router for WE School Suez.

Serves the 10-slide + 4-tab Appendix interactive competition pitch presentation
for the HP IDEA Egypt judging committee, with embedded 1080p pitch video streaming
and chapter navigation.
"""

import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse

router = APIRouter(tags=["WeConnect HP IDEA Pitch Deck"])

_HTML_FILE = os.path.join(os.path.dirname(__file__), "sqbs_pitch.html")
if os.path.exists(_HTML_FILE):
    with open(_HTML_FILE, "r", encoding="utf-8") as _f:
        SQBS_PITCH_HTML = _f.read()
else:
    SQBS_PITCH_HTML = "<!DOCTYPE html><html><body><h1>WeConnect — HP IDEA Egypt Pitch</h1></body></html>"

NEON_PITCH_VIDEO_URL = "https://br-still-boat-b5bl10k7.storage.c-7.us-east-2.aws.neon.tech/assets/weconnect_media/class_video_1.mp4"
LOCAL_VIDEO_PATHS = [
    r"C:\Users\dell\OneDrive\Desktop\WeConnect_Pitch_5Min.mp4",
    os.path.join(os.path.dirname(__file__), "..", "..", "WeConnect_Pitch_5Min.mp4"),
]

PITCH_CHAPTERS = [
    {"index": 1, "time": "0:00", "seconds": 0, "title_ar": "المشكلة والدافع الأساسي", "title_en": "Hook & Problem Statement"},
    {"index": 2, "time": "0:30", "seconds": 30, "title_ar": "شريحة المستخدمين والبيئة المدرسية", "title_en": "Target Persona & School Context"},
    {"index": 3, "time": "1:00", "seconds": 60, "title_ar": "معمارية منظومة WeConnect", "title_en": "Ecosystem Architecture"},
    {"index": 4, "time": "1:30", "seconds": 90, "title_ar": "التحضير الذكي برمز الاستجابة السريع QR المتغير", "title_en": "Anti-Proxy Dynamic QR Attendance"},
    {"index": 5, "time": "2:00", "seconds": 120, "title_ar": "استوديو الامتحانات الذكية متعدد الأنماط", "title_en": "AI Multi-Format Exam Studio"},
    {"index": 6, "time": "2:30", "seconds": 150, "title_ar": "تجربة الطالب وحصص العلاج الذاتي", "title_en": "Student Experience & Auto-Remediation"},
    {"index": 7, "time": "3:00", "seconds": 180, "title_ar": "سجل الدرجات الرسمي المعتمد لوزارة التعليم", "title_en": "Ministry Official Gradebook & Heatmap"},
    {"index": 8, "time": "3:30", "seconds": 210, "title_ar": "الجدوى الاقتصادية واقتصاديات الرموز المجانية", "title_en": "Unit Economics & Free-Tier Gemini"},
    {"index": 9, "time": "4:00", "seconds": 240, "title_ar": "بروتوكول الاتحاد بين مدارس WE", "title_en": "Inter-School Federation (Suez, Cairo, Alex)"},
    {"index": 10, "time": "4:30", "seconds": 270, "title_ar": "خارطة التوسع والأثر والختام", "title_en": "Scalability, National Impact & Call to Action"}
]


@router.get("/weconnect", response_class=HTMLResponse)
@router.get("/hp-idea", response_class=HTMLResponse)
@router.get("/pitch", response_class=HTMLResponse)
@router.get("/pitch-deck", response_class=HTMLResponse)
@router.get("/sqbs", response_class=HTMLResponse)
@router.get("/competition", response_class=HTMLResponse)
def get_sqbs_pitch_deck():
    """Serve the 10-slide + Appendix interactive WeConnect HP IDEA Egypt pitch deck."""
    # Re-read if updated during runtime
    if os.path.exists(_HTML_FILE):
        with open(_HTML_FILE, "r", encoding="utf-8") as _f:
            content = _f.read()
    else:
        content = SQBS_PITCH_HTML
    return HTMLResponse(content=content)


@router.get("/api/media/pitch-video")
def get_pitch_video(request: Request):
    """Stream or redirect to the official 5-minute HP IDEA Competition Pitch Video.
    
    Prefers local low-latency video file if present on server; falls back to Neon cloud object storage.
    """
    for path in LOCAL_VIDEO_PATHS:
        if os.path.exists(path):
            return FileResponse(
                path,
                media_type="video/mp4",
                filename="WeConnect_Pitch_5Min.mp4",
                headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=86400"}
            )
    return RedirectResponse(url=NEON_PITCH_VIDEO_URL, status_code=307)


@router.get("/api/media/pitch-video/info")
def get_pitch_video_info():
    """Return metadata and chapter timestamps for the WeConnect 5-minute competition pitch video."""
    local_available = any(os.path.exists(p) for p in LOCAL_VIDEO_PATHS)
    return JSONResponse(content={
        "title": "WeConnect HP IDEA Egypt Official Pitch Presentation",
        "school": "WE Applied Technology School — Suez",
        "duration_seconds": 300,
        "duration_formatted": "05:00",
        "resolution": "1080p (1920x1080 Full HD 30fps)",
        "audio": "Dual-Voiceover Ducked High-Fidelity Audio",
        "local_stream_available": local_available,
        "neon_storage_url": NEON_PITCH_VIDEO_URL,
        "chapters": PITCH_CHAPTERS
    })

