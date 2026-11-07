"""Neon Services API Router.

Exposes status and integration endpoints for all wired Neon services:
PostgreSQL, Auth, AI Gateway, Object Storage, Functions, and Realtime.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.core.config import settings
from app.db.database import get_db, check_connection
from app.services.neon_storage import neon_storage
from app.services.neon_ai_gateway import neon_ai
from app.services.neon_auth import neon_auth
from app.services.neon_realtime import neon_realtime
from app.services.neon_functions import neon_functions

router = APIRouter(prefix="/api/neon", tags=["Neon Services"])


@router.get("/status")
def get_neon_status() -> Dict[str, Any]:
    """Report configuration and health for all wired Neon services."""
    db_connected = check_connection()

    return {
        "status": "online",
        "services": {
            "postgres": {
                "configured": bool(settings.DATABASE_URL),
                "is_pooled": "pooler" in settings.DATABASE_URL or "sslmode=require" in settings.DATABASE_URL,
                "unpooled_configured": bool(settings.DATABASE_URL_UNPOOLED),
                "connected": db_connected,
            },
            "auth": {
                "configured": neon_auth.is_configured,
                "base_url": settings.NEON_AUTH_BASE_URL,
                "jwks_url": neon_auth.jwks_url,
            },
            "ai_gateway": {
                "configured": neon_ai.is_configured,
                "base_url": settings.NEON_AI_GATEWAY_BASE_URL,
                "token_set": bool(settings.NEON_AI_GATEWAY_TOKEN),
            },
            "object_storage": {
                "configured": neon_storage.is_configured,
                "endpoint_url": settings.AWS_ENDPOINT_URL_S3,
                "bucket": settings.NEON_STORAGE_BUCKET,
                "region": settings.AWS_REGION,
                "addressing_style": "path",
            },
            "realtime": {
                "configured": neon_realtime.is_configured,
                "url": settings.NEON_REALTIME_URL,
                "secret_set": bool(settings.NEON_REALTIME_SECRET),
            },
            "functions": {
                "configured": bool(settings.NEON_FUNCTION_HELLO_BASE_URL),
                "hello_url": settings.NEON_FUNCTION_HELLO_BASE_URL,
            },
        },
    }


@router.post("/storage/upload")
async def upload_to_storage(file: UploadFile = File(...)):
    """Upload a file to the Neon Object Storage bucket."""
    if not neon_storage.is_configured:
        raise HTTPException(status_code=503, detail="Neon Object Storage not configured")

    success, result = neon_storage.upload_file(
        file_obj=file.file,
        object_key=f"uploads/{file.filename}",
        content_type=file.content_type or "application/octet-stream",
    )
    if not success:
        raise HTTPException(status_code=502, detail=f"Upload failed: {result}")

    return {
        "success": True,
        "object_key": f"uploads/{file.filename}",
        "url": result,
    }


@router.get("/storage/list")
def list_storage_objects(prefix: str = ""):
    """List objects in the configured Neon storage bucket."""
    if not neon_storage.is_configured:
        raise HTTPException(status_code=503, detail="Neon Object Storage not configured")

    objects = neon_storage.list_objects(prefix)
    return {"bucket": settings.NEON_STORAGE_BUCKET, "objects": objects}


@router.get("/storage/presigned-url")
def get_presigned_url(key: str, expires_in: int = 3600):
    """Generate a presigned GET URL for an object in Neon storage."""
    if not neon_storage.is_configured:
        raise HTTPException(status_code=503, detail="Neon Object Storage not configured")
    url = neon_storage.get_presigned_url(key, expires_in=expires_in)
    if not url:
        raise HTTPException(status_code=502, detail="Failed to generate presigned URL")
    return {"key": key, "presigned_url": url, "expires_in": expires_in}


@router.post("/realtime/seal")
def seal_realtime_query(
    query: str,
    params: Optional[Dict[str, Any]] = None,
):
    """Seal a SQL query for Neon Realtime live subscription."""
    import time
    sealed = neon_realtime.seal_query(query, params)
    try:
        from app.db.database import SessionLocal
        with SessionLocal() as db:
            txid = neon_realtime.get_current_txid(db)
    except Exception:
        txid = str(int(time.time() * 1000))
    sealed["current_txid"] = txid
    return sealed


@router.get("/auth/jwks")
async def get_neon_jwks():
    """Fetch Neon Auth JWKS keys."""
    if not neon_auth.is_configured:
        raise HTTPException(status_code=503, detail="Neon Auth not configured")
    jwks = await neon_auth.get_jwks()
    if not jwks:
        raise HTTPException(status_code=502, detail="Failed to retrieve Neon Auth JWKS")
    return jwks


@router.get("/ai/models")
async def list_ai_models():
    """List models available on the Neon AI Gateway branch endpoint."""
    if not neon_ai.is_configured:
        return {"models": [], "notice": "Neon AI Gateway is disabled on Free plan; using Gemini AI fallback"}
    models = await neon_ai.list_models()
    return {"models": models}


@router.post("/functions/invoke")
async def invoke_neon_function(slug: str = "hello", path: str = "/"):
    """Invoke a deployed Neon Function."""
    result = await neon_functions.invoke(slug=slug, path=path)
    return result
