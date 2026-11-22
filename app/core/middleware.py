"""Cybersecurity middleware for FastAPI: Rate limiting, Security Headers, and Cloaking.
"""

import posixpath
import time
import re
from urllib.parse import unquote
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces essential HTTP security headers on all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 1. Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Prevent clickjacking (allow embedding only on same origin)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # 3. Cross-Site Scripting (XSS) filter for legacy browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 4. Enforce HTTPS (HTTP Strict Transport Security)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # 5. Referrer policy to prevent information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 6. Restrict browser feature permissions
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        # 7. Content Security Policy (allows app assets while blocking inline script injections)
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' https: data: blob:; "
                "img-src 'self' https: data: blob:; "
                "media-src 'self' https: data: blob:; "
                "connect-src 'self' https: wss:;"
            )

        # 8. Server fingerprint cloaking
        response.headers["Server"] = "protected"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter against brute-force and DoS attacks."""

    def __init__(self, app):
        super().__init__(app)
        # IP -> list of timestamps
        self.request_history: Dict[str, List[float]] = {}
        # Route specific rules: (regex, max_requests, window_seconds)
        self.rules = [
            (re.compile(r"^/auth/login"), 10, 60),
            (re.compile(r"^/auth/forgot-password"), 5, 60),
            (re.compile(r"^/auth/verify-otp"), 10, 60),
            (re.compile(r"^/auth/reset-password"), 5, 60),
            (re.compile(r"^/contact"), 5, 60),
            (re.compile(r"^/admin/api"), 30, 60),
            (re.compile(r"^/.*"), 180, 60),  # Global fallback: 180 req / min
        ]
        self._last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"

    def _cleanup_old_records(self, now: float):
        if now - self._last_cleanup > 300:  # Every 5 minutes
            self._last_cleanup = now
            expired_keys = []
            for ip, timestamps in list(self.request_history.items()):
                valid = [t for t in timestamps if now - t < 120]
                if valid:
                    self.request_history[ip] = valid
                else:
                    expired_keys.append(ip)
            for k in expired_keys:
                self.request_history.pop(k, None)

    async def dispatch(self, request: Request, call_next):
        # WebSocket handshakes, CORS preflight OPTIONS, and internal TestClient bypass standard rate limiter
        ip = self._get_client_ip(request)
        if request.method == "OPTIONS" or request.url.path.startswith("/chat/ws") or ip == "testclient":
            return await call_next(request)

        now = time.time()
        self._cleanup_old_records(now)

        path = request.url.path

        # Find matching rule
        max_requests, window = 180, 60
        for pattern, m_req, win in self.rules:
            if pattern.search(path):
                max_requests, window = m_req, win
                break

        key = f"{ip}:{path}" if max_requests < 180 else ip
        history = self.request_history.get(key, [])
        history = [t for t in history if now - t < window]

        if len(history) >= max_requests:
            retry_after = int(window - (now - history[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "تم تجاوز الحد الأقصى للطلبات المسموح به. يرجى الانتظار والمحاولة لاحقاً.",
                    "error": "Too many requests. Brute-force rate limit protection triggered.",
                    "retry_after_seconds": max(1, retry_after),
                },
                headers={"Retry-After": str(max(1, retry_after))},
            )

        history.append(now)
        self.request_history[key] = history

        return await call_next(request)


class PlatformMaintenanceMiddleware(BaseHTTPMiddleware):
    """Blocks non-admin platform traffic with HTTP 503 when the admin kill-switch is engaged."""

    _ALWAYS_ALLOWED_EXACT = {
        "/health",
        "/api/health",
        "/platform/status",
        "/api/platform/status",
        "/admin",
        "/dashboard",
        "/users-management",
        "/users-portal",
        "/admin/storage",
        "/storage",
        "/login",
        "/auth/login",
        "/auth/logout",
    }

    @classmethod
    def _normalize_path(cls, request: Request) -> str:
        path = request.url.path or "/"
        orig = request.query_params.get("__orig_path")
        if orig and path in ("/api/index.py", "/api/index"):
            path = "/" + orig.strip("/") if orig.strip("/") else "/"
        # Decode percent-encoding and collapse dot-segments to prevent /admin/../ bypasses
        decoded = unquote(path)
        if not decoded.startswith("/"):
            decoded = "/" + decoded
        normalized = posixpath.normpath(decoded)
        # posixpath.normpath preserves a leading "//" per POSIX; collapse it
        while normalized.startswith("//"):
            normalized = normalized[1:]
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        if normalized != "/":
            normalized = normalized.rstrip("/") or "/"
        return normalized

    @classmethod
    def _is_bypassed(cls, method: str, norm_path: str) -> bool:
        if method == "OPTIONS":
            return True
        if norm_path in cls._ALWAYS_ALLOWED_EXACT:
            return True
        if norm_path.startswith("/admin/"):
            return True
        # GET /users serves the admin user-management HTML portal; /users/me etc. are blocked
        if norm_path == "/users" and method == "GET":
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        norm_path = self._normalize_path(request)
        if self._is_bypassed(request.method.upper(), norm_path):
            return await call_next(request)

        from app.services.platform_service import (
            MAINTENANCE_HEADERS,
            build_maintenance_json_payload,
            get_platform_status,
            render_maintenance_html,
            resolve_db_session_for_app,
        )

        try:
            with resolve_db_session_for_app(request.app) as db:
                status_info = get_platform_status(db)
        except Exception:
            # Fail open on transient DB session resolution failure
            return await call_next(request)

        if status_info.get("is_active", True):
            return await call_next(request)

        accept = (request.headers.get("accept") or "").lower()
        if request.method.upper() == "GET" and "text/html" in accept and "application/json" not in accept:
            return HTMLResponse(
                content=render_maintenance_html(
                    status_info["maintenance_message"],
                    status_info.get("stopped_at"),
                ),
                status_code=503,
                headers=MAINTENANCE_HEADERS,
            )

        return JSONResponse(
            status_code=503,
            content=build_maintenance_json_payload(
                status_info["maintenance_message"],
                status_info.get("stopped_at"),
            ),
            headers=MAINTENANCE_HEADERS,
        )
