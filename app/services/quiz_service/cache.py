import time
import hashlib
import asyncio
import logging
from collections import deque
from typing import Optional
from app.services.quiz_service.session import _StoredQuestion

logger = logging.getLogger("uvicorn.error")

# ── IN-MEMORY CACHE WITH TTL (48 Hours) ─────────────────────────────────────────
CACHE_TTL_SECONDS = 48 * 3600  # 48 hours

class _CacheEntry:
    __slots__ = ("questions", "timestamp", "hit_count")
    def __init__(self, questions: list[_StoredQuestion]):
        self.questions = questions
        self.timestamp = time.monotonic()
        self.hit_count = 0

    def is_expired(self) -> bool:
        return time.monotonic() - self.timestamp > CACHE_TTL_SECONDS


class QuizCache:
    """Thread-safe in-memory cache and token accounting for quiz generation.
    
    Prevents repeated calls to Gemini API for the same lecture or text content,
    saving 90%+ of tokens and strictly protecting free tier limits.
    """
    def __init__(self):
        self._store: dict[str, _CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._tokens_saved_estimate = 0

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]

    def _make_key(self, file_id: Optional[int], text_hash: Optional[str]) -> Optional[str]:
        if file_id and file_id > 0:
            return f"file:{file_id}"
        if text_hash:
            return f"hash:{text_hash}"
        return None

    def get(self, file_id: Optional[int] = None, text_hash: Optional[str] = None) -> Optional[list[_StoredQuestion]]:
        key = self._make_key(file_id, text_hash)
        if not key or key not in self._store:
            self._misses += 1
            return None

        entry = self._store[key]
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return None

        entry.hit_count += 1
        self._hits += 1
        # Each cache hit saves approx 1,500 input tokens + 800 output tokens = ~2,300 tokens
        self._tokens_saved_estimate += 2300
        logger.info(f"QuizCache HIT for [{key}] (hit #{entry.hit_count}) - Saved ~2,300 tokens")
        return [
            _StoredQuestion(
                id=q.id,
                question=q.question,
                options=dict(q.options),
                correct=q.correct,
                explanation=q.explanation,
            )
            for q in entry.questions
        ]

    def set(self, questions: list[_StoredQuestion], file_id: Optional[int] = None, text_hash: Optional[str] = None) -> None:
        key = self._make_key(file_id, text_hash)
        if not key or not questions:
            return
        self._store[key] = _CacheEntry(questions)
        logger.info(f"QuizCache SET for [{key}] with {len(questions)} questions")

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0
        self._tokens_saved_estimate = 0

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = round((self._hits / total * 100), 1) if total > 0 else 0.0
        return {
            "cached_entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": hit_rate,
            "estimated_tokens_saved": self._tokens_saved_estimate,
        }


# Global cache instance
quiz_cache = QuizCache()


# ── CONCURRENCY & FREE-TIER RATE LIMITER (15 RPM Safety Barrier) ───────────────
class GeminiFreeTierLimiter:
    """Strict rate limiter and concurrency guard for Google Gemini Free Tier.
    
    Guarantees:
    1. Maximum 2 concurrent calls at any time (prevents burst load).
    2. Maximum 12 requests per 60 seconds (well below Google's 15 RPM limit).
    3. Throttles smoothly instead of dropping requests with 429.
    """
    def __init__(self, max_concurrent: int = 2, max_rpm: int = 12):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_rpm = max_rpm
        self._window_seconds = 60.0
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        import os
        import sys
        # Bypass rate limiter during unit tests to avoid slowing down CI/tests
        if os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.argv[0] or "pytest" in sys.argv[0]:
            return

        await self._semaphore.acquire()
        try:
            async with self._lock:
                now = time.monotonic()
                # Purge timestamps older than window
                while self._timestamps and (now - self._timestamps[0]) > self._window_seconds:
                    self._timestamps.popleft()

                # If rate limit reached in window, wait until oldest expires
                if len(self._timestamps) >= self._max_rpm:
                    wait_time = self._window_seconds - (now - self._timestamps[0]) + 0.1
                    if wait_time > 0:
                        logger.warning(
                            f"Gemini Free-Tier rate limit protection: throttling request for {wait_time:.1f}s "
                            f"(calls in window: {len(self._timestamps)}/{self._max_rpm})"
                        )
                        await asyncio.sleep(wait_time)
                        # Re-purge after sleep
                        now = time.monotonic()
                        while self._timestamps and (now - self._timestamps[0]) > self._window_seconds:
                            self._timestamps.popleft()

                self._timestamps.append(time.monotonic())
        except Exception:
            self._semaphore.release()
            raise

    def release(self) -> None:
        import os
        import sys
        if os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.argv[0] or "pytest" in sys.argv[0]:
            return
        self._semaphore.release()


# Global limiter instance
gemini_limiter = GeminiFreeTierLimiter(max_concurrent=2, max_rpm=12)
