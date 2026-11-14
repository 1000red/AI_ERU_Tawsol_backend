"""Cybersecurity middleware for FastAPI: Rate limiting, Security Headers, and Cloaking.
"""

import time
import re
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


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
        # WebSocket handshakes and CORS preflight OPTIONS bypass standard rate limiter
        if request.method == "OPTIONS" or request.url.path.startswith("/chat/ws"):
            return await call_next(request)

        now = time.time()
        self._cleanup_old_records(now)

        ip = self._get_client_ip(request)
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
