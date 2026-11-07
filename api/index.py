"""Vercel Serverless Function entrypoint for FastAPI."""

import sys
import os
import json
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from app.main import app
except Exception as e:
    error_trace = traceback.format_exc()

    # Diagnostic pure ASGI fallback that reports the exact startup exception
    async def app(scope, receive, send):
        if scope.get("type") == "http":
            body = json.dumps({
                "status": "startup_failed",
                "error": str(e),
                "traceback": error_trace,
                "sys_path": sys.path,
                "root_files": os.listdir(root_dir) if os.path.exists(root_dir) else []
            }, indent=2).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
