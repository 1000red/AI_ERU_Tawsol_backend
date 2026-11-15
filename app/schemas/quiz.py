from pydantic import BaseModel
from typing import Optional

class QuizGenerateRequest(BaseModel):
    file_id: Optional[int] = None
    text_content: Optional[str] = None
    topic: Optional[str] = None


class QuizOption(BaseModel):
    A: str
    B: str
    C: str
    D: str


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: QuizOption # "A" | "B" | "C" | "D"


class QuizGenerateResponse(BaseModel):
    session_id: str
    file_id: Optional[int] = None
    questions: list[QuizQuestion]


class QuizEvaluateRequest(BaseModel):
    session_id: str
    question_id: int
    selected: Optional[str] = None  # "A" | "B" | "C" | "D" or empty for reveal


class QuizEvaluateResponse(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str
