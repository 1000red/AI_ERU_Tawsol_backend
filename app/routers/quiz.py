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
    QuizSubmitRequest,
    QuizSubmitResponse,
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
            detail="Quiz generation is only available for students and teachers.",
        )

    target_file_id = body.file_id or 0
    text_to_process = ""
    material_file: MaterialFile | None = None

    # Support generating directly from text_content
    if body.text_content and len(body.text_content.strip()) >= 50:
        text_to_process = body.text_content.strip()
    elif body.file_id:
        # ── Load the file ──────────────────────────────────────────────────────
        material_file = (
            db.query(MaterialFile)
            .filter(MaterialFile.file_id == body.file_id)
            .first()
        )

        if not material_file:
            raise HTTPException(status_code=404, detail="File not found.")

        # ── If caller is a student, must be enrolled in that course ───────────
        if caller.type_code == "STU":
            if not material_file.material_id:
                raise HTTPException(
                    status_code=422,
                    detail="This file is not associated with any course.",
                )
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

        if not material_file.file_path:
            raise HTTPException(
                status_code=422,
                detail="This file has no stored content to generate a quiz from.",
            )

        # ── Extract text & generate ────────────────────────────────────────────
        try:
            text_to_process = extract_text(material_file.file_path)
        except HTTPException:
            raise
        except Exception as exc:
            # Fallback to title/description if rich
            if material_file.description and len(material_file.description.strip()) >= 100:
                text_to_process = f"{material_file.title}\n{material_file.description}"
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"An unexpected error occurred while processing the file: {exc}",
                )
    else:
        raise HTTPException(
            status_code=422,
            detail="Either file_id or text_content must be provided.",
        )

    stored_questions = await generate_quiz(text_to_process)

    # ── Create session (server stores correct answers) ─────────────────────
    session_id = create_session(target_file_id, stored_questions)

    # ── Log quiz generation in DB for Admin Monitoring & Gemini Accounting ─
    try:
        from app.models.quiz_log import QuizLog
        import json
        q_data = [
            {
                "id": q.id,
                "question": q.question,
                "options": q.options,
                "correct": q.correct,
                "explanation": q.explanation
            }
            for q in stored_questions
        ]
        topic_title = getattr(body, "topic", None)
        if not topic_title:
            if material_file and getattr(material_file, "title", None):
                topic_title = material_file.title
            elif target_file_id and target_file_id > 0:
                topic_title = f"محاضرة #{target_file_id}"
            elif body.text_content:
                topic_title = body.text_content[:60].strip() + "..."
            else:
                topic_title = "اختبار ذكي تفاعلي"

        course_val = None
        if material_file and getattr(material_file, "material_id", None):
            course_val = material_file.material_id

        diff_val = getattr(body, "difficulty", None) or "medium"

        log_entry = QuizLog(
            session_id=session_id,
            user_id=caller.user_id if caller else None,
            course_id=course_val,
            file_id=target_file_id if (target_file_id and target_file_id > 0) else None,
            topic=topic_title,
            difficulty=diff_val,
            num_questions=len(stored_questions),
            questions_json=json.dumps(q_data, ensure_ascii=False),
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Failed to log quiz in DB: {e}")
        db.rollback()

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
        file_id=target_file_id,
        questions=public_questions,
    )


@router.post("/evaluate", response_model=QuizEvaluateResponse)
def evaluate_answer(
    body: QuizEvaluateRequest,
    db: Session = Depends(get_db),
):
    question = get_question(body.session_id, body.question_id)
    if question is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz session not found or has expired. Please generate a new quiz.",
        )

    is_correct = (body.selected.strip().upper() == question.correct) if (body.selected and body.selected.strip()) else False

    # Increment attempt count on QuizLog
    try:
        from app.models.quiz_log import QuizLog
        log_entry = db.query(QuizLog).filter(QuizLog.session_id == body.session_id).first()
        if log_entry:
            log_entry.attempts_count = (log_entry.attempts_count or 0) + 1
            db.commit()
    except Exception:
        db.rollback()

    return QuizEvaluateResponse(
        correct=is_correct,
        correct_answer=question.correct,
        explanation=question.explanation,
    )


@router.post("/submit", response_model=QuizSubmitResponse)
def submit_quiz_endpoint(
    body: QuizSubmitRequest,
    db: Session = Depends(get_db),
):
    """
    Submits student answers for a complete quiz session, grades the answers,
    updates quiz log score & attempts, and logs the attempt into quiz_student_attempts.
    """
    import json
    from app.models.quiz_log import QuizLog, QuizStudentAttempt
    from app.services.quiz_service.session import _store

    questions_list = []
    session = _store.get(body.session_id)
    if session and not session.is_expired():
        for q in session.questions:
            questions_list.append({
                "id": q.id,
                "question": q.question,
                "options": q.options,
                "correct": q.correct,
                "explanation": q.explanation,
            })

    quiz_log = db.query(QuizLog).filter(QuizLog.session_id == body.session_id).first()
    if not questions_list and quiz_log and quiz_log.questions_json:
        try:
            questions_list = json.loads(quiz_log.questions_json)
        except Exception:
            pass

    if not questions_list:
        raise HTTPException(
            status_code=404,
            detail="Quiz session not found or has expired. Please generate a new quiz.",
        )

    total_questions = len(questions_list)
    correct_count = 0
    details = []

    for q in questions_list:
        q_id = str(q.get("id"))
        selected_opt = body.answers.get(q_id)
        if selected_opt is None and q_id.isdigit():
            selected_opt = body.answers.get(int(q_id))
        selected_clean = (str(selected_opt).strip().upper()) if selected_opt else ""
        correct_opt = str(q.get("correct", "")).strip().upper()
        is_correct = (selected_clean == correct_opt) if selected_clean else False
        if is_correct:
            correct_count += 1
        details.append({
            "id": int(q_id) if q_id.isdigit() else q_id,
            "question": q.get("question"),
            "selected": selected_clean,
            "correct_answer": correct_opt,
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
        })

    score_pct = round((correct_count / total_questions) * 100.0, 1) if total_questions > 0 else 0.0
    passed = score_pct >= 50.0

    # Record or update in DB
    try:
        if quiz_log:
            quiz_log.score = score_pct
            quiz_log.attempts_count = (quiz_log.attempts_count or 0) + 1
            if body.student_id and not quiz_log.user_id:
                quiz_log.user_id = body.student_id

        # Save student attempt
        if body.student_id:
            attempt = QuizStudentAttempt(
                session_id=body.session_id,
                quiz_log_id=quiz_log.id if quiz_log else None,
                student_id=body.student_id,
                score=score_pct,
                total_questions=total_questions,
                correct_count=correct_count,
                answers_json=json.dumps(body.answers, ensure_ascii=False),
            )
            db.add(attempt)
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Error persisting quiz submit: {e}")
        db.rollback()

    return QuizSubmitResponse(
        session_id=body.session_id,
        total_questions=total_questions,
        correct_count=correct_count,
        score_percentage=score_pct,
        passed=passed,
        details=details,
    )



@router.get("/session/{session_id}/all-answers")
def get_all_session_answers(session_id: str):
    """Retrieve all answers and explanations for a session (revealed when clicked)."""
    from app.services.quiz_service.session import _sessions
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found or expired.")
    return {
        str(q_id): {
            "correct_answer": q.correct,
            "explanation": q.explanation
        }
        for q_id, q in session.questions.items()
    }
