import unittest
import asyncio
from unittest.mock import patch, MagicMock
from app.services.quiz_service.cache import QuizCache, GeminiFreeTierLimiter, quiz_cache
from app.services.quiz_service.compressor import clean_and_compress_text
from app.services.quiz_service.session import _StoredQuestion
from app.services.quiz_service.generator import generate_quiz


class TestGeminiTokenOptimization(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        quiz_cache.clear()

    def tearDown(self):
        quiz_cache.clear()
        self.loop.close()

    def test_01_compressor_reduces_text_size_and_strips_noise(self):
        noisy_text = """
        Lecture 1: Operating Systems
        Page 1 of 50
        Copyright 2026. All rights reserved.
        Downloaded from https://example.com/material.pdf
        
        An operating system manages computer hardware and software resources.
        An operating system manages computer hardware and software resources.
        
        It provides common services for computer programs.
        """ * 30  # Very large text (~9,000 chars)

        compressed = clean_and_compress_text(noisy_text, max_chars=1000)
        self.assertLessEqual(len(compressed), 1000)
        self.assertNotIn("Page 1 of 50", compressed)
        self.assertNotIn("Copyright 2026", compressed)
        self.assertIn("operating system manages", compressed)

    def test_02_quiz_cache_stores_and_retrieves_questions(self):
        cache = QuizCache()
        sample_qs = [
            _StoredQuestion(id=1, question="What is OS?", options={"A": "1", "B": "2", "C": "3", "D": "4"}, correct="A", explanation="Core OS"),
            _StoredQuestion(id=2, question="What is CPU?", options={"A": "1", "B": "2", "C": "3", "D": "4"}, correct="B", explanation="Core CPU"),
        ]

        self.assertIsNone(cache.get(file_id=42))
        cache.set(sample_qs, file_id=42)

        cached_qs = cache.get(file_id=42)
        self.assertIsNotNone(cached_qs)
        self.assertEqual(len(cached_qs), 2)
        self.assertEqual(cached_qs[0].question, "What is OS?")
        self.assertGreater(cache.stats["estimated_tokens_saved"], 0)
        self.assertEqual(cache.stats["hits"], 1)

    def test_03_generate_quiz_uses_cache_on_second_call_zero_tokens(self):
        sample_text = "This is a detailed technical lecture on Python data structures including lists, dictionaries, tuples, and sets. " * 10
        mock_response = MagicMock()
        mock_response.text = '{"questions": [' + ','.join([
            f'{{"id": {i}, "question": "Question {i}?", "options": {{"A": "optA", "B": "optB", "C": "optC", "D": "optD"}}, "correct": "A", "explanation": "Expl {i}"}}'
            for i in range(1, 6)
        ]) + ']}'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.services.quiz_service.generator._make_client", return_value=mock_client):
            # First call: cache miss -> invokes Gemini
            qs1 = self.loop.run_until_complete(generate_quiz(sample_text, num_questions=5, file_id=99))
            self.assertEqual(len(qs1), 5)
            self.assertEqual(mock_client.models.generate_content.call_count, 1)

            # Second call with same file_id: cache HIT -> ZERO calls to Gemini!
            qs2 = self.loop.run_until_complete(generate_quiz(sample_text, num_questions=5, file_id=99))
            self.assertEqual(len(qs2), 5)
            self.assertEqual(mock_client.models.generate_content.call_count, 1)  # STILL 1, no new API call!

            # Third call with force_refresh=True: bypasses cache -> invokes Gemini
            qs3 = self.loop.run_until_complete(generate_quiz(sample_text, num_questions=5, force_refresh=True, file_id=99))
            self.assertEqual(len(qs3), 5)
            self.assertEqual(mock_client.models.generate_content.call_count, 2)  # Incremented to 2


if __name__ == "__main__":
    unittest.main()
