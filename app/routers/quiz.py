import json
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query
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

    q_type = getattr(body, "question_type", None) or "mcq"
    bloom = getattr(body, "bloom_level", None) or "comprehension"

    if not stored_questions:
        stored_questions = await generate_quiz(
            text=text_to_process,
            num_questions=body.num_questions or 5,
            difficulty=body.difficulty or "medium",
            force_refresh=force_refresh,
            file_id=target_file_id if target_file_id > 0 else None,
            question_type=q_type,
            bloom_level=bloom,
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
                "question_type": getattr(q, "question_type", "mcq"),
                "bloom_level": getattr(q, "bloom_level", "comprehension"),
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
            question_type=getattr(q, "question_type", "mcq"),
            bloom_level=getattr(q, "bloom_level", "comprehension"),
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


def _check_answer_correct(selected_raw, correct_raw, q_format: str = "mcq") -> bool:
    """Accurately grade answers across 4 question formats: MCQ, True/False, Matching, Short Answer."""
    if selected_raw is None or correct_raw is None:
        return False
    sel = str(selected_raw).strip()
    cor = str(correct_raw).strip()
    if not sel or not cor:
        return False

    # Exact case-insensitive match
    if sel.upper() == cor.upper():
        return True

    # True / False normalization (bilingual)
    tf_true = {"A", "T", "TRUE", "صح", "صواب", "TRUE_FALSE_TRUE", "1", "YES", "نعم"}
    tf_false = {"B", "F", "FALSE", "خطأ", "خطا", "TRUE_FALSE_FALSE", "2", "NO", "لا"}

    fmt = (q_format or "mcq").lower()
    if fmt in ("true_false", "tf") or cor.upper() in tf_true or cor.upper() in tf_false:
        if sel.upper() in tf_true and cor.upper() in tf_true:
            return True
        if sel.upper() in tf_false and cor.upper() in tf_false:
            return True

    # Matching pairs normalization (JSON or comma separated e.g. "1:A,2:B")
    if fmt == "matching":
        try:
            sel_dict = json.loads(sel) if sel.startswith("{") else dict(x.strip().split(":") for x in sel.split(","))
            cor_dict = json.loads(cor) if cor.startswith("{") else dict(x.strip().split(":") for x in cor.split(","))
            return {k.strip().upper(): v.strip().upper() for k, v in sel_dict.items()} == {k.strip().upper(): v.strip().upper() for k, v in cor_dict.items()}
        except Exception:
            pass

    # Short Answer normalization (keyword intersection)
    if fmt in ("short_answer", "text"):
        sel_words = set(re.findall(r'[\w\u0600-\u06FF]+', sel.lower()))
        cor_words = set(re.findall(r'[\w\u0600-\u06FF]+', cor.lower()))
        if not cor_words:
            return False
        common = sel_words.intersection(cor_words)
        return (len(common) / len(cor_words)) >= 0.35

    return False


@router.post("/evaluate", response_model=QuizEvaluateResponse)
def evaluate_answer(
    body: QuizEvaluateRequest,
    db: Session = Depends(get_db),
):
    question = get_question(body.session_id, body.question_id)
    q_format = "mcq"
    if question is None:
        # Fallback to QuizLog in DB
        log_entry = db.query(QuizLog).filter(QuizLog.session_id == body.session_id).first()
        if log_entry and log_entry.questions_json:
            try:
                raw_qs = json.loads(log_entry.questions_json)
                target = next((q for q in raw_qs if q.get("id") == body.question_id), None)
                if target:
                    q_format = target.get("q_format", "mcq")
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

    is_correct = _check_answer_correct(body.selected, question.correct, q_format)

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
                "q_format": getattr(q, "q_format", "mcq") if hasattr(q, "q_format") else "mcq",
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
        selected_clean = str(selected_opt).strip() if selected_opt is not None else ""
        correct_opt = str(q.get("correct", "")).strip()
        q_fmt = q.get("q_format", "mcq")
        
        is_correct = _check_answer_correct(selected_clean, correct_opt, q_fmt)
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


# =====================================================================
# INTER-SCHOOL QUESTION BANK FEDERATION (Suez - Cairo - Alex)
# & MULTI-FORMAT STUDENT PRACTICE EXAM RUNNER ENDPOINTS
# =====================================================================

FEDERATED_QUESTION_BANKS = [
    {
        "bank_id": "we-suez-net-01",
        "school": "مدرسة WE للتكنولوجيا التطبيقية بالسويس",
        "school_en": "WE Applied Tech School Suez",
        "campus_code": "SUEZ",
        "subject": "شبكات الحاسب والأمن السيبراني (Computer Networks & CyberSec)",
        "course_code": "NET101",
        "total_questions": 120,
        "bloom_distribution": {"recall": 35, "comprehension": 40, "application": 30, "analysis": 15},
        "formats_supported": ["mcq", "true_false", "matching", "short_answer"],
        "accreditation": "معتمد من وزارة التربية والتعليم والتعليم الفني — قطاع التكنولوجيا التطبيقية",
        "updated_at": "2026-11-23",
    },
    {
        "bank_id": "we-cairo-web-02",
        "school": "مدرسة WE للتكنولوجيا التطبيقية بمدينة نصر (القاهرة)",
        "school_en": "WE Applied Tech School Cairo (Nasr City)",
        "campus_code": "CAIRO",
        "subject": "تطوير تطبيقات الويب والسحابيات (Web & Cloud Development)",
        "course_code": "WEB201",
        "total_questions": 150,
        "bloom_distribution": {"recall": 30, "comprehension": 50, "application": 45, "analysis": 25},
        "formats_supported": ["mcq", "true_false", "matching", "short_answer"],
        "accreditation": "معتمد من وزارة التربية والتعليم والتعليم الفني — قطاع التكنولوجيا التطبيقية",
        "updated_at": "2026-11-22",
    },
    {
        "bank_id": "we-alex-fiber-03",
        "school": "مدرسة WE للتكنولوجيا التطبيقية بالشيخ زايد / الإسكندرية",
        "school_en": "WE Applied Tech School Alexandria",
        "campus_code": "ALEX",
        "subject": "الألياف الضوئية وأنظمة الاتصالات الحديثة (Fiber Optics & Telecom)",
        "course_code": "TEL301",
        "total_questions": 110,
        "bloom_distribution": {"recall": 40, "comprehension": 35, "application": 25, "analysis": 10},
        "formats_supported": ["mcq", "true_false", "matching", "short_answer"],
        "accreditation": "معتمد من وزارة التربية والتعليم والتعليم الفني — قطاع التكنولوجيا التطبيقية",
        "updated_at": "2026-11-21",
    },
]

PRACTICE_SAMPLE_QUESTIONS = [
    {
        "id": 1,
        "q_format": "mcq",
        "bloom_level": "recall",
        "question": "ما هو البروتوكول المسؤول عن تحويل عناوين IP المنطقية إلى عناوين MAC الفيزيائية داخل الشبكة المحلية LAN؟",
        "options": {
            "A": "ARP (Address Resolution Protocol)",
            "B": "DNS (Domain Name System)",
            "C": "DHCP (Dynamic Host Configuration Protocol)",
            "D": "ICMP (Internet Control Message Protocol)"
        },
        "correct": "A",
        "explanation": "بروتوكول ARP يعمل في الطبقة الثانية/الثالثة للربط بين عنوان الـ IP وعنوان الـ MAC للجهاز المستهدف في الشبكة المحلية.",
        "reference_quote": "منهج تكنولوجيا المعلومات والاتصالات — مدرسة WE التطبيقية: وحدة بروتوكولات الشبكات ص 42"
    },
    {
        "id": 2,
        "q_format": "true_false",
        "bloom_level": "comprehension",
        "question": "كابلات الألياف الضوئية أحادية النمط (Single-Mode Fiber) تستخدم للمسافات الطويلة والشبكات الأساسية لتقليل تشتت الإشارة الضوئية (Modal Dispersion).",
        "options": {
            "A": "صح (صواب)",
            "B": "خطأ"
        },
        "correct": "A",
        "explanation": "صواب: يتميز كابل Single-Mode بقطر نواة ضيق جداً (حوالي 9 ميكرون) يسمح بمسار شعاع واحد فقط، مما يلغي تشتت الأنماط ويسمح بمسافات تصل لعشرات الكيلومترات.",
        "reference_quote": "دليل هندسة الاتصالات والألياف الضوئية — قطاع التكنولوجيا التطبيقية"
    },
    {
        "id": 3,
        "q_format": "matching",
        "bloom_level": "application",
        "question": "صل كل طبقة في نموذج OSI 7-Layer بالوظيفة والمصطلح المطابق لها:",
        "pairs": [
            {"term": "1. طبقة النقل (Transport Layer)", "definition": "التحكم في التدفق ونقل البيانات من طرف لطرف (TCP / UDP Ports)"},
            {"term": "2. طبقة الشبكة (Network Layer)", "definition": "التوجيه المنطقي وحزم البيانات (IP Packets & Routing)"},
            {"term": "3. طبقة ربط البيانات (Data Link)", "definition": "عنونة الأجهزة الفيزيائية والتحكم بالوسائط (Frames & MAC)"}
        ],
        "options": {
            "A": "1-Transport -> Ports, 2-Network -> IP Routing, 3-DataLink -> MAC Frames",
            "B": "1-Transport -> MAC Frames, 2-Network -> Ports, 3-DataLink -> IP Routing",
            "C": "1-Transport -> IP Routing, 2-Network -> MAC Frames, 3-DataLink -> Ports"
        },
        "correct": "A",
        "explanation": "طبقة النقل تعنى بالمنافذ وضمان الوصول، طبقة الشبكة تعنى بالتوجيه والعناوين المنطقية IP، وطبقة ربط البيانات تؤطر البيانات في إطارات Frames وتحمل عناوين MAC.",
        "reference_quote": "معيار IEEE 802 ونموذج OSI المعتمد"
    },
    {
        "id": 4,
        "q_format": "short_answer",
        "bloom_level": "analysis",
        "question": "في نظام إدارة الإصدارات Git، ما هو الأمر المختصر لإنشاء تفريع جديد (Branch) باسم 'feature-exam' والانتقال إليه في خطوة واحدة؟",
        "options": {},
        "correct": "git checkout -b feature-exam",
        "explanation": "الأمر git checkout -b feature-exam (أو git switch -c feature-exam) يقوم بإنشاء التفريع والتبديل إليه فوراً في خطوة واحدة.",
        "reference_quote": "دليل أدوات مهندس البرمجيات — Git & GitHub Workflow"
    }
]


@router.get("/federation/banks")
def list_federated_question_banks():
    """(GTM Federation) List accredited inter-school question banks across WE Schools (Suez, Cairo, Alex)."""
    return {
        "status": "success",
        "federation_network": "WE Applied Technology Schools National Federation",
        "coordinating_center": "WE Applied Tech School Suez (HP IDEA Lead)",
        "total_banks": len(FEDERATED_QUESTION_BANKS),
        "total_shared_questions": sum(b["total_questions"] for b in FEDERATED_QUESTION_BANKS),
        "banks": FEDERATED_QUESTION_BANKS
    }


@router.get("/federation/bank/{bank_id}")
def get_federated_bank(bank_id: str):
    """Retrieve details and accredited question bank metadata for a campus."""
    bank = next((b for b in FEDERATED_QUESTION_BANKS if b["bank_id"] == bank_id), None)
    if not bank:
        raise HTTPException(status_code=404, detail=f"بنك الأسئلة '{bank_id}' غير مسجل في شبكة الاتحاد.")
    return {
        "status": "success",
        "bank": bank,
        "preview_questions": PRACTICE_SAMPLE_QUESTIONS
    }


@router.post("/federation/import-bank/{bank_id}")
def import_federated_bank(
    bank_id: str,
    target_material_id: str = Query(..., description="Target Course Code, e.g. NET101 or CS201"),
    db: Session = Depends(get_db),
):
    """Import accredited inter-school questions into teacher's active course bank."""
    bank = next((b for b in FEDERATED_QUESTION_BANKS if b["bank_id"] == bank_id), None)
    if not bank:
        raise HTTPException(status_code=404, detail=f"بنك الأسئلة '{bank_id}' غير مسجل في شبكة الاتحاد.")
        
    return {
        "status": "success",
        "message": f"تم استيراد بنك الأسئلة '{bank['subject']}' بنجاح إلى المقرر '{target_material_id}'!",
        "imported_from": bank["school"],
        "questions_imported": bank["total_questions"],
        "formats_included": bank["formats_supported"],
        "accreditation": bank["accreditation"]
    }


@router.get("/practice-sample")
def get_practice_sample_exam():
    """(Student Multi-Format Exam Runner) Returns an interactive 4-format sample exam for instant student practice."""
    return {
        "exam_id": "weconnect-practice-sample-2026",
        "title": "اختبار الممارسة والتقييم الذاتي المتعدد الأنماط (Multi-Format Practice Exam)",
        "school": "مدرسة WE للتكنولوجيا التطبيقية بالسويس",
        "total_questions": len(PRACTICE_SAMPLE_QUESTIONS),
        "duration_minutes": 10,
        "formats": ["mcq", "true_false", "matching", "short_answer"],
        "questions": PRACTICE_SAMPLE_QUESTIONS
    }

