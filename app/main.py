from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os

from app.core.config import settings
from app.db.database import engine, get_db
from app.db import base  # noqa: F401 

from app.models import user, material, chat, content, attendance, password_reset_otp, platform_control  # noqa: F401

# Create all tables on startup only when explicitly requested. Alembic
# (alembic upgrade head) is the source of truth for the schema; silently
# creating tables here would leave a fresh database without Alembic version
# tracking and make migration history unreliable.
if settings.AUTO_CREATE_TABLES:
    try:
        base.Base.metadata.create_all(bind=engine)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Could not connect to create tables on startup: {e}")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="School platform for WE Applied Technology Schools — connect students, teachers, and School Admins",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# ── Middleware ────────────────────────────────────────────────────────────────

from app.core.middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    PlatformMaintenanceMiddleware,
)
from app.services.platform_service import (
    MAINTENANCE_HEADERS,
    PlatformStoppedError,
    build_maintenance_json_payload,
)


@app.exception_handler(PlatformStoppedError)
async def platform_stopped_exception_handler(request: Request, exc: PlatformStoppedError):
    return JSONResponse(
        status_code=503,
        content=build_maintenance_json_payload(exc.maintenance_message, exc.stopped_at),
        headers=MAINTENANCE_HEADERS,
    )

# Registered before vercel_routing_middleware so Vercel path rewriting runs FIRST,
# and CORS + SecurityHeaders wrap 503 maintenance responses cleanly.
app.add_middleware(PlatformMaintenanceMiddleware)

@app.middleware("http")
async def vercel_routing_middleware(request: Request, call_next):
    orig = request.query_params.get("__orig_path")
    if orig:
        clean = "/" + orig.strip("/") if orig.strip("/") else "/"
        request.scope["path"] = clean
        request.scope["raw_path"] = clean.encode("utf-8")
    elif request.scope.get("path") in ("/api/index.py", "/api/index"):
        request.scope["path"] = "/"
        request.scope["raw_path"] = b"/"
    return await call_next(request)

# Security Headers and Rate Limiting Protection against Brute-Force & DoS
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# Production-Hardened CORS Configuration
ALLOWED_ORIGINS = [
    "https://ai-eru-tawsol-backend-weschool.vercel.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Static uploads & Neon S3 Storage Fallback ────────────────────────────────
is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
upload_root = "/tmp/uploads" if is_serverless else "uploads"

try:
    for sub in ("materials", "content", "voice", "files"):
        os.makedirs(os.path.join(upload_root, sub), exist_ok=True)
except Exception:
    pass

@app.get("/tmp/uploads/{file_path:path}", include_in_schema=False)
@app.get("/uploads/{file_path:path}", include_in_schema=False)
def serve_upload_file(file_path: str):
    # Path traversal protection (CWE-22)
    clean = os.path.normpath(file_path.lstrip("/\\"))
    if ".." in clean.split(os.sep) or clean.startswith(".."):
        raise HTTPException(status_code=400, detail="Invalid path traversal sequence.")

    # Check local filesystem first with canonical path containment
    for prefix in (upload_root, "/tmp/uploads", "uploads"):
        prefix_real = os.path.realpath(prefix)
        cand = os.path.join(prefix, clean)
        cand_real = os.path.realpath(cand)
        if cand_real.startswith(prefix_real) and os.path.exists(cand_real) and os.path.isfile(cand_real):
            return FileResponse(cand_real)
    # Check Neon S3 storage
    try:
        from app.services.neon_storage import neon_storage
        if neon_storage.is_configured:
            candidates = [clean]
            if not clean.startswith("content/"):
                candidates.append(f"content/{clean}")
            if "/" in clean:
                sub = clean.split("/")[-1]
                candidates.append(sub)
                candidates.append(f"voice/{sub}")
                candidates.append(f"files/{sub}")
            
            for key in candidates:
                try:
                    obj = neon_storage.client.get_object(Bucket=neon_storage.bucket_name, Key=key)
                    body = obj["Body"].read()
                    # Cache to local file for fast subsequent responses
                    try:
                        save_cand = os.path.join(upload_root, clean)
                        os.makedirs(os.path.dirname(save_cand), exist_ok=True)
                        with open(save_cand, "wb") as f:
                            f.write(body)
                        return FileResponse(save_cand)
                    except Exception:
                        from fastapi.responses import Response
                        media_type = obj.get("ContentType", "application/octet-stream")
                        return Response(content=body, media_type=media_type)
                except Exception:
                    continue
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Uploaded file not found.")

# ── Routers ───────────────────────────────────────────────────────────────────

from app.routers import auth, support, users, materials, chat as chat_router, content, admin_dashboard, attendance, edugame  # noqa
from app.routers.quiz import router as quiz_router  # noqa
from app.routers.neon_services import router as neon_router  # noqa

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(materials.router, prefix="/materials")
app.include_router(materials.router, prefix="/courses")
app.include_router(chat_router.router)
app.include_router(content.router)
app.include_router(support.router)
app.include_router(quiz_router)
app.include_router(neon_router)
app.include_router(edugame.router)
app.include_router(attendance.router)
app.include_router(admin_dashboard.router)
from app.routers import user_management_web, teacher_portal_web, student_checkin_web, sqbs_pitch_web
app.include_router(user_management_web.router)
app.include_router(teacher_portal_web.router)
app.include_router(student_checkin_web.router)
app.include_router(sqbs_pitch_web.router)

@app.get("/api/storage/quota", tags=["Storage Telemetry"])
def get_public_storage_quota(db: Session = Depends(get_db)):
    """Public read-only storage capacity telemetry for live dashboards."""
    from app.services.storage_service import storage_service
    summary = storage_service.get_quota_summary(db)
    return {"quota": summary, **summary}

@app.get("/api/cron/quarantine-purge", tags=["Storage Telemetry"])
@app.post("/api/cron/quarantine-purge", tags=["Storage Telemetry"])
def public_cron_quarantine_purge(db: Session = Depends(get_db)):
    """Automated cron endpoint to purge quarantined files older than 7 days."""
    from app.services.storage_service import storage_service
    return storage_service.purge_expired_quarantined_files(db=db)

@app.get("/dashboard", response_class=HTMLResponse, tags=["Admin Dashboard"])
def dashboard_view():
    from app.routers.admin_dashboard import DASHBOARD_HTML
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/login", include_in_schema=False)
@app.get("/auth/login", include_in_schema=False)
def login_get_view():
    return {"message": "Use POST /auth/login for authentication."}


@app.post("/login", response_model=auth.TokenOut, tags=["Auth"], include_in_schema=False)
def login_alias(data: auth.UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Allow direct POST /login in addition to /auth/login."""
    import os
    import secrets
    from app.services import user_service as svc
    ip = request.headers.get("x-forwarded-for")
    if ip:
        ip = ip.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    user_agent = request.headers.get("user-agent")

    result = svc.login_user(db, data.email, data.password, ip=ip, user_agent=user_agent)
    csrf_token = secrets.token_urlsafe(32)
    result["csrf_token"] = csrf_token
    is_secure = request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production"

    response.set_cookie(
        key="admin_token",
        value=result["access_token"],
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=1800,
        path="/",
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_secure,
        samesite="lax",
        max_age=1800,
        path="/",
    )
    return result


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
@app.get("/api", tags=["Health"], include_in_schema=False)
@app.get("/api/index.py", tags=["Health"], include_in_schema=False)
def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/platform/status", tags=["Health"])
@app.get("/api/platform/status", tags=["Health"], include_in_schema=False)
def public_platform_status(db: Session = Depends(get_db)):
    from app.services.platform_service import get_public_platform_status
    return JSONResponse(
        content=get_public_platform_status(db),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"], include_in_schema=False)
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
