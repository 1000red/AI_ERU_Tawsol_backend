"""Adversarial stress and edge-case verification suite for Milestone M1 (Challenger M1-1).

Verification scope:
1. Empty and whitespace API keys (503 Service Unavailable).
2. Invalid API keys (401 Unauthorized propagation).
3. Rate limit simulation (429 Too Many Requests propagation).
4. Malformed JSON outputs from LLM (retry on attempt 1, graceful 502 fallback on exhausted retries).
5. Text input length validation (< 50 chars and < 200 chars rejection with 422).
6. Live generation with actual configured GEMINI_API_KEY.
"""

import os
import sys
import json
import asyncio
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from app.core.config import settings
from app.services.quiz_service.generator import (
    _make_client,
    _handle_error,
    _parse_questions,
    generate_quiz,
    _StoredQuestion,
)


def _build_valid_quiz_payload(num_questions=10):
    """Generate valid quiz payload adhering to schema."""
    questions = []
    for i in range(1, num_questions + 1):
        questions.append({
            "id": i,
            "question": f"Question {i} about operating systems?",
            "options": {
                "A": f"Option A for Q{i}",
                "B": f"Option B for Q{i}",
                "C": f"Option C for Q{i}",
                "D": f"Option D for Q{i}",
            },
            "correct": "C",
            "explanation": f"Explanation for Q{i} referencing paging mechanisms.",
        })
    return json.dumps({"questions": questions})


SAMPLE_LECTURE = (
    "Virtual Memory Management in Modern Operating Systems: "
    "Virtual memory is a memory management technique that provides an idealized abstraction "
    "of the storage resources that are actually available on a given machine which creates the "
    "illusion to users of a very large (main) memory. The primary advantages of virtual memory "
    "include freeing applications from having to manage a shared memory space, increased security "
    "due to memory isolation, and being able to conceptually use more memory than might be physically "
    "available using the technique of paging. The Memory Management Unit (MMU) is the computer hardware "
    "component responsible for handling memory references requested by the central processing unit. "
    "Its functions include the translation of virtual addresses to physical addresses, memory protection, "
    "cache control, and bus arbitration."
)


class TestAdversarialApiKeyHandling(unittest.TestCase):
    """Stress testing _make_client() and error handling with edge-case keys."""

    def test_01_empty_string_api_key_raises_503(self):
        """Verify empty string GEMINI_API_KEY raises HTTPException 503."""
        with patch.object(settings, "GEMINI_API_KEY", ""):
            with self.assertRaises(HTTPException) as ctx:
                _make_client()
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("GEMINI_API_KEY is not set", ctx.exception.detail)

    def test_02_none_api_key_raises_503(self):
        """Verify None GEMINI_API_KEY raises HTTPException 503."""
        with patch.object(settings, "GEMINI_API_KEY", None):
            with self.assertRaises(HTTPException) as ctx:
                _make_client()
            self.assertEqual(ctx.exception.status_code, 503)

    def test_03_whitespace_api_keys_must_raise_503(self):
        """Adversarial edge case: Whitespace-only API keys ('   ', tabs, newlines) must raise 503."""
        whitespace_cases = [" ", "   ", "\t", "\n", "\r\n  \t "]
        for ws in whitespace_cases:
            with self.subTest(whitespace=repr(ws)):
                with patch.object(settings, "GEMINI_API_KEY", ws):
                    # Strict contract check: A whitespace-only key is invalid and unconfigured,
                    # so _make_client() MUST raise 503.
                    with self.assertRaises(HTTPException) as ctx:
                        _make_client()
                    self.assertEqual(
                        ctx.exception.status_code,
                        503,
                        f"Expected 503 for whitespace key {repr(ws)}, got {ctx.exception.status_code}",
                    )

    def test_04_invalid_key_error_propagation_401(self):
        """Verify invalid API key errors from Google SDK are caught and mapped to 401."""
        test_errors = [
            Exception("API_KEY_INVALID: 403 Forbidden"),
            Exception("401 Unauthorized: Invalid API key provided"),
            Exception("Request had invalid authentication credentials. Expected OAuth 2 access token, login cookie or other valid credential."),
        ]
        for err in test_errors:
            with self.subTest(err=str(err)):
                with self.assertRaises(HTTPException) as ctx:
                    _handle_error(err)
                self.assertEqual(ctx.exception.status_code, 401)
                self.assertIn("Invalid Gemini API key", ctx.exception.detail)


class TestAdversarialRateLimits(unittest.TestCase):
    """Stress testing rate limit handling under simulated spikes and quota exhaustion."""

    def test_01_quota_exhausted_propagation_429(self):
        """Verify 429 quota exhaustion error strings are mapped to HTTPException 429."""
        rate_limit_errors = [
            Exception("429 Resource exhausted: quota exceeded"),
            Exception("ResourceExhausted: 429 Online rate quota exceeded"),
            Exception("RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'Generate Content API requests'"),
            Exception("429 Too Many Requests: Rate limit reached"),
        ]
        for err in rate_limit_errors:
            with self.subTest(err=str(err)):
                with self.assertRaises(HTTPException) as ctx:
                    _handle_error(err)
                self.assertEqual(ctx.exception.status_code, 429)
                self.assertIn("rate limit reached", ctx.exception.detail)

    def test_02_timeout_deadline_propagation_504(self):
        """Verify deadline exceeded / timeout errors are mapped to HTTPException 504."""
        timeout_errors = [
            Exception("504 Deadline exceeded: timeout"),
            Exception("Request timed out after 30000ms"),
        ]
        for err in timeout_errors:
            with self.subTest(err=str(err)):
                with self.assertRaises(HTTPException) as ctx:
                    _handle_error(err)
                self.assertEqual(ctx.exception.status_code, 504)
                self.assertIn("timed out", ctx.exception.detail)


class TestAdversarialMalformedJsonAndRetries(unittest.TestCase):
    """Stress testing LLM response parsing, malformed JSON, retries, and fallback."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_01_retry_succeeds_after_malformed_json_attempt_1(self):
        """Attempt 1 returns malformed JSON; Attempt 2 returns valid JSON -> recovers cleanly."""
        resp_bad = MagicMock()
        resp_bad.text = '{"questions": [{"id": 1, "question": "Truncated...'

        resp_good = MagicMock()
        resp_good.text = _build_valid_quiz_payload(10)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_bad, resp_good]

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            questions = self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE))
            self.assertEqual(len(questions), 10)
            self.assertEqual(mock_client.models.generate_content.call_count, 2)

    def test_02_all_retries_fail_malformed_json_raises_502(self):
        """Both Attempt 1 and Attempt 2 return invalid JSON -> raises 502 with detail."""
        resp_bad1 = MagicMock()
        resp_bad1.text = "NOT EVEN JSON"

        resp_bad2 = MagicMock()
        resp_bad2.text = "<html><body>502 Bad Gateway from intermediate proxy</body></html>"

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_bad1, resp_bad2]

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            with self.assertRaises(HTTPException) as ctx:
                self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE))
            self.assertEqual(ctx.exception.status_code, 502)
            self.assertIn("malformed JSON", ctx.exception.detail)
            self.assertEqual(mock_client.models.generate_content.call_count, 2)

    def test_03_retry_succeeds_after_empty_safety_blocked_attempt_1(self):
        """Attempt 1 returns empty/None text (safety blocked); Attempt 2 returns valid JSON."""
        resp_blocked = MagicMock()
        # Simulate safety blocked response where .text raises ValueError or returns None
        resp_blocked.text = ""

        resp_good = MagicMock()
        resp_good.text = _build_valid_quiz_payload(10)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_blocked, resp_good]

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            questions = self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE))
            self.assertEqual(len(questions), 10)
            self.assertEqual(mock_client.models.generate_content.call_count, 2)

    def test_04_all_retries_empty_safety_blocked_raises_502(self):
        """Both attempts return empty text -> raises 502 describing empty/blocked response."""
        resp_blocked1 = MagicMock()
        resp_blocked1.text = ""
        resp_blocked2 = MagicMock()
        resp_blocked2.text = None

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [resp_blocked1, resp_blocked2]

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            with self.assertRaises(HTTPException) as ctx:
                self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE))
            self.assertEqual(ctx.exception.status_code, 502)
            self.assertIn("empty or blocked response", ctx.exception.detail)


class TestAdversarialTextValidation(unittest.TestCase):
    """Stress testing input text length boundaries."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_01_text_shorter_than_50_chars_raises_422(self):
        """Verify inputs under 50 characters are rejected with HTTPException 422."""
        short_inputs = [
            "",
            "A",
            "Too short lecture text.",
            "x" * 49,
        ]
        for text in short_inputs:
            with self.subTest(length=len(text)):
                with self.assertRaises(HTTPException) as ctx:
                    self.loop.run_until_complete(generate_quiz(text))
                self.assertEqual(ctx.exception.status_code, 422)
                self.assertIn("too little extractable text", ctx.exception.detail)

    def test_02_text_boundary_199_vs_200_chars(self):
        """Verify boundary condition: 199 chars raises 422, while 200 chars proceeds."""
        text_199 = "x" * 199
        with self.assertRaises(HTTPException) as ctx:
            self.loop.run_until_complete(generate_quiz(text_199))
        self.assertEqual(ctx.exception.status_code, 422)

        # 200 characters should proceed past length validation
        text_200 = "x" * 200
        mock_resp = MagicMock()
        mock_resp.text = _build_valid_quiz_payload(10)
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            questions = self.loop.run_until_complete(generate_quiz(text_200))
            self.assertEqual(len(questions), 10)


class TestAdversarialLiveGeminiVerification(unittest.TestCase):
    """Empirical live testing against Google Gemini using actual configured key."""

    def test_01_live_client_probe(self):
        """Live connectivity probe with model gemini-2.5-flash."""
        if not settings.GEMINI_API_KEY:
            self.skipTest("GEMINI_API_KEY not configured")

        client = _make_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Respond with only the word: VERIFIED",
        )
        self.assertIsNotNone(response)
        self.assertTrue(bool(response.text))
        self.assertIn("VERIFIED", response.text.upper())

    def test_02_live_generate_quiz_end_to_end(self):
        """Live end-to-end generate_quiz invocation with lecture text."""
        if not settings.GEMINI_API_KEY:
            self.skipTest("GEMINI_API_KEY not configured")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            questions = loop.run_until_complete(generate_quiz(SAMPLE_LECTURE))
            self.assertGreaterEqual(len(questions), 5)
            self.assertLessEqual(len(questions), 10)
            for q in questions:
                self.assertIsInstance(q, _StoredQuestion)
                self.assertIsInstance(q.id, int)
                self.assertTrue(bool(q.question))
                self.assertEqual(set(q.options.keys()), {"A", "B", "C", "D"})
                self.assertIn(q.correct, ["A", "B", "C", "D"])
                self.assertTrue(bool(q.explanation))
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
