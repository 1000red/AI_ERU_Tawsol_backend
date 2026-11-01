"""Neon AI Gateway Service.

Provides a unified API and single credential for LLMs (Claude, GPT, Gemini)
branch-scoped to this Neon environment.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NeonAIGatewayService:
    def __init__(self):
        self.base_url = settings.NEON_AI_GATEWAY_BASE_URL.rstrip("/")
        self.token = settings.NEON_AI_GATEWAY_TOKEN

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from the branch endpoint /v1/models."""
        if not self.is_configured:
            return []

        url = f"{self.base_url}/v1/models"
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("data", [])
                logger.warning(f"Neon AI Gateway list models returned status {resp.status_code}")
                return []
            except Exception as e:
                logger.error(f"Error querying Neon AI Gateway models: {e}")
                return []

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Unified Chat Completions endpoint (/v1/chat/completions)."""
        if not self.is_configured:
            return None

        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            try:
                resp = await client.post(url, headers=self.headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content")
                logger.warning(f"Neon AI Gateway chat completion failed ({resp.status_code}): {resp.text}")
                return None
            except Exception as e:
                logger.error(f"Error calling Neon AI Gateway: {e}")
                return None


neon_ai = NeonAIGatewayService()
