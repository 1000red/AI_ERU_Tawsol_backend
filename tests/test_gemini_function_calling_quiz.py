import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException

from app.services.quiz_service.session import (
    _StoredQuestion,
    create_session,
    get_question,
    get_session,
    update_session_questions,
    replace_session_question,
)
from app.services.quiz_service.generator import (
    _build_quiz_tool,
    _build_single_question_tool,
    _extract_stored_questions_from_call_args,
    _parse_questions_json_fallback,
    generate_quiz,
    regenerate_single_question,
)
from app.schemas.quiz import (
    QuizOption,
    QuizQuestionUpdateItem,
    QuizUpdateQuestionsRequest,
    QuizRegenerateQuestionRequest,
)


class TestGeminiFunctionCallingQuiz(unittest.IsolatedAsyncioTestCase):

    def test_01_build_quiz_tool_schema(self):
        """Verify the Gemini Function Calling tool is properly defined with typed schema and quotes."""
        tool = _build_quiz_tool()
        self.assertIsNotNone(tool)
        self.assertTrue(len(tool.function_declarations) > 0)
        decl = tool.function_declarations[0]
        self.assertEqual(decl.name, "save_quiz_questions")
        params = decl.parameters
        self.assertIn("questions", params.properties)

    def test_02_build_single_question_tool_schema(self):
        """Verify the single question function declaration for regeneration."""
        tool = _build_single_question_tool()
        self.assertIsNotNone(tool)
        self.assertTrue(len(tool.function_declarations) > 0)
        decl = tool.function_declarations[0]
        self.assertEqual(decl.name, "save_single_question")
        props = decl.parameters.properties
        self.assertIn("reference_quote", props)
        self.assertIn("options", props)
        self.assertIn("correct", props)

    def test_03_extract_stored_questions_from_call_args(self):
        """Verify parsing function call argument dictionary into _StoredQuestion dataclasses."""
        mock_args = {
            "questions": [
                {
                    "id": 1,
                    "question": "ما هو دور جدار الحماية (Firewall) في شبكات الحاسب؟",
                    "options": {
                        "A": "مراقبة وفلترة حركة المرور للبيانات الواردة والصادرة",
                        "B": "زيادة سرعة المعالج في السيرفر",
                        "C": "توليد كود HTML للصفحات",
                        "D": "طباعة التقارير الإدارية",
                    },
                    "correct": "A",
                    "explanation": "جدار الحماية يعمل كحاجز أمني بين الشبكة الداخلية والخارجية.",
                    "reference_quote": "يعتبر جدار الحماية خط الدفاع الأول في تأمين الشبكة عبر فحص الحزم.",
                },
                {
                    "id": 2,
                    "question": "أي بروتوكول يُستخدم لنقل الصفحات المشفرة عبر الويب؟",
                    "options": {
                        "A": "HTTP",
                        "B": "HTTPS",
                        "C": "FTP",
                        "D": "SMTP",
                    },
                    "correct": "B",
                    "explanation": "HTTPS يستخدم TLS/SSL لتشفير البيانات.",
                    "reference_quote": "يعتمد بروتوكول HTTPS على التشفير الآمن لنقل البيانات عبر المنفذ 443.",
                }
            ]
        }
        questions = _extract_stored_questions_from_call_args(mock_args)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].id, 1)
        self.assertEqual(questions[0].correct, "A")
        self.assertEqual(
            questions[0].reference_quote,
            "يعتبر جدار الحماية خط الدفاع الأول في تأمين الشبكة عبر فحص الحزم."
        )
        self.assertEqual(questions[1].id, 2)
        self.assertEqual(questions[1].correct, "B")

    def test_04_session_update_and_replace(self):
        """Verify updating multiple questions and replacing a single question in session."""
        q1 = _StoredQuestion(
            id=1,
            question="السؤال الأول الأصلي",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            correct="A",
            explanation="شرح 1",
            reference_quote="اقتباس 1",
        )
        q2 = _StoredQuestion(
            id=2,
            question="السؤال الثاني الأصلي",
            options={"A": "10", "B": "20", "C": "30", "D": "40"},
            correct="B",
            explanation="شرح 2",
            reference_quote="اقتباس 2",
        )

        sid = create_session(file_id=101, questions=[q1, q2])
        session = get_session(sid)
        self.assertIsNotNone(session)
        self.assertEqual(len(session.questions), 2)

        # Replace single question
        new_q2 = _StoredQuestion(
            id=2,
            question="السؤال الثاني المُعدل أو المُعاد توليده",
            options={"A": "A+", "B": "B+", "C": "C+", "D": "D+"},
            correct="C",
            explanation="شرح جديد",
            reference_quote="اقتباس جديد",
        )
        replaced = replace_session_question(sid, 2, new_q2)
        self.assertTrue(replaced)

        fetched_q2 = get_question(sid, 2)
        self.assertEqual(fetched_q2.question, "السؤال الثاني المُعدل أو المُعاد توليده")
        self.assertEqual(fetched_q2.correct, "C")
        self.assertEqual(fetched_q2.reference_quote, "اقتباس جديد")

        # Update all questions
        updated = update_session_questions(sid, [new_q2])
        self.assertTrue(updated)
        self.assertEqual(len(get_session(sid).questions), 1)

    @patch("app.services.quiz_service.generator._make_client")
    @patch("app.services.quiz_service.generator.quiz_cache")
    async def test_05_generate_quiz_function_calling_flow(self, mock_cache, mock_make_client):
        """Verify generate_quiz invokes Gemini with function calling tool and returns _StoredQuestions."""
        mock_cache.get.return_value = None

        mock_call = MagicMock()
        mock_call.name = "save_quiz_questions"
        mock_call.args = {
            "questions": [
                {
                    "id": i,
                    "question": f"سؤال تجريبي {i}",
                    "options": {"A": "خيار أ", "B": "خيار ب", "C": "خيار ج", "D": "خيار د"},
                    "correct": "A",
                    "explanation": f"شرح للسؤال {i}",
                    "reference_quote": f"مقتبس من نص المحاضرة للسؤال {i}",
                }
                for i in range(1, 6)
            ]
        }

        mock_response = MagicMock()
        mock_response.function_calls = [mock_call]
        mock_response.text = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_make_client.return_value = mock_client

        sample_lecture = "محتوى تدريبي لمادة أمن الشبكات والاتصالات الرقمية في مدرسة وي بالسويس " * 10

        questions = await generate_quiz(sample_lecture, num_questions=5, difficulty="medium", force_refresh=True)
        self.assertEqual(len(questions), 5)
        self.assertEqual(questions[0].reference_quote, "مقتبس من نص المحاضرة للسؤال 1")


if __name__ == "__main__":
    unittest.main()
