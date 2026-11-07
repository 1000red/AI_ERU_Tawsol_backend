"""Neon Functions Service.

Client for invoking long-running serverless functions deployed to Neon branches.
"""

import logging
from typing import Any, Dict, Optional

try:
    import httpx
except ImportError:
    httpx = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class NeonFunctionsService:
    def __init__(self):
        self.hello_url = settings.NEON_FUNCTION_HELLO_BASE_URL.rstrip("/")

    def get_url(self, slug: str) -> Optional[str]:
        if slug == "hello" and self.hello_url:
            return self.hello_url
        return None

    async def invoke(
        self,
        slug: str = "hello",
        path: str = "/",
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Invoke a deployed Neon Function."""
        base_url = self.get_url(slug)
        if not base_url:
            return {
                "success": False,
                "error": f"Base URL for Neon function '{slug}' is not configured.",
                "status_code": 503,
            }

        if not httpx:
            return {
                "success": False,
                "error": "httpx library is not installed",
                "status_code": 503,
            }

        url = f"{base_url}{path if path.startswith('/') else '/' + path}"
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            try:
                if method.upper() == "POST":
                    resp = await client.post(url, json=payload or {})
                else:
                    resp = await client.get(url)

                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text}

                return {
                    "success": resp.status_code < 400,
                    "status_code": resp.status_code,
                    "data": data,
                }
            except Exception as e:
                logger.error(f"Error invoking Neon function '{slug}': {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "status_code": 500,
                }


neon_functions = NeonFunctionsService()
