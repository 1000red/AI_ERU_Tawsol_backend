"""Adversarial stress test suite for Milestone M1 (Challenger M1-2).

Empirically tests:
1. Multi-threaded and concurrent client initialization (_make_client() under thread & task storms).
2. Path anchoring and settings loading across varied directories and altered environment variables.
3. SSLContext failure resilience under multiple simulated failure modes.
"""

import os
import sys
import ssl
import subprocess
import threading
import asyncio
import concurrent.futures
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
from app.core.config import settings, Settings, get_settings
from app.services.quiz_service.generator import _make_client, generate_quiz


class TestAdversarialConcurrency(unittest.TestCase):
    """Stress testing concurrent and multi-threaded initialization of _make_client()."""

    def test_01_multithreaded_make_client_storm(self):
        """Invoke _make_client() simultaneously from 50 worker threads."""
        num_threads = 50
        barrier = threading.Barrier(num_threads)
        results = []
        errors = []

        def worker():
            try:
                # Synchronize start across all threads to maximize contention
                barrier.wait(timeout=10)
                client = _make_client()
                results.append(client)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(len(errors), 0, f"Thread errors encountered: {errors}")
        self.assertEqual(len(results), num_threads)
        for client in results:
            self.assertIsNotNone(client)
            self.assertEqual(client._api_client.api_key, settings.GEMINI_API_KEY)
            self.assertIsNotNone(client._api_client._http_options)

    def test_02_asyncio_concurrent_tasks(self):
        """Invoke _make_client() simultaneously from 50 asyncio tasks."""
        async def run_tasks():
            tasks = [asyncio.to_thread(_make_client) for _ in range(50)]
            return await asyncio.gather(*tasks, return_exceptions=True)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(run_tasks())
            self.assertEqual(len(results), 50)
            for res in results:
                self.assertFalse(isinstance(res, Exception), f"Async task failed: {res}")
                self.assertEqual(res._api_client.api_key, settings.GEMINI_API_KEY)
        finally:
            loop.close()

    def test_03_concurrent_client_instantiation_isolation(self):
        """Verify 30 concurrent threads creating clients produce independent, isolated client instances."""
        clients = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(_make_client) for _ in range(30)]
            for f in concurrent.futures.as_completed(futures):
                clients.append(f.result())

        self.assertEqual(len(clients), 30)
        # Verify all clients have the correct key and non-interfering HTTP options
        for c in clients:
            self.assertEqual(c._api_client.api_key, settings.GEMINI_API_KEY)
            self.assertIsNotNone(c._api_client._http_options)

    def test_04_concurrent_quiz_generation_mocked(self):
        """Verify 20 simultaneous quiz generation requests do not suffer race conditions."""
        sample_text = (
            "Software engineering design patterns provide reusable solutions to common software design problems. "
            "Creational patterns deal with object creation mechanisms. Structural patterns ease design by identifying "
            "a simple way to realize relationships among entities. Behavioral patterns identify common communication "
            "patterns between objects and realize these patterns. For instance, the Factory Method pattern defines an "
            "interface for creating an object, but lets subclasses decide which class to instantiate."
        )

        mock_payload = '{"questions": [' + ','.join([
            f'{{"id": {i}, "question": "Question {i}?", "options": {{"A": "1", "B": "2", "C": "3", "D": "4"}}, "correct": "A", "explanation": "Exp {i}"}}'
            for i in range(1, 11)
        ]) + ']}'

        mock_response = MagicMock()
        mock_response.text = mock_payload
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        async def run_concurrent_quizzes():
            with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
                tasks = [generate_quiz(sample_text) for _ in range(20)]
                return await asyncio.gather(*tasks)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(run_concurrent_quizzes())
            self.assertEqual(len(results), 20)
            for q_list in results:
                self.assertEqual(len(q_list), 10)
                self.assertEqual(q_list[0].id, 1)
        finally:
            loop.close()


class TestAdversarialPathAnchoring(unittest.TestCase):
    """Stress testing path anchoring, working directory independence, and env var overrides."""

    def test_01_settings_loading_from_multiple_cwds(self):
        """Execute independent python subprocesses from diverse working directories."""
        test_cwds = [
            str(BACKEND_DIR.parent),                     # C:\Users\dell\.gemini\antigravity\scratch
            str(BACKEND_DIR / "app" / "core"),           # Subdirectory inside package
            str(BACKEND_DIR / "app"),                    # Intermediate subdirectory
            os.environ.get("TEMP", "C:\\Windows\\Temp"), # System temp directory
        ]

        check_code = (
            f"import sys; sys.path.insert(0, r'{BACKEND_DIR}'); "
            "from app.core.config import settings; "
            "assert settings.GEMINI_API_KEY.startswith('AQ.'), f'Wrong key: {settings.GEMINI_API_KEY}'; "
            "print('SUCCESS')"
        )

        for cwd in test_cwds:
            if not os.path.exists(cwd):
                continue
            proc = subprocess.run(
                [sys.executable, "-c", check_code],
                cwd=cwd,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"Failed from CWD={cwd}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}",
            )
            self.assertIn("SUCCESS", proc.stdout)

    def test_02_environment_variable_precedence_override(self):
        """Verify explicit process environment variable overrides .env file."""
        override_key = "AQ.adversarial_override_key_999"
        check_code = (
            f"import sys; sys.path.insert(0, r'{BACKEND_DIR}'); "
            "from app.core.config import get_settings; "
            "s = get_settings(); "
            f"assert s.GEMINI_API_KEY == '{override_key}', f'Actual: {{s.GEMINI_API_KEY}}'; "
            "print('OVERRIDE_OK')"
        )
        env = os.environ.copy()
        env["GEMINI_API_KEY"] = override_key

        proc = subprocess.run(
            [sys.executable, "-c", check_code],
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Failed env override test\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}",
        )
        self.assertIn("OVERRIDE_OK", proc.stdout)

    def test_03_missing_dotenv_file_graceful_handling(self):
        """Verify Settings handles missing .env without unhandled exceptions."""
        with patch.object(Path, "exists", return_value=False):
            # When .env does not exist
            fresh_settings = Settings()
            self.assertIsInstance(fresh_settings, Settings)

    def test_04_lru_cache_and_cache_clear_behavior(self):
        """Verify get_settings() returns identical cached instances and reloads on cache_clear."""
        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)

        get_settings.cache_clear()
        s3 = get_settings()
        self.assertIsNotNone(s3)
        self.assertEqual(s3.GEMINI_API_KEY, s1.GEMINI_API_KEY)


class TestAdversarialSSLResilience(unittest.TestCase):
    """Stress testing SSL failure modes and fallback to uncustomized client."""

    def test_01_ssl_create_default_context_sslerror(self):
        """When ssl.create_default_context() raises ssl.SSLError."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.test_ssl_err"):
            with patch("ssl.create_default_context", side_effect=ssl.SSLError("Simulated SSLError")):
                with self.assertRaises(HTTPException) as ctx:
                    _make_client()
                self.assertEqual(ctx.exception.status_code, 503)
                self.assertIn("Failed to initialize Gemini AI client", ctx.exception.detail)

    def test_02_ssl_create_default_context_oserror(self):
        """When ssl.create_default_context() raises OSError."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.test_os_err"):
            with patch("ssl.create_default_context", side_effect=OSError("Crypto API failure")):
                with self.assertRaises(HTTPException) as ctx:
                    _make_client()
                self.assertEqual(ctx.exception.status_code, 503)
                self.assertIn("Failed to initialize Gemini AI client", ctx.exception.detail)

    def test_03_load_default_certs_attribute_error(self):
        """When ctx.load_default_certs is missing (AttributeError)."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.test_attr_err"):
            with patch.object(ssl.SSLContext, "load_default_certs", side_effect=AttributeError("No attribute")):
                client = _make_client()
                self.assertIsNotNone(client)
                self.assertEqual(client._api_client.api_key, "AQ.test_attr_err")

    def test_04_load_default_certs_permission_error(self):
        """When ctx.load_default_certs throws PermissionError."""
        with patch.object(settings, "GEMINI_API_KEY", "AQ.test_perm_err"):
            with patch.object(ssl.SSLContext, "load_default_certs", side_effect=PermissionError("Access denied")):
                client = _make_client()
                self.assertIsNotNone(client)
                self.assertEqual(client._api_client.api_key, "AQ.test_perm_err")

    def test_05_http_options_construction_failure(self):
        """When google.genai.types.HttpOptions raises a TypeError."""
        from google.genai import types
        with patch.object(settings, "GEMINI_API_KEY", "AQ.test_http_opt_err"):
            with patch.object(types, "HttpOptions", side_effect=TypeError("Bad args")):
                client = _make_client()
                self.assertIsNotNone(client)
                self.assertEqual(client._api_client.api_key, "AQ.test_http_opt_err")

    def test_06_genai_client_ssl_options_failure(self):
        """When genai.Client with http_options fails, falls back to basic Client."""
        from google import genai
        original_client_init = genai.Client.__init__

        calls = []

        def mock_client_init(self, *args, **kwargs):
            calls.append(kwargs)
            if kwargs.get("http_options") is not None:
                raise RuntimeError("Failed with http_options")
            return original_client_init(self, *args, **kwargs)

        with patch.object(settings, "GEMINI_API_KEY", "AQ.test_client_fallback"):
            with patch.object(genai.Client, "__init__", mock_client_init):
                client = _make_client()
                self.assertIsNotNone(client)
                # Verify that 2 calls occurred: first with http_options, second without
                self.assertEqual(len(calls), 2)
                self.assertIsNotNone(calls[0].get("http_options"))
                self.assertIsNone(calls[1].get("http_options"))


if __name__ == "__main__":
    unittest.main()
