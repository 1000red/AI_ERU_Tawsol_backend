from pydantic import BaseModel

class QuizGenerateRequest(BaseModel):
    file_id: int


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
    file_id: int
    questions: list[QuizQuestion]


class QuizEvaluateRequest(BaseModel):
    session_id: str
    question_id: int
    selected: str  # "A" | "B" | "C" | "D"


class QuizEvaluateResponse(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str
