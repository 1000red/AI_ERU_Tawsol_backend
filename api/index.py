"""Vercel Serverless Function entrypoint for FastAPI."""

import sys
import os
import traceback
from urllib.parse import parse_qs, urlencode

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from app.main import app as fastapi_app

    async def app(scope, receive, send):
        if scope.get("type") in ("http", "websocket"):
            raw_p = scope.get("path", "")
            qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")

            if "?" in raw_p:
                path_part, qs_part = raw_p.split("?", 1)
                scope["path"] = path_part
                qs = f"{qs}&{qs_part}" if qs else qs_part

            params = parse_qs(qs, keep_blank_values=True)

            if "__orig_path" in params:
                orig = params.pop("__orig_path")[0]
                clean = "/" + orig.strip("/") if orig.strip("/") else "/"
                scope["path"] = clean
                scope["raw_path"] = clean.encode("utf-8")
                new_qs = urlencode(params, doseq=True)
                scope["query_string"] = new_qs.encode("utf-8")
            else:
                headers = dict(scope.get("headers", []))
                matched = headers.get(b"x-matched-path", b"").decode("utf-8", errors="ignore")
                if matched and not matched.startswith("/api/index"):
                    clean = matched.split("?")[0]
                    scope["path"] = clean
                    scope["raw_path"] = clean.encode("utf-8")
                elif scope.get("path", "").startswith("/api/index.py"):
                    rest = scope["path"][len("/api/index.py"):] or "/"
                    scope["path"] = rest
                    scope["raw_path"] = rest.encode("utf-8")
                elif scope.get("path", "").startswith("/api/index"):
                    rest = scope["path"][len("/api/index"):] or "/"
                    scope["path"] = rest
                    scope["raw_path"] = rest.encode("utf-8")

        await fastapi_app(scope, receive, send)

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
