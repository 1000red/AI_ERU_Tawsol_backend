"""Vercel Serverless Function entrypoint for FastAPI."""

import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    err_text = traceback.format_exc()
    print("FATAL APP IMPORT ERROR:", err_text, file=sys.stderr)

    app = FastAPI(title="Vercel Startup Error Diagnostic")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
    async def catch_all(path: str):
        return JSONResponse(
            status_code=200,
            content={
                "status": "startup_failed",
                "error": str(e),
                "traceback": err_text,
                "sys_path": sys.path,
                "root_files": os.listdir(root_dir) if os.path.exists(root_dir) else []
            }
        )
