from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.db.database import engine
from app.db import base  # noqa: F401 — triggers all model imports for create_all

# Import models to ensure tables are created
from app.models import user, material, chat, notification, content  # noqa: F401

# Create all tables
try:
    base.Base.metadata.create_all(bind=engine)
except Exception as e:
    import sys
    print(f"❌ Failed to create tables: {e}")
    sys.exit(1)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="University community platform — connect students, TAs, and admins",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to your domain in production
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Static files ──────────────────────────────────────────────────────────────

os.makedirs("uploads/profiles", exist_ok=True)
os.makedirs("uploads/materials", exist_ok=True)
os.makedirs("uploads/content", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────

from app.routers import auth, support, users, materials, chat as chat_router, content  # noqa

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(materials.router)
app.include_router(chat_router.router)
app.include_router(content.router)
app.include_router(support.router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}