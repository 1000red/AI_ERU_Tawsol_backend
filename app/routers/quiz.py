import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.models.content.material_file import MaterialFile
from app.models.material import MaterialStudent
from app.models.user import User
from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizEvaluateRequest,
    QuizEvaluateResponse,
    QuizQuestion,
    QuizOption,
)
from app.services.quiz_service import (
    create_session,
    get_question,
    extract_text,
    generate_quiz,
)

router = APIRouter(prefix="/quiz", tags=["Quiz"])

_FILE_TYPES = {"pdf", "ppt", "word"}
_STAFF_TYPES = {"DR", "TA"}


@router.post("/generate", response_model=QuizGenerateResponse)
async def generate_quiz_endpoint(
    body: QuizGenerateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # ── Verify caller has access ──────────────────────────────────────────
    caller: User = db.query(User).filter(User.user_id == user_id).first()

    if not caller:
        raise HTTPException(status_code=404, detail="User not found.")
    if caller.type_code not in ("STU", "DR", "TA", "ADM"):
        raise HTTPException(
            status_code=403,
            detail="Only students, teachers, and admins can generate quizzes.",
        )

    # ── Load the file ──────────────────────────────────────────────────────
    material_file: MaterialFile | None = (
        db.query(MaterialFile)
        .filter(MaterialFile.file_id == body.file_id)
        .first()
    )

    if not material_file:
        raise HTTPException(status_code=404, detail="File not found.")

    # ── File must be uploaded by staff or admin ───────────────────────────
    author: User | None = (
        db.query(User).filter(User.user_id == material_file.author_id).first()
    )

    if author and author.type_code not in ("DR", "TA", "ADM"):
        raise HTTPException(
            status_code=403,
            detail="Quiz generation is only available for official course materials.",
        )

    # ── File must belong to a course ──────────────────────────────────────
    if not material_file.material_id:
        raise HTTPException(
            status_code=422,
            detail="This file is not associated with any course.",
        )

    # ── If caller is a student, must be enrolled in that course ───────────
    if caller.type_code == "STU":
        enrollment = (
            db.query(MaterialStudent)
            .filter(
                MaterialStudent.material_id == material_file.material_id,
                MaterialStudent.user_id == user_id,
            )
            .first()
        )

        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="You are not enrolled in the course this file belongs to.",
            )

    # ── File must be a supported type ─────────────────────────────────────
    if material_file.file_type not in _FILE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Quiz generation is not supported for '{material_file.file_type}' files. "
                   "Supported types: PDF, PPTX, DOCX.",
        )

    if not material_file.file_path:
        raise HTTPException(
            status_code=422,
            detail="This file has no stored content to generate a quiz from.",
        )

    # ── Extract text & generate ────────────────────────────────────────────
    try:
        text = extract_text(material_file.file_path)
        stored_questions = await generate_quiz(text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while processing the file: {exc}",
        )

    # ── Create session (server stores correct answers) ─────────────────────
    session_id = create_session(body.file_id, stored_questions)

    # ── Return questions WITHOUT correct answers ────────────────────────────
    public_questions = [
        QuizQuestion(
            id=q.id,
            question=q.question,
            options=QuizOption(**q.options),
        )
        for q in stored_questions
    ]

    return QuizGenerateResponse(
        session_id=session_id,
        file_id=body.file_id,
        questions=public_questions,
    )


@router.post("/evaluate", response_model=QuizEvaluateResponse)
def evaluate_answer(
    body: QuizEvaluateRequest,
):
    if body.selected.upper() not in {"A", "B", "C", "D"}:
        raise HTTPException(
            status_code=422,
            detail="Selected answer must be A, B, C, or D.",
        )

    question = get_question(body.session_id, body.question_id)
    if question is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz session not found or has expired. Please generate a new quiz.",
        )

    is_correct = body.selected.upper() == question.correct

    return QuizEvaluateResponse(
        correct=is_correct,
        correct_answer=question.correct,
        explanation=question.explanation,
    )
