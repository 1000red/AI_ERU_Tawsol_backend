import json
import re
import asyncio
from fastapi import HTTPException

from app.core.config import settings
from app.services.quiz_service.session import _StoredQuestion

_PROMPT = """\
You are a strict educational quiz generator. Your task is to create exactly 10 \
multiple-choice questions from the LECTURE CONTENT below.

STRICT RULES — follow every rule exactly:
1. Use ONLY information found in the lecture content. Do NOT add outside knowledge.
2. Ignore completely: author names, instructor names, course codes, page numbers, \
   headers, footers, watermarks, timestamps, file names, university names.
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


def _make_client():
    from google import genai

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set. Add it to backend/.env and restart.",
        )
    return genai.Client(api_key=api_key)


def _handle_error(exc: Exception) -> None:
    msg = str(exc).lower()

    if "api_key" in msg or "invalid" in msg or "403" in msg or "401" in msg:
        raise HTTPException(
            status_code=401,
            detail="Invalid Gemini API key. Check GEMINI_API_KEY in backend/.env.",
        )
    if "quota" in msg or "429" in msg or "resource_exhausted" in msg:
        raise HTTPException(
            status_code=429,
            detail="Gemini free-tier rate limit reached. Wait a minute and try again.",
        )
    if "deadline" in msg or "timeout" in msg:
        raise HTTPException(
            status_code=504,
            detail="Gemini API timed out. Please try again.",
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


async def generate_quiz(text: str) -> list[_StoredQuestion]:
    if len(text) < 200:
        raise HTTPException(
            status_code=422,
            detail="The file contains too little extractable text to generate a quiz.",
        )

    trimmed = text[:12_000]
    prompt = _PROMPT + trimmed

    from google.genai import types

    client = _make_client()

    loop = asyncio.get_running_loop()

    # Attempt up to 2 times — Gemini occasionally returns empty/blocked responses.
    last_error = HTTPException(
        status_code=502,
        detail="AI returned an empty or blocked response. Please try again.",
    )

    for attempt in range(2):
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                ),
            )
        except HTTPException:
            raise
        except Exception as exc:
            _handle_error(exc)

        try:
            raw = response.text # safety-blocked
        except Exception:
            raw = None

        if raw and raw.strip(): # JSON not none
            try:
                return _parse_questions(raw)
            except HTTPException as parse_err:
                last_error = parse_err
                continue  # retry on parse failure

    raise last_error # or HTTPException(status_code=502, detail="Quiz generation failed.")
