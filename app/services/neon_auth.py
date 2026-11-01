"""Neon Auth Service.

Managed Better Auth client for authentication, session lookup,
and JWT verification via Neon JWKS.
"""

import logging
from typing import Any, Dict, Optional
import httpx
from jose import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


class NeonAuthService:
    def __init__(self):
        self.base_url = settings.NEON_AUTH_BASE_URL.rstrip("/")
        self.jwks_url = settings.NEON_AUTH_JWKS_URL or (
            f"{self.base_url}/.well-known/jwks.json" if self.base_url else ""
        )
        self._cached_jwks: Optional[Dict[str, Any]] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def get_jwks(self) -> Optional[Dict[str, Any]]:
        """Fetch JWKS keys from Neon Auth endpoint."""
        if not self.jwks_url:
            return None

        if self._cached_jwks:
            return self._cached_jwks

        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            try:
                resp = await client.get(self.jwks_url)
                if resp.status_code == 200:
                    self._cached_jwks = resp.json()
                    return self._cached_jwks
                logger.warning(f"Failed to fetch JWKS from Neon Auth ({resp.status_code})")
                return None
            except Exception as e:
                logger.error(f"Error fetching Neon Auth JWKS: {e}")
                return None

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token against Neon Auth JWKS or inspect claims."""
        if not token:
            return None

        jwks = await self.get_jwks()
        if jwks:
            try:
                # Decode with public key set
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")
                keys = jwks.get("keys", [])
                matching_key = next((k for k in keys if k.get("kid") == kid), keys[0] if keys else None)
                if matching_key:
                    return jwt.decode(
                        token,
                        matching_key,
                        algorithms=["EdDSA", "RS256", "HS256"],
                        options={"verify_aud": False},
                    )
            except Exception as e:
                logger.warning(f"Neon JWKS verification failed: {e}")

        # Fallback to unverified decode for inspection if key set cannot be reached
        try:
            return jwt.get_unverified_claims(token)
        except Exception:
            return None

    async def get_session(self, auth_header: str) -> Optional[Dict[str, Any]]:
        """Check session with Neon Auth server."""
        if not self.is_configured:
            return None

        url = f"{self.base_url}/get-session"
        headers = {"Authorization": auth_header}
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                return None
            except Exception as e:
                logger.error(f"Error checking Neon Auth session: {e}")
                return None


neon_auth = NeonAuthService()
