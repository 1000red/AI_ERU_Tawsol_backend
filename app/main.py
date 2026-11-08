from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.db.database import engine
from app.db import base  # noqa: F401 

from app.models import user, material, chat, content, attendance  # noqa: F401

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Static files ──────────────────────────────────────────────────────────────

is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
upload_root = "/tmp/uploads" if is_serverless else "uploads"

try:
    for sub in ("materials", "content", "voice", "files"):
        os.makedirs(os.path.join(upload_root, sub), exist_ok=True)
    if os.path.exists(upload_root):
        app.mount("/uploads", StaticFiles(directory=upload_root), name="uploads")
except Exception as e:
    import logging
    logging.getLogger("uvicorn.error").warning(f"Could not mount static uploads directory: {e}")

# ── Routers ───────────────────────────────────────────────────────────────────

from app.routers import auth, support, users, materials, chat as chat_router, content, admin_dashboard, attendance  # noqa
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
app.include_router(attendance.router)
app.include_router(admin_dashboard.router)

@app.get("/dashboard", response_class=HTMLResponse, tags=["Admin Dashboard"])
def dashboard_view():
    from app.routers.admin_dashboard import DASHBOARD_HTML
    return HTMLResponse(content=DASHBOARD_HTML)


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


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"], include_in_schema=False)
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
