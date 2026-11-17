import json
import re
import asyncio
from fastapi import HTTPException

from app.core.config import settings
from app.services.quiz_service.session import _StoredQuestion
from app.services.quiz_service.cache import quiz_cache, gemini_limiter
from app.services.quiz_service.compressor import clean_and_compress_text

_PROMPT = """\
You are a strict educational quiz generator. Your task is to create exactly 10 \
multiple-choice questions from the LECTURE CONTENT below.

STRICT RULES — follow every rule exactly:
1. Use ONLY information found in the lecture content. Do NOT add outside knowledge.
2. Ignore completely: author names, teacher names, course codes, page numbers, \
   headers, footers, watermarks, timestamps, file names, school names.
3. Focus on: key concepts, definitions, processes, principles, and learning objectives.
4. Difficulty level: MEDIUM.
5. Generate exactly 10 questions. Each question has exactly 4 options: A, B, C, D.
6. Distribute correct answers across all positions — do NOT always make A or the \
   longest option correct.
7. Distractors (wrong answers) must be plausible and related to the topic — not \
   obviously wrong.
8. Each explanation must reference specific content from the lecture.

Return ONLY valid JSON in this exact format, nothing else:
{
  "questions": [
    {
      "id": 1,
      "question": "...",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct": "A",
      "explanation": "..."
    }
  ]
}

LECTURE CONTENT:
"""


def _build_prompt(text: str, num_questions: int = 10, difficulty: str = "medium") -> str:
    """Build a compact, token-efficient quiz generation prompt."""
    return f"""You are a strict educational quiz generator. Create exactly {num_questions} multiple-choice questions (difficulty: {difficulty.upper()}) from the lecture content below.

STRICT RULES:
1. Use ONLY information from the lecture content. Do NOT add outside knowledge.
2. Ignore author names, dates, course codes, file names, headers, footers, watermarks.
3. Focus on key definitions, core concepts, processes, and learning objectives.
4. Generate exactly {num_questions} questions. Each question has exactly 4 options: A, B, C, D with plausible distractors.
5. Distribute correct answers across A, B, C, D.
6. Keep each explanation concise (1 clear sentence referencing the content).

Return strictly valid JSON with this exact schema:
{{
  "questions": [
    {{
      "id": 1,
      "question": "...",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct": "A",
      "explanation": "..."
    }}
  ]
}}

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


def _parse_questions(raw: str) -> list[_StoredQuestion]:
    # pre-processing data from google
    raw = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini returned malformed JSON: {exc}. Raw: {raw[:300]}",
        )

    questions_raw = data.get("questions", [])
    if len(questions_raw) < 5:
        raise HTTPException(
            status_code=502,
            detail="Gemini generated too few questions. Please try again.",
        )

    questions: list[_StoredQuestion] = []
    for i, q in enumerate(questions_raw[:10], start=1):
        try:
            opts = q["options"]
            questions.append(
                _StoredQuestion(
                    id=i,
                    question=q["question"],
                    options={
                        "A": opts["A"],
                        "B": opts["B"],
                        "C": opts["C"],
                        "D": opts["D"],
                    },
                    correct=q["correct"].upper().strip(),
                    explanation=q.get("explanation", ""),
                )
            )
        except (KeyError, TypeError):
            continue

    if len(questions) < 5:
        raise HTTPException(
            status_code=502,
            detail="Too many malformed questions from Gemini. Please try again.",
        )

    return questions


async def generate_quiz(
    text: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    force_refresh: bool = False,
    file_id: int | None = None,
) -> list[_StoredQuestion]:
    """Generates MCQs with strict token compression, intelligent caching, and free-tier rate protection."""
    if len(text) < 200:
        raise HTTPException(
            status_code=422,
            detail="The file contains too little extractable text to generate a quiz.",
        )

    # ── 1. Check in-memory cache if file_id is provided ────────────────────────
    if file_id and file_id > 0 and not force_refresh and getattr(settings, "GEMINI_CACHE_ENABLED", True):
        cached = quiz_cache.get(file_id=file_id)
        if cached and len(cached) >= 5:
            return cached[:num_questions]

    # ── 2. Compress and clean lecture text to strictly minimize tokens ─────────
    max_chars = getattr(settings, "GEMINI_INPUT_MAX_CHARS", 3800)
    trimmed = clean_and_compress_text(text, max_chars=max_chars)
    if len(trimmed) < 150:
        trimmed = text[:max_chars]

    # ── 3. Build token-efficient prompt ────────────────────────────────────────
    prompt = _build_prompt(trimmed, num_questions=num_questions, difficulty=difficulty)

    from app.services.neon_ai_gateway import neon_ai

    # Try Neon AI Gateway first if configured
    if neon_ai.is_configured:
        try:
            raw = await neon_ai.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gemini-2.5-flash",
            )
            if raw and raw.strip():
                questions = _parse_questions(raw)
                if file_id and file_id > 0 and len(questions) >= 5:
                    quiz_cache.set(questions, file_id=file_id)
                return questions[:num_questions]
        except Exception:
            pass

    from google.genai import types

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
                                response_mime_type="application/json",
                                temperature=0.7,
                                max_output_tokens=1500,
                            ),
                        ),
                    )
                except HTTPException:
                    raise
                except Exception as exc:
                    exc_msg = str(exc).lower()
                    # If model not found on Google endpoint (404), fallback to next model
                    if "not found" in exc_msg or "404" in exc_msg or "is not supported" in exc_msg:
                        break
                    _handle_error(exc)

                try:
                    raw = response.text
                except Exception:
                    raw = None

                if raw and raw.strip():
                    try:
                        questions = _parse_questions(raw)
                        # Cache questions for this file to save 100% of tokens for future students
                        if file_id and file_id > 0 and len(questions) >= 5:
                            quiz_cache.set(questions, file_id=file_id)
                        return questions[:num_questions]
                    except HTTPException as parse_err:
                        last_error = parse_err
                        continue
    finally:
        gemini_limiter.release()

    raise last_error
