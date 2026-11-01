"""Neon Realtime Service.

Manages query sealing with NEON_REALTIME_SECRET and optimistic mutation
tracking for reactive live query subscriptions.
"""

import hmac
import hashlib
import json
import base64
import time
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class NeonRealtimeService:
    def __init__(self):
        self.secret = settings.NEON_REALTIME_SECRET
        self.realtime_url = settings.NEON_REALTIME_URL or "wss://realtime.neon.tech"

    @property
    def is_configured(self) -> bool:
        return bool(self.secret)

    def seal_query(self, sql_query: str, params: Optional[Dict[str, Any]] = None, ttl_seconds: int = 3600) -> Dict[str, Any]:
        """Seal a read-only SQL query with NEON_REALTIME_SECRET.
        
        The sealed query token guarantees query authenticity and parameter integrity
        when establishing live WebSocket subscriptions to Neon Realtime.
        """
        payload = {
            "sql": sql_query.strip(),
            "params": params or {},
            "exp": int(time.time()) + ttl_seconds,
            "created_at": int(time.time()),
        }
        encoded_data = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

        secret_bytes = self.secret.encode("utf-8") if self.secret else b"default_secret"
        signature = hmac.new(secret_bytes, encoded_data.encode("utf-8"), hashlib.sha256).hexdigest()

        sealed_token = f"{encoded_data}.{signature}"

        return {
            "sealed_query": sealed_token,
            "realtime_url": self.realtime_url,
            "expires_in": ttl_seconds,
        }

    def verify_sealed_query(self, sealed_token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a sealed query token."""
        try:
            parts = sealed_token.split(".")
            if len(parts) != 2:
                return None
            encoded_data, signature = parts
            secret_bytes = self.secret.encode("utf-8") if self.secret else b"default_secret"
            expected_sig = hmac.new(secret_bytes, encoded_data.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                return None

            payload_raw = base64.urlsafe_b64decode(encoded_data.encode("utf-8")).decode("utf-8")
            payload = json.loads(payload_raw)
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception as e:
            logger.error(f"Error verifying sealed query: {e}")
            return None

    def get_current_txid(self, db: Session) -> Optional[str]:
        """Fetch current transaction ID for optimistic updates (pg_current_xact_id)."""
        try:
            res = db.execute(text("SELECT pg_current_xact_id()::text")).scalar()
            return str(res)
        except Exception:
            # Fallback for SQLite or when xact_id is not available
            return str(int(time.time() * 1000))


neon_realtime = NeonRealtimeService()
