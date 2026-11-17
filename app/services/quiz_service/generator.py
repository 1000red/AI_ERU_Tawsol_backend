import json
import re
import asyncio
from fastapi import HTTPException

from app.core.config import settings
from app.services.quiz_service.session import _StoredQuestion
from app.services.quiz_service.cache import quiz_cache, gemini_limiter
from app.services.quiz_service.compressor import clean_and_compress_text


def _build_quiz_tool():
    """Builds the Gemini Function Calling Tool for structured, zero-hallucination quiz generation."""
    from google.genai import types

    func = types.FunctionDeclaration(
        name="save_quiz_questions",
        description="Save multiple-choice questions strictly grounded in the uploaded lecture text with verbatim reference quotes.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "questions": types.Schema(
                    type="ARRAY",
                    items=types.Schema(
                        type="OBJECT",
                        properties={
                            "id": types.Schema(type="INTEGER", description="Sequential question number starting from 1"),
                            "question": types.Schema(type="STRING", description="Question text strictly derived from the text"),
                            "options": types.Schema(
                                type="OBJECT",
                                properties={
                                    "A": types.Schema(type="STRING"),
                                    "B": types.Schema(type="STRING"),
                                    "C": types.Schema(type="STRING"),
                                    "D": types.Schema(type="STRING"),
                                },
                                required=["A", "B", "C", "D"],
                            ),
                            "correct": types.Schema(type="STRING", enum=["A", "B", "C", "D"], description="The single correct option letter"),
                            "explanation": types.Schema(type="STRING", description="Concise pedagogical explanation proving the answer"),
                            "reference_quote": types.Schema(type="STRING", description="Verbatim sentence from the lecture text as evidence"),
                        },
                        required=["id", "question", "options", "correct", "explanation", "reference_quote"],
                    ),
                )
            },
            required=["questions"],
        ),
    )
    return types.Tool(function_declarations=[func])


def _build_single_question_tool():
    """Builds the Gemini Function Calling Tool for single question regeneration."""
    from google.genai import types

    func = types.FunctionDeclaration(
        name="save_single_question",
        description="Save a single newly generated multiple-choice question strictly grounded in lecture text with verbatim quote.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "id": types.Schema(type="INTEGER", description="Question ID to replace"),
                "question": types.Schema(type="STRING", description="Question text strictly derived from the lecture text"),
                "options": types.Schema(
                    type="OBJECT",
                    properties={
                        "A": types.Schema(type="STRING"),
                        "B": types.Schema(type="STRING"),
                        "C": types.Schema(type="STRING"),
                        "D": types.Schema(type="STRING"),
                    },
                    required=["A", "B", "C", "D"],
                ),
                "correct": types.Schema(type="STRING", enum=["A", "B", "C", "D"]),
                "explanation": types.Schema(type="STRING", description="Concise explanation proving the answer"),
                "reference_quote": types.Schema(type="STRING", description="Verbatim sentence from the lecture text as evidence"),
            },
            required=["id", "question", "options", "correct", "explanation", "reference_quote"],
        ),
    )
    return types.Tool(function_declarations=[func])


def _build_grounded_prompt(text: str, num_questions: int = 10, difficulty: str = "medium") -> str:
    """Build a prompt enforcing 100% strict grounding on uploaded lecture text only."""
    return f"""You are a master academic assessment architect for WE Applied Technology School in Suez.
Your mission is to generate exactly {num_questions} high-quality, professional multiple-choice questions (difficulty: {difficulty.upper()}) STRICTLY grounded in the provided lecture content.

STRICT ZERO-HALLUCINATION GROUNDING RULES:
1. Grounding: Every question, correct answer, and explanation must be 100% directly substantiated by the lecture text below. Do NOT use outside knowledge or internet facts not present in this text.
2. Evidence Citation: For EVERY question, you MUST provide a verbatim quote (`reference_quote`) extracted directly from the lecture text that unequivocally proves the correct answer.
3. Content Scope: Focus strictly on key technical concepts, core definitions, architectures, protocols, formulas, or operational procedures described in the text.
4. Ignore: Author names, dates, course codes, file names, headers, footers, watermarks, slide numbers.
5. Distractors: Provide 4 plausible options (A, B, C, D). Distractors must be relevant technical concepts from the same topic, not absurd or obviously false.
6. Distribution: Distribute correct answers evenly across A, B, C, D.
7. Format: You MUST call the `save_quiz_questions` tool with all {num_questions} questions.

LECTURE CONTENT:
{text}
"""


def _build_single_grounded_prompt(text: str, question_id: int, existing_questions: list[str], difficulty: str = "medium") -> str:
    """Build a prompt for regenerating a single question without duplicating existing questions."""
    avoid_list = "\n- ".join(existing_questions[:10]) if existing_questions else "None"
    return f"""You are a master academic assessment architect for WE Applied Technology School in Suez.
Your mission is to generate ONE single replacement multiple-choice question #{question_id} (difficulty: {difficulty.upper()}) STRICTLY grounded in the provided lecture content.

STRICT ZERO-HALLUCINATION GROUNDING RULES:
1. Grounding: Must be 100% substantiated by the lecture text below. No outside facts.
2. Evidence Citation: You MUST provide the verbatim sentence (`reference_quote`) from the lecture text as proof.
3. Avoid Duplication: Do NOT duplicate or closely rephrase any of the existing quiz questions:
- {avoid_list}
4. Options: 4 plausible options (A, B, C, D) with evenly balanced choices.
5. Format: You MUST call the `save_single_question` tool with question #{question_id}.

LECTURE CONTENT:
{text}
"""


def _make_client():
    import ssl
    import traceback
    from google import genai
    from google.genai import types

    api_key = settings.GEMINI_API_KEY
    if not api_key or not str(api_key).strip():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set. Cannot initialize Gemini AI client.",
        )
    api_key = str(api_key).strip()

    try:
        ctx = ssl.create_default_context()
        ctx.load_default_certs()
        http_options = types.HttpOptions(
            api_version="v1beta",
            client_args={"verify": ctx},
            async_client_args={"verify": ctx},
        )
        return genai.Client(api_key=api_key, http_options=http_options)
    except Exception as e:
        tb = traceback.format_exc()
        if (
            "load_default_certs" in tb
            or isinstance(e, (TypeError, AttributeError, PermissionError))
            or "http_options" in tb
            or "Failed with http_options" in str(e)
        ):
            try:
                return genai.Client(api_key=api_key)
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to initialize Gemini AI client: {exc}",
                )
        raise HTTPException(
            status_code=503,
            detail=f"Failed to initialize Gemini AI client: {e}",
        )


def _handle_error(exc: Exception) -> None:
    msg = str(exc).lower()

    if (
        "api_key" in msg
        or "invalid" in msg
        or "403" in msg
        or "401" in msg
        or "unauthorized" in msg
        or "forbidden" in msg
        or "credentials" in msg
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Gemini API key. Check GEMINI_API_KEY in backend/.env.",
        )
    if "quota" in msg or "429" in msg or "resource_exhausted" in msg:
        raise HTTPException(
            status_code=429,
            detail="Gemini free-tier rate limit reached. Wait a minute and try again.",
        )
    if (
        "deadline" in msg
        or "timeout" in msg
        or "timed out" in msg
        or "time out" in msg
    ):
        raise HTTPException(
            status_code=504,
            detail="AI generation timed out.",
        )
    raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}")


def _extract_stored_questions_from_call_args(args: dict) -> list[_StoredQuestion]:
    """Converts function call arguments into a verified list of _StoredQuestion dataclasses."""
    questions_raw = args.get("questions", [])
    if not isinstance(questions_raw, list) or len(questions_raw) == 0:
        return []

    questions: list[_StoredQuestion] = []
    for i, q in enumerate(questions_raw, start=1):
        if not isinstance(q, dict):
            continue
        opts = q.get("options", {})
        if not isinstance(opts, dict):
            continue

        correct = str(q.get("correct", "A")).upper().strip()
        if correct not in ("A", "B", "C", "D"):
            correct = "A"

        q_id = q.get("id")
        try:
            q_id = int(q_id)
        except (ValueError, TypeError):
            q_id = i

        questions.append(
            _StoredQuestion(
                id=q_id,
                question=str(q.get("question", "")).strip(),
                options={
                    "A": str(opts.get("A", "")).strip(),
                    "B": str(opts.get("B", "")).strip(),
                    "C": str(opts.get("C", "")).strip(),
                    "D": str(opts.get("D", "")).strip(),
                },
                correct=correct,
                explanation=str(q.get("explanation", "")).strip(),
                reference_quote=str(q.get("reference_quote", "")).strip(),
            )
        )
    return questions


def _parse_questions_json_fallback(raw: str, min_required: int = 5) -> list[_StoredQuestion]:
    """Fallback JSON parser if Gemini responds with raw JSON text instead of a tool call."""
    raw = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini returned malformed JSON: {exc}. Raw: {raw[:300]}",
        )

    questions_raw = data.get("questions", [])
    if len(questions_raw) < min_required:
        raise HTTPException(
            status_code=502,
            detail="Gemini generated too few questions. Please try again.",
        )

    questions: list[_StoredQuestion] = []
    for i, q in enumerate(questions_raw, start=1):
        try:
            opts = q["options"]
            correct = str(q["correct"]).upper().strip()
            if correct not in ("A", "B", "C", "D"):
                correct = "A"
            questions.append(
                _StoredQuestion(
                    id=int(q.get("id", i)),
                    question=q["question"],
                    options={
                        "A": opts["A"],
                        "B": opts["B"],
                        "C": opts["C"],
                        "D": opts["D"],
                    },
                    correct=correct,
                    explanation=q.get("explanation", ""),
                    reference_quote=q.get("reference_quote", ""),
                )
            )
        except (KeyError, TypeError):
            continue

    if len(questions) < min_required:
        raise HTTPException(
            status_code=502,
            detail="Too many malformed questions from Gemini. Please try again.",
        )

    return questions


_parse_questions = _parse_questions_json_fallback  # Backward compatibility alias


async def generate_quiz(
    text: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    force_refresh: bool = False,
    file_id: int | None = None,
) -> list[_StoredQuestion]:
    """Generates MCQs using Gemini Function Calling, strictly grounded in the uploaded material."""
    if len(text) < 150:
        raise HTTPException(
            status_code=422,
            detail="The file contains too little extractable text to generate a quiz.",
        )

    # ── 1. Check in-memory cache if file_id is provided ────────────────────────
    if file_id and file_id > 0 and not force_refresh and getattr(settings, "GEMINI_CACHE_ENABLED", True):
        cached = quiz_cache.get(file_id=file_id)
        if cached and len(cached) >= 3:
            return cached[:num_questions]

    # ── 2. Compress and clean lecture text to strictly minimize tokens ─────────
    max_chars = getattr(settings, "GEMINI_INPUT_MAX_CHARS", 3800)
    trimmed = clean_and_compress_text(text, max_chars=max_chars)
    if len(trimmed) < 150:
        trimmed = text[:max_chars]

    # ── 3. Build token-efficient strict grounding prompt & tool ────────────────
    prompt = _build_grounded_prompt(trimmed, num_questions=num_questions, difficulty=difficulty)

    from google.genai import types

    quiz_tool = _build_quiz_tool()
    tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.ANY,
            allowed_function_names=["save_quiz_questions"],
        )
    )

    client = _make_client()
    loop = asyncio.get_running_loop()

    # Model resolution: candidate models ordered by priority
    configured_model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash-8b") or "gemini-1.5-flash-8b"
    model_candidates = [configured_model, "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]
    models: list[str] = []
    for m in model_candidates:
        if m and m not in models:
            models.append(m)

    last_error = HTTPException(
        status_code=502,
        detail="AI returned an empty or blocked response. Please try again.",
    )

    # ── 4. Concurrency & Rate Limiter Guard (guarantees <= 12 RPM, max 2 concurrent)
    await gemini_limiter.acquire()
    try:
        for model_name in models:
            for attempt in range(2):
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda m=model_name: client.models.generate_content(
                            model=m,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                tools=[quiz_tool],
                                tool_config=tool_config,
                                temperature=0.2,
                                max_output_tokens=2500,
                            ),
                        ),
                    )
                except HTTPException:
                    raise
                except Exception as exc:
                    exc_msg = str(exc).lower()
                    if "not found" in exc_msg or "404" in exc_msg or "is not supported" in exc_msg:
                        break
                    _handle_error(exc)

                # ── 5. Extract questions from Gemini Function Call ───────────────────
                try:
                    if response and response.function_calls:
                        for call in response.function_calls:
                            if call.name == "save_quiz_questions" and call.args:
                                questions = _extract_stored_questions_from_call_args(call.args)
                                if len(questions) >= 3:
                                    if file_id and file_id > 0:
                                        quiz_cache.set(questions, file_id=file_id)
                                    return questions[:num_questions]
                except Exception as e:
                    pass

                # Fallback: check text response
                try:
                    raw = response.text if response else None
                    if raw and raw.strip():
                        questions = _parse_questions_json_fallback(raw)
                        if file_id and file_id > 0 and len(questions) >= 3:
                            quiz_cache.set(questions, file_id=file_id)
                        return questions[:num_questions]
                except Exception as parse_err:
                    last_error = parse_err
                    continue
    finally:
        gemini_limiter.release()

    raise last_error


async def regenerate_single_question(
    text: str,
    question_id: int,
    existing_questions: list[str],
    difficulty: str = "medium",
) -> _StoredQuestion:
    """Regenerates a single question using Gemini Function Calling, strictly avoiding duplicates."""
    if len(text) < 150:
        raise HTTPException(
            status_code=422,
            detail="The file contains too little extractable text to generate a question.",
        )

    max_chars = getattr(settings, "GEMINI_INPUT_MAX_CHARS", 3800)
    trimmed = clean_and_compress_text(text, max_chars=max_chars)
    if len(trimmed) < 150:
        trimmed = text[:max_chars]

    prompt = _build_single_grounded_prompt(
        trimmed,
        question_id=question_id,
        existing_questions=existing_questions,
        difficulty=difficulty,
    )

    from google.genai import types

    single_tool = _build_single_question_tool()
    tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.ANY,
            allowed_function_names=["save_single_question"],
        )
    )

    client = _make_client()
    loop = asyncio.get_running_loop()

    configured_model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash-8b") or "gemini-1.5-flash-8b"
    model_candidates = [configured_model, "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]
    models: list[str] = [m for m in model_candidates if m]

    await gemini_limiter.acquire()
    try:
        for model_name in models:
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda m=model_name: client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[single_tool],
                            tool_config=tool_config,
                            temperature=0.3,
                            max_output_tokens=1000,
                        ),
                    ),
                )
            except HTTPException:
                raise
            except Exception as exc:
                exc_msg = str(exc).lower()
                if "not found" in exc_msg or "404" in exc_msg or "is not supported" in exc_msg:
                    continue
                _handle_error(exc)

            if response and response.function_calls:
                for call in response.function_calls:
                    if call.name == "save_single_question" and call.args:
                        args = call.args
                        opts = args.get("options", {})
                        correct = str(args.get("correct", "A")).upper().strip()
                        if correct not in ("A", "B", "C", "D"):
                            correct = "A"
                        return _StoredQuestion(
                            id=question_id,
                            question=str(args.get("question", "")).strip(),
                            options={
                                "A": str(opts.get("A", "")).strip(),
                                "B": str(opts.get("B", "")).strip(),
                                "C": str(opts.get("C", "")).strip(),
                                "D": str(opts.get("D", "")).strip(),
                            },
                            correct=correct,
                            explanation=str(args.get("explanation", "")).strip(),
                            reference_quote=str(args.get("reference_quote", "")).strip(),
                        )

            # Fallback JSON parsing
            raw = response.text if response else None
            if raw and raw.strip():
                try:
                    clean = re.sub(r"```(?:json)?", "", raw).strip()
                    data = json.loads(clean)
                    if "questions" in data and isinstance(data["questions"], list) and len(data["questions"]) > 0:
                        data = data["questions"][0]
                    opts = data.get("options", {})
                    correct = str(data.get("correct", "A")).upper().strip()
                    if correct not in ("A", "B", "C", "D"):
                        correct = "A"
                    return _StoredQuestion(
                        id=question_id,
                        question=str(data.get("question", "")).strip(),
                        options={
                            "A": str(opts.get("A", "")).strip(),
                            "B": str(opts.get("B", "")).strip(),
                            "C": str(opts.get("C", "")).strip(),
                            "D": str(opts.get("D", "")).strip(),
                        },
                        correct=correct,
                        explanation=str(data.get("explanation", "")).strip(),
                        reference_quote=str(data.get("reference_quote", "")).strip(),
                    )
                except Exception:
                    pass
    finally:
        gemini_limiter.release()

    raise HTTPException(status_code=502, detail="Failed to regenerate question with Gemini Function Calling.")
