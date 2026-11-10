"""Comprehensive Test Suite for Gemini AI Configuration and Quiz Generation.

Covers:
1. settings.GEMINI_API_KEY loading from environment and fallback
2. _make_client() factory, SSL HttpOptions configuration, and fallback handling
3. 503 Service Unavailable handling for missing AND whitespace-only API keys
4. System SSL context crash resilience raising HTTP 503
5. Timeout error string matching ("timed out", "time out", "Request timed out") mapping to HTTP 504
6. Live gemini-2.5-flash model invocation with active key and rate-limit safety
7. Mocked quiz generation supporting offline/CI environments and error branches
"""

import os
import sys
import json
import ssl
import asyncio
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from app.core.config import settings, Settings
from app.services.quiz_service.generator import (
    _make_client,
    _handle_error,
    _parse_questions,
    generate_quiz,
    _StoredQuestion,
)


# Reusable mock question payload (10 valid questions)
def _build_mock_quiz_json(count=10):
    questions = []
    for i in range(1, count + 1):
        questions.append({
            "id": i,
            "question": f"Sample concept question {i}?",
            "options": {
                "A": f"Option A for {i}",
                "B": f"Option B for {i}",
                "C": f"Option C for {i}",
                "D": f"Option D for {i}",
            },
            "correct": "B",
            "explanation": f"Explanation referencing lecture topic {i}.",
        })
    return json.dumps({"questions": questions})


SAMPLE_LECTURE_TEXT = (
    "Computer Networks and Layered Architecture: "
    "A computer network is a set of computers sharing resources located on or provided by network nodes. "
    "The computers use common communication protocols over digital interconnections to communicate with each other. "
    "These interconnections are made up of telecommunication network technologies, based on physically wired, optical, "
    "and wireless radio-frequency methods that may be arranged in a variety of network topologies. "
    "The Open Systems Interconnection (OSI) model describes seven distinct layers: Physical, Data Link, Network, "
    "Transport, Session, Presentation, and Application. "
    "The Transport layer provides host-to-host communication services for applications through protocols such as TCP and UDP. "
    "TCP provides reliable, ordered, and error-checked delivery of a stream of octets between applications running on hosts. "
    "UDP provides connectionless communication with minimal protocol overhead, making it suitable for real-time applications. "
    "The Network layer manages packet forwarding including routing through intermediate routers. "
    "IP addresses identify network interfaces and provide addressing across interconnected networks. "
    "Subnetting divides a larger network into smaller subnetworks, improving security and performance."
)


class TestGeminiConfig(unittest.TestCase):
    """Test 1: Verification of settings.GEMINI_API_KEY loading."""

    def test_01_gemini_api_key_loaded_from_settings(self):
        """Verify GEMINI_API_KEY is present and formatted correctly."""
        self.assertTrue(hasattr(settings, "GEMINI_API_KEY"))
        self.assertIsInstance(settings.GEMINI_API_KEY, str)
        self.assertTrue(
            len(settings.GEMINI_API_KEY) > 0,
            "GEMINI_API_KEY must be populated in backend/.env",
        )
        self.assertTrue(
            settings.GEMINI_API_KEY.startswith("AQ."),
            "GEMINI_API_KEY should start with 'AQ.'",
        )

    def test_02_gemini_api_key_empty_fallback(self):
        """Verify Settings defaults to empty string when environment variable is unset."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            fresh_settings = Settings()
            self.assertEqual(fresh_settings.GEMINI_API_KEY, "")


class TestGeminiClientFactory(unittest.TestCase):
    """Test 2 & 3: Verification of _make_client(), SSL options, and 503 error handling."""

    def test_01_make_client_with_valid_key(self):
        """Verify _make_client returns a valid google.genai.Client with HttpOptions."""
        from google import genai

        with patch.object(settings, "GEMINI_API_KEY", "AQ.dummy_key_for_client_factory_test"):
            client = _make_client()
            self.assertIsInstance(client, genai.Client)
            self.assertEqual(client._api_client.api_key, "AQ.dummy_key_for_client_factory_test")

    def test_02_make_client_ssl_options_configured(self):
        """Verify _make_client includes HttpOptions verify context."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.dummy_key"):
            client = _make_client()
            self.assertIsNotNone(client._api_client._http_options)
            self.assertIsNotNone(client._api_client._http_options.client_args.get("verify"))

    def test_03_make_client_missing_key_raises_503(self):
        """Test 3: Verify 503 Service Unavailable when GEMINI_API_KEY is empty or None."""
        for empty_val in ("", None):
            with self.subTest(val=repr(empty_val)):
                with patch.object(settings, "GEMINI_API_KEY", empty_val):
                    with self.assertRaises(HTTPException) as ctx:
                        _make_client()
                    self.assertEqual(ctx.exception.status_code, 503)
                    self.assertIn("GEMINI_API_KEY is not set", ctx.exception.detail)

    def test_03b_make_client_whitespace_key_raises_503(self):
        """Verify 503 Service Unavailable when GEMINI_API_KEY contains only whitespace."""
        whitespace_samples = [" ", "   ", "\t", "\n", "\r\n  \t "]
        for ws in whitespace_samples:
            with self.subTest(ws=repr(ws)):
                with patch.object(settings, "GEMINI_API_KEY", ws):
                    with self.assertRaises(HTTPException) as ctx:
                        _make_client()
                    self.assertEqual(ctx.exception.status_code, 503)
                    self.assertIn("GEMINI_API_KEY is not set", ctx.exception.detail)

    def test_04_make_client_ssl_failure_graceful_fallback(self):
        """Verify _make_client falls back to default http_options if SSL cert loading fails."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.dummy_key"):
            with patch.object(ssl.SSLContext, "load_default_certs", side_effect=RuntimeError("Simulated cert failure")):
                client = _make_client()
                self.assertIsNotNone(client)
                self.assertEqual(client._api_client.api_key, "AQ.dummy_key")

    def test_05_make_client_system_ssl_crash_raises_503(self):
        """Verify _make_client raises HTTP 503 when system SSL context initialization crashes."""
        ssl_failures = [
            ssl.SSLError("Simulated system SSLError"),
            OSError("Crypto API failure"),
            RuntimeError("System TLS failure"),
        ]
        for err in ssl_failures:
            with self.subTest(err=repr(err)):
                with patch.object(settings, "GEMINI_API_KEY", "AQ.dummy_key"):
                    with patch("ssl.create_default_context", side_effect=err):
                        with self.assertRaises(HTTPException) as ctx:
                            _make_client()
                        self.assertEqual(ctx.exception.status_code, 503)
                        self.assertIn("Failed to initialize Gemini AI client", ctx.exception.detail)


class TestGeminiQuizGeneratorMocked(unittest.TestCase):
    """Test 5: Mocked generation supporting offline/CI environments."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_01_generate_quiz_success(self):
        """Verify full mocked quiz generation pipeline returns 10 questions."""
        mock_response = MagicMock()
        mock_response.text = _build_mock_quiz_json(10)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            questions = self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(len(questions), 10)
            self.assertEqual(questions[0].id, 1)
            self.assertEqual(questions[0].correct, "B")
            self.assertIn("A", questions[0].options)
            self.assertIn("D", questions[0].options)

    def test_02_generate_quiz_markdown_codeblock_stripping(self):
        """Verify parser handles ```json codeblock delimiters."""
        raw_json = _build_mock_quiz_json(5)
        markdown_wrapped = f"```json\n{raw_json}\n```"

        mock_response = MagicMock()
        mock_response.text = markdown_wrapped

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            questions = self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(len(questions), 5)

    def test_03_generate_quiz_text_too_short_raises_422(self):
        """Verify input with < 200 characters is rejected with 422."""
        with self.assertRaises(HTTPException) as ctx:
            self.loop.run_until_complete(generate_quiz("Short text"))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("too little extractable text", ctx.exception.detail)

    def test_04_generate_quiz_too_few_questions_raises_502(self):
        """Verify response with < 5 questions raises 502."""
        mock_response = MagicMock()
        mock_response.text = _build_mock_quiz_json(3)

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            with self.assertRaises(HTTPException) as ctx:
                self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(ctx.exception.status_code, 502)
            self.assertIn("too few questions", ctx.exception.detail)

    def test_05_generate_quiz_retry_on_malformed_json(self):
        """Verify retry loop: recovers when attempt 1 is malformed but attempt 2 succeeds."""
        mock_resp_bad = MagicMock()
        mock_resp_bad.text = "NOT JSON"

        mock_resp_good = MagicMock()
        mock_resp_good.text = _build_mock_quiz_json(10)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [mock_resp_bad, mock_resp_good]

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            questions = self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(len(questions), 10)
            self.assertEqual(mock_client.models.generate_content.call_count, 2)

    def test_06_generate_quiz_missing_key_propagates_503(self):
        """Verify generate_quiz raises 503 when GEMINI_API_KEY is not set."""
        with patch.object(settings, "GEMINI_API_KEY", ""):
            with self.assertRaises(HTTPException) as ctx:
                self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("GEMINI_API_KEY is not set", ctx.exception.detail)

    def test_06b_generate_quiz_whitespace_key_propagates_503(self):
        """Verify generate_quiz raises 503 when GEMINI_API_KEY is whitespace-only."""
        for ws_key in (" ", "   ", "\t", "\n"):
            with self.subTest(key=repr(ws_key)):
                with patch.object(settings, "GEMINI_API_KEY", ws_key):
                    with self.assertRaises(HTTPException) as ctx:
                        self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
                    self.assertEqual(ctx.exception.status_code, 503)
                    self.assertIn("GEMINI_API_KEY is not set", ctx.exception.detail)

    def test_07_error_handling_quota_exhausted_429(self):
        """Verify 429 quota exhaustion is mapped to HTTPException 429."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 Resource exhausted: quota exceeded")

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            with self.assertRaises(HTTPException) as ctx:
                self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(ctx.exception.status_code, 429)

    def test_08_error_handling_invalid_api_key_401(self):
        """Verify invalid API key error is mapped to HTTPException 401."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API_KEY_INVALID: 403 Forbidden")

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            with self.assertRaises(HTTPException) as ctx:
                self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_09_error_handling_timeout_504(self):
        """Verify deadline exceeded and all timeout variants are mapped to HTTPException 504."""
        timeout_messages = [
            "504 Deadline exceeded: timeout",
            "Request timed out after 30000ms",
            "connection timed out",
            "Read timed out",
            "Gateway time out",
            "Connection time out",
            "Client deadline exceeded",
        ]
        for err_msg in timeout_messages:
            with self.subTest(msg=err_msg):
                mock_client = MagicMock()
                mock_client.models.generate_content.side_effect = Exception(err_msg)

                with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
                    with self.assertRaises(HTTPException) as ctx:
                        self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
                    self.assertEqual(ctx.exception.status_code, 504)
                    self.assertIn("timed out", ctx.exception.detail)

    def test_10_handle_error_timeout_variations_direct(self):
        """Direct unit verification of _handle_error mapping timeout strings to 504."""
        timeout_phrases = [
            "timed out",
            "time out",
            "Request timed out after 30000ms",
            "Read timed out",
            "upstream connect time out",
            "deadline",
            "timeout",
        ]
        for phrase in timeout_phrases:
            with self.subTest(phrase=phrase):
                with self.assertRaises(HTTPException) as ctx:
                    _handle_error(Exception(phrase))
                self.assertEqual(ctx.exception.status_code, 504)
                self.assertIn("timed out", ctx.exception.detail)

    def test_11_generate_quiz_system_ssl_crash_propagates_503(self):
        """Verify generate_quiz propagates 503 when system SSL context initialization crashes."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.dummy_key"):
            with patch("ssl.create_default_context", side_effect=ssl.SSLError("Crypto API failure")):
                with self.assertRaises(HTTPException) as ctx:
                    self.loop.run_until_complete(generate_quiz(SAMPLE_LECTURE_TEXT))
                self.assertEqual(ctx.exception.status_code, 503)
                self.assertIn("Failed to initialize Gemini AI client", ctx.exception.detail)


class TestGeminiLiveInvocation(unittest.TestCase):
    """Test 4: Live model invocation with gemini-2.5-flash using configured key."""

    def test_01_live_gemini_2_5_flash_invocation(self):
        """Live probe to gemini-2.5-flash using configured key."""
        if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
            self.skipTest("GEMINI_API_KEY is not set in backend/.env; skipping live test.")

        try:
            client = _make_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Respond with only the word: VERIFIED",
            )
            self.assertIsNotNone(response)
            self.assertTrue(bool(response.text))
            self.assertIn("VERIFIED", response.text.upper())
        except Exception as exc:
            exc_str = str(exc).lower()
            # If running in strictly air-gapped environment without internet access
            if "getaddrinfo failed" in exc_str or "connecterror" in exc_str:
                self.skipTest(f"Live network unavailable: {exc}")
            # If live API quota limit reached on shared development key
            elif "429" in exc_str or "resource_exhausted" in exc_str or "quota" in exc_str:
                self.skipTest(f"Live Gemini API quota limit reached on key: {exc}")
            # If live API is experiencing transient high demand
            elif "503" in exc_str or "high demand" in exc_str or "unavailable" in exc_str:
                self.skipTest(f"Live Gemini API temporarily unavailable: {exc}")
            else:
                raise


if __name__ == "__main__":
    unittest.main()
