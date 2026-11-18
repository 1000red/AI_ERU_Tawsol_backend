import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.models.content.material_file import MaterialFile
from app.models.material import MaterialStudent
from app.models.user import User
from app.models.quiz_log import QuizLog, QuizStudentAttempt
from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizEvaluateRequest,
    QuizEvaluateResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizQuestion,
    QuizOption,
    QuizQuestionUpdateItem,
    QuizUpdateQuestionsRequest,
    QuizRegenerateQuestionRequest,
    QuizRegenerateQuestionResponse,
)
from app.services.quiz_service import (
    create_session,
    get_question,
    get_session,
    update_session_questions,
    replace_session_question,
    _StoredQuestion,
    extract_text,
    generate_quiz,
    regenerate_single_question,
)

router = APIRouter(prefix="/quiz", tags=["Quiz"])
logger = logging.getLogger("uvicorn.error")

_STAFF_TYPES = {"DR", "TA", "ADM"}


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
        material_file = (
            db.query(MaterialFile)
            .filter(MaterialFile.file_id == body.file_id)
            .first()
        )

        if not material_file:
            raise HTTPException(status_code=404, detail="File not found.")

        # If caller is a student, must be enrolled in that course
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

        try:
            text_to_process = extract_text(material_file.file_path)
        except HTTPException as exc:
            if (
                exc.status_code in (404, 500)
                and material_file.description
                and len(material_file.description.strip()) >= 50
            ):
                text_to_process = (
                    f"{material_file.title or ''}\n"
                    f"{material_file.description.strip()}\n"
                    f"محتوى المادة الدراسية في مدرسة WE للتكنولوجيا التطبيقية بالسويس."
                )
            else:
                raise
        except Exception as exc:
            if material_file.description and len(material_file.description.strip()) >= 50:
                text_to_process = f"{material_file.title or ''}\n{material_file.description.strip()}"
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

    # ── Token-Saving Check: Reuse existing DB QuizLog if not force_refresh ─
    from_cache = False
    tokens_saved = 0
    stored_questions = None
    force_refresh = bool(getattr(body, "force_refresh", False))

    if target_file_id and target_file_id > 0 and not force_refresh:
        existing_log = (
            db.query(QuizLog)
            .filter(QuizLog.file_id == target_file_id, QuizLog.questions_json.isnot(None))
            .order_by(QuizLog.id.desc())
            .first()
        )
        if existing_log and existing_log.questions_json:
            try:
                raw_qs = json.loads(existing_log.questions_json)
                if isinstance(raw_qs, list) and len(raw_qs) >= 3:
                    stored_questions = [
                        _StoredQuestion(
                            id=q.get("id", idx + 1),
                            question=q.get("question", ""),
                            options=q.get("options", {}),
                            correct=q.get("correct", "A"),
                            explanation=q.get("explanation", ""),
                            reference_quote=q.get("reference_quote", ""),
                        )
                        for idx, q in enumerate(raw_qs)
                    ]
                    from_cache = True
                    tokens_saved = 2300
                    from app.services.quiz_service.cache import quiz_cache
                    quiz_cache.set(stored_questions, file_id=target_file_id)
            except Exception:
                stored_questions = None

    if not stored_questions:
        stored_questions = await generate_quiz(
            text=text_to_process,
            num_questions=body.num_questions or 5,
            difficulty=body.difficulty or "medium",
            force_refresh=force_refresh,
            file_id=target_file_id if target_file_id > 0 else None,
        )

    # ── Create session ────────────────────────────────────────────────────
    session_id = create_session(target_file_id, stored_questions)

    # ── Log quiz generation in DB ─────────────────────────────────────────
    try:
        q_data = [
            {
                "id": q.id,
                "question": q.question,
                "options": q.options,
                "correct": q.correct,
                "explanation": q.explanation,
                "reference_quote": getattr(q, "reference_quote", ""),
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
        logger.error(f"Failed to log quiz in DB: {e}")
        db.rollback()

    # ── Prepare response ──────────────────────────────────────────────────
    is_teacher = caller.type_code in _STAFF_TYPES
    public_questions = [
        QuizQuestion(
            id=q.id,
            question=q.question,
            options=QuizOption(**q.options),
            reference_quote=getattr(q, "reference_quote", "") or "",
            explanation=q.explanation if is_teacher else "",
            correct=q.correct if is_teacher else None,
        )
        for q in stored_questions
    ]

    return QuizGenerateResponse(
        session_id=session_id,
        file_id=target_file_id,
        questions=public_questions,
        from_cache=from_cache,
        tokens_saved=tokens_saved,
    )


@router.post("/evaluate", response_model=QuizEvaluateResponse)
def evaluate_answer(
    body: QuizEvaluateRequest,
    db: Session = Depends(get_db),
):
    question = get_question(body.session_id, body.question_id)
    if question is None:
        # Fallback to QuizLog in DB
        log_entry = db.query(QuizLog).filter(QuizLog.session_id == body.session_id).first()
        if log_entry and log_entry.questions_json:
            try:
                raw_qs = json.loads(log_entry.questions_json)
                target = next((q for q in raw_qs if q.get("id") == body.question_id), None)
                if target:
                    question = _StoredQuestion(
                        id=target.get("id", body.question_id),
                        question=target.get("question", ""),
                        options=target.get("options", {}),
                        correct=target.get("correct", "A"),
                        explanation=target.get("explanation", ""),
                        reference_quote=target.get("reference_quote", ""),
                    )
            except Exception:
                pass

    if question is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz session not found or has expired. Please generate a new quiz.",
        )

    is_correct = (body.selected.strip().upper() == question.correct) if (body.selected and body.selected.strip()) else False

    try:
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
        reference_quote=getattr(question, "reference_quote", "") or "",
    )


@router.post("/submit", response_model=QuizSubmitResponse)
def submit_quiz_endpoint(
    body: QuizSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submits student answers for a complete quiz session and grades them."""
    questions_list = []
    session = get_session(body.session_id)
    if session and not session.is_expired():
        for q in session.questions:
            questions_list.append({
                "id": q.id,
                "question": q.question,
                "options": q.options,
                "correct": q.correct,
                "explanation": q.explanation,
                "reference_quote": getattr(q, "reference_quote", ""),
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
            "reference_quote": q.get("reference_quote", ""),
        })

    score_pct = round((correct_count / total_questions) * 100.0, 1) if total_questions > 0 else 0.0
    passed = score_pct >= 50.0

    try:
        if quiz_log:
            quiz_log.score = score_pct
            quiz_log.attempts_count = (quiz_log.attempts_count or 0) + 1
            if body.student_id and not quiz_log.user_id:
                quiz_log.user_id = body.student_id

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
        logger.error(f"Error persisting quiz submit: {e}")
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
def get_all_session_answers(
    session_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all answers, explanations, and reference quotes for a session."""
    session = get_session(session_id)
    if session and not session.is_expired():
        return {
            str(q.id): {
                "correct_answer": q.correct,
                "explanation": q.explanation,
                "reference_quote": getattr(q, "reference_quote", "") or "",
            }
            for q in session.questions
        }

    quiz_log = db.query(QuizLog).filter(QuizLog.session_id == session_id).first()
    if quiz_log and quiz_log.questions_json:
        try:
            raw_qs = json.loads(quiz_log.questions_json)
            return {
                str(q.get("id")): {
                    "correct_answer": q.get("correct", "A"),
                    "explanation": q.get("explanation", ""),
                    "reference_quote": q.get("reference_quote", "") or "",
                }
                for q in raw_qs
            }
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Quiz session not found or expired.")


@router.put("/session/{session_id}/questions")
def update_quiz_questions(
    session_id: str,
    body: QuizUpdateQuestionsRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Updates the questions of an existing quiz session with teacher inline edits."""
    caller = db.query(User).filter(User.user_id == user_id).first()
    if not caller or caller.type_code not in _STAFF_TYPES:
        raise HTTPException(status_code=403, detail="Only teachers can edit quiz questions.")

    converted_questions = [
        _StoredQuestion(
            id=item.id,
            question=item.question.strip(),
            options={
                "A": item.options.A.strip(),
                "B": item.options.B.strip(),
                "C": item.options.C.strip(),
                "D": item.options.D.strip(),
            },
            correct=item.correct.upper().strip(),
            explanation=item.explanation or "",
            reference_quote=item.reference_quote or "",
        )
        for item in body.questions
    ]

    # Update in-memory session
    update_session_questions(session_id, converted_questions)

    # Update database record
    quiz_log = db.query(QuizLog).filter(QuizLog.session_id == session_id).first()
    if quiz_log:
        try:
            q_data = [
                {
                    "id": q.id,
                    "question": q.question,
                    "options": q.options,
                    "correct": q.correct,
                    "explanation": q.explanation,
                    "reference_quote": q.reference_quote,
                }
                for q in converted_questions
            ]
            quiz_log.num_questions = len(converted_questions)
            quiz_log.questions_json = json.dumps(q_data, ensure_ascii=False)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update QuizLog questions_json: {e}")
            db.rollback()

    return {
        "status": "success",
        "session_id": session_id,
        "questions_count": len(converted_questions),
        "message": "تم حفظ تعديلات الأسئلة بنجاح.",
    }


@router.post("/session/{session_id}/regenerate-question/{question_id}", response_model=QuizRegenerateQuestionResponse)
async def regenerate_single_quiz_question(
    session_id: str,
    question_id: int,
    body: QuizRegenerateQuestionRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Regenerates a single question using Gemini Function Calling without replacing other questions."""
    caller = db.query(User).filter(User.user_id == user_id).first()
    if not caller or caller.type_code not in _STAFF_TYPES:
        raise HTTPException(status_code=403, detail="Only teachers can regenerate quiz questions.")

    session = get_session(session_id)
    quiz_log = db.query(QuizLog).filter(QuizLog.session_id == session_id).first()

    target_file_id = session.file_id if session else (quiz_log.file_id if quiz_log else None)
    text_to_process = ""

    if target_file_id and target_file_id > 0:
        mat_file = db.query(MaterialFile).filter(MaterialFile.file_id == target_file_id).first()
        if mat_file and mat_file.file_path:
            try:
                text_to_process = extract_text(mat_file.file_path)
            except Exception:
                text_to_process = ""

    if not text_to_process and quiz_log:
        if quiz_log.topic:
            text_to_process = f"محتوى دراسي لمادة: {quiz_log.topic}. مفاهيم وتعاريف وتطبيقات تقنية أساسية."

    if not text_to_process or len(text_to_process.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Cannot extract lecture content to regenerate the question.",
        )

    # Collect existing questions to avoid duplication
    existing_qs = []
    if session:
        existing_qs = [q.question for q in session.questions if q.id != question_id]
    elif quiz_log and quiz_log.questions_json:
        try:
            raw_qs = json.loads(quiz_log.questions_json)
            existing_qs = [q.get("question", "") for q in raw_qs if q.get("id") != question_id]
        except Exception:
            pass

    new_q = await regenerate_single_question(
        text=text_to_process,
        question_id=question_id,
        existing_questions=existing_qs,
        difficulty=body.difficulty or "medium",
    )

    # Replace in session
    if session:
        replace_session_question(session_id, question_id, new_q)

    # Update in QuizLog DB
    if quiz_log and quiz_log.questions_json:
        try:
            raw_qs = json.loads(quiz_log.questions_json)
            updated = False
            for idx, q in enumerate(raw_qs):
                if q.get("id") == question_id:
                    raw_qs[idx] = {
                        "id": question_id,
                        "question": new_q.question,
                        "options": new_q.options,
                        "correct": new_q.correct,
                        "explanation": new_q.explanation,
                        "reference_quote": new_q.reference_quote,
                    }
                    updated = True
                    break
            if not updated:
                raw_qs.append({
                    "id": question_id,
                    "question": new_q.question,
                    "options": new_q.options,
                    "correct": new_q.correct,
                    "explanation": new_q.explanation,
                    "reference_quote": new_q.reference_quote,
                })
            quiz_log.questions_json = json.dumps(raw_qs, ensure_ascii=False)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update QuizLog on single question regen: {e}")
            db.rollback()

    return QuizRegenerateQuestionResponse(
        session_id=session_id,
        question=QuizQuestionUpdateItem(
            id=new_q.id,
            question=new_q.question,
            options=QuizOption(**new_q.options),
            correct=new_q.correct,
            explanation=new_q.explanation,
            reference_quote=new_q.reference_quote,
        ),
    )
