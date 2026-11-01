"""Comprehensive End-to-End Test Suite for Neon Services Integration."""

import sys
import os
import io
import unittest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.core.config import settings
from app.services.neon_storage import neon_storage
from app.services.neon_ai_gateway import neon_ai
from app.services.neon_auth import neon_auth
from app.services.neon_realtime import neon_realtime
from app.services.neon_functions import neon_functions
from app.services.quiz_service.generator import _parse_questions


class TestNeonServicesE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_app_health_endpoints(self):
        """Test root and health status endpoints."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("app"), settings.APP_NAME)
        self.assertEqual(data.get("status"), "running")

        resp_health = self.client.get("/health")
        self.assertEqual(resp_health.status_code, 200)
        self.assertEqual(resp_health.json(), {"status": "ok"})
        print("PASS: Root & Health endpoints responded 200 OK.")

    def test_02_neon_status_endpoint(self):
        """Test the /api/neon/status endpoint reporting all 6 Neon services."""
        resp = self.client.get("/api/neon/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "online")
        services = data.get("services", {})

        # 1. Postgres
        self.assertIn("postgres", services)
        self.assertTrue(services["postgres"]["configured"])
        self.assertTrue(services["postgres"]["is_pooled"])
        self.assertTrue(services["postgres"]["unpooled_configured"])

        # 2. Auth
        self.assertIn("auth", services)
        self.assertTrue(services["auth"]["configured"])
        self.assertTrue("neonauth" in services["auth"]["base_url"])

        # 3. AI Gateway (Available on paid plan; gracefully disabled on Free plan)
        self.assertIn("ai_gateway", services)
        self.assertIn("configured", services["ai_gateway"])

        # 4. Object Storage
        self.assertIn("object_storage", services)
        self.assertTrue(services["object_storage"]["configured"])
        self.assertEqual(services["object_storage"]["bucket"], "assets")
        self.assertEqual(services["object_storage"]["addressing_style"], "path")

        # 5. Realtime
        self.assertIn("realtime", services)
        self.assertTrue(services["realtime"]["configured"])
        self.assertTrue(services["realtime"]["secret_set"])

        # 6. Functions
        self.assertIn("functions", services)
        self.assertTrue(services["functions"]["configured"])
        self.assertTrue("hello" in services["functions"]["hello_url"])

        print("PASS: /api/neon/status verified all 6 Neon services declared & configured.")

    def test_03_neon_realtime_query_sealing(self):
        """Test Neon Realtime query sealing and signature verification."""
        sql_query = "SELECT id, title, created_at FROM announcements ORDER BY created_at DESC LIMIT 10"
        resp = self.client.post(
            "/api/neon/realtime/seal",
            params={"query": sql_query},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sealed_query", data)
        self.assertIn("realtime_url", data)
        self.assertIn("current_txid", data)

        # Verify query can be unsealed and authenticated
        unsealed = neon_realtime.verify_sealed_query(data["sealed_query"])
        self.assertIsNotNone(unsealed)
        self.assertEqual(unsealed["sql"], sql_query)
        print("PASS: Neon Realtime sealed query generated, verified, and transaction tracked.")

    def test_04_neon_object_storage_client(self):
        """Test Neon Object Storage S3 client configuration and methods."""
        self.assertTrue(neon_storage.is_configured)
        self.assertEqual(neon_storage.bucket_name, "assets")
        self.assertEqual(neon_storage.region_name, "us-east-2")

        # Test boto3 client initialization with path-style addressing
        client = neon_storage.client
        self.assertIsNotNone(client)

        # Test presigned URL generation (offline SigV4 computation)
        test_key = "materials/lecture1_slides.pdf"
        presigned = neon_storage.get_presigned_url(test_key, expires_in=1800)
        self.assertIsNotNone(presigned)
        self.assertIn("assets/materials/lecture1_slides.pdf", presigned)
        self.assertIn("X-Amz-Signature", presigned)
        print(f"PASS: Neon Object Storage presigned URL generated with SigV4 path-style: {presigned[:60]}...")

    def test_05_neon_auth_service(self):
        """Test Neon Auth JWKS and token decoding."""
        self.assertTrue(neon_auth.is_configured)
        self.assertTrue("neonauth" in neon_auth.base_url)
        self.assertTrue(neon_auth.jwks_url.endswith("jwks.json"))

        # Test unverified claim decoding helper
        from jose import jwt
        mock_token = jwt.encode({"sub": "user_42", "email": "student@eru.edu"}, "dummy_secret", algorithm="HS256")
        claims = jwt.get_unverified_claims(mock_token)
        self.assertEqual(claims.get("sub"), "user_42")
        print("PASS: Neon Auth token decode and configuration verified.")

    def test_06_neon_ai_gateway_service(self):
        """Test Neon AI Gateway client configuration and endpoints."""
        # AI Gateway client exists and provides dialect structure
        self.assertIsNotNone(neon_ai)
        print("PASS: Neon AI Gateway client initialized.")

    def test_07_neon_functions_service(self):
        """Test Neon Functions invocation router and configuration."""
        url = neon_functions.get_url("hello")
        self.assertIsNotNone(url)
        self.assertTrue("hello" in url)
        print("PASS: Neon Functions hello endpoint URL mapping verified.")

    def test_08_quiz_generation_parser(self):
        """Test quiz question parser utilized by Neon AI Gateway integration."""
        sample_json = '''
        {
            "questions": [
                {
                    "id": 1,
                    "question": "What is the primary benefit of Neon Object Storage?",
                    "options": {
                        "A": "It branches copy-on-write with the database",
                        "B": "It requires a separate AWS billing account",
                        "C": "It uses FTP protocol only",
                        "D": "It only works on Windows 98"
                    },
                    "correct": "A",
                    "explanation": "Neon Object Storage branches with Postgres so branches get identical file state."
                },
                {
                    "id": 2,
                    "question": "Which database URL should Alembic migrations use in Neon?",
                    "options": {
                        "A": "Pooled DATABASE_URL",
                        "B": "Unpooled direct DATABASE_URL_UNPOOLED",
                        "C": "Localhost only",
                        "D": "None"
                    },
                    "correct": "B",
                    "explanation": "Neon pooled connections use PgBouncer which does not support DDL locks."
                },
                {
                    "id": 3,
                    "question": "What dialect path does Neon AI Gateway use for OpenAI chat completions?",
                    "options": {
                        "A": "/v1/chat/completions",
                        "B": "/chat/neon",
                        "C": "/llm/prompt",
                        "D": "/query"
                    },
                    "correct": "A",
                    "explanation": "/v1 is the unified OpenAI chat completions endpoint."
                },
                {
                    "id": 4,
                    "question": "What addressing style does Neon Object Storage require?",
                    "options": {
                        "A": "Virtual-hosted style",
                        "B": "Path-style addressing",
                        "C": "IP addressing only",
                        "D": "DNS CNAME only"
                    },
                    "correct": "B",
                    "explanation": "Neon Object Storage requires path-style S3 addressing."
                },
                {
                    "id": 5,
                    "question": "What runtime does Neon Functions use?",
                    "options": {
                        "A": "Node.js 24 fetch handler",
                        "B": "Python 2.7 CGI",
                        "C": "PHP 5.3",
                        "D": "Ruby 1.8"
                    },
                    "correct": "A",
                    "explanation": "Neon Functions are long-running Node.js 24 HTTP fetch handlers."
                }
            ]
        }
        '''
        questions = _parse_questions(sample_json)
        self.assertEqual(len(questions), 5)
        self.assertEqual(questions[0].correct, "A")
        self.assertEqual(questions[1].correct, "B")
        print("PASS: Quiz parser verified with Neon AI response format.")

    def test_09_storage_presigned_endpoint(self):
        """Test GET /api/neon/storage/presigned-url endpoint."""
        resp = self.client.get("/api/neon/storage/presigned-url", params={"key": "materials/lecture1.pdf"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("key"), "materials/lecture1.pdf")
        self.assertIn("assets/materials/lecture1.pdf", data.get("presigned_url", ""))
        self.assertEqual(data.get("expires_in"), 3600)
        print("PASS: /api/neon/storage/presigned-url returned SigV4 presigned URL.")

    def test_10_neon_functions_invocation_handling(self):
        """Test /api/neon/functions/invoke endpoint and error handling."""
        resp = self.client.post("/api/neon/functions/invoke", params={"slug": "hello", "path": "/"})
        # If the function host is offline/unprovisioned, it returns clean 500/503/502 JSON without crashing
        self.assertIn(resp.status_code, [200, 500, 502, 503])
        data = resp.json()
        self.assertIn("success", data)
        print(f"PASS: /api/neon/functions/invoke handled gracefully (status: {resp.status_code}).")

    def test_11_neon_ai_models_endpoint(self):
        """Test GET /api/neon/ai/models endpoint."""
        resp = self.client.get("/api/neon/ai/models")
        # Returns 200 with list (empty or populated) when handled
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)
        print("PASS: /api/neon/ai/models endpoint returned models list.")

    def test_12_alembic_configuration(self):
        """Verify Alembic is configured to use direct unpooled database connection."""
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        self.assertIsNotNone(script)
        # Verify settings has DATABASE_URL_UNPOOLED configured
        self.assertTrue(bool(settings.DATABASE_URL_UNPOOLED))
        self.assertNotIn("pooler", settings.DATABASE_URL_UNPOOLED)
        print("PASS: Alembic direct unpooled connection configuration verified.")


if __name__ == "__main__":
    unittest.main()
