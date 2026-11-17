from pydantic import BaseModel
from typing import Optional


class QuizGenerateRequest(BaseModel):
    file_id: Optional[int] = None
    text_content: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = "medium"
    num_questions: Optional[int] = 5
    force_refresh: Optional[bool] = False


class QuizOption(BaseModel):
    A: str
    B: str
    C: str
    D: str


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: QuizOption  # "A" | "B" | "C" | "D"
    reference_quote: Optional[str] = ""
    explanation: Optional[str] = ""
    correct: Optional[str] = None


class QuizGenerateResponse(BaseModel):
    session_id: str
    file_id: Optional[int] = None
    questions: list[QuizQuestion]
    from_cache: Optional[bool] = False
    tokens_saved: Optional[int] = 0


class QuizEvaluateRequest(BaseModel):
    session_id: str
    question_id: int
    selected: Optional[str] = None  # "A" | "B" | "C" | "D" or empty for reveal


class QuizEvaluateResponse(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str
    reference_quote: Optional[str] = ""


class QuizSubmitRequest(BaseModel):
    session_id: str
    answers: dict[str, str] = {}  # e.g. {"1": "A", "2": "C"}
    student_id: Optional[int] = None


class QuizSubmitResponse(BaseModel):
    session_id: str
    total_questions: int
    correct_count: int
    score_percentage: float
    passed: bool
    details: list[dict] = []


class QuizQuestionUpdateItem(BaseModel):
    id: int
    question: str
    options: QuizOption
    correct: str  # "A" | "B" | "C" | "D"
    explanation: Optional[str] = ""
    reference_quote: Optional[str] = ""


class QuizUpdateQuestionsRequest(BaseModel):
    session_id: str
    questions: list[QuizQuestionUpdateItem]


class QuizRegenerateQuestionRequest(BaseModel):
    session_id: str
    question_id: int
    difficulty: Optional[str] = "medium"


class QuizRegenerateQuestionResponse(BaseModel):
    session_id: str
    question: QuizQuestionUpdateItem
