import re
import logging

logger = logging.getLogger("uvicorn.error")

# Noise patterns to remove from raw lecture texts (saves tokens)
_NOISE_PATTERNS = [
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(all rights reserved|copyright|confidential|do not distribute).*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*https?://\S+\s*$", re.MULTILINE),
    re.compile(r"^\s*downloaded\s+from\s+.*$", re.IGNORECASE | re.MULTILINE),
]


def clean_and_compress_text(text: str, max_chars: int = 3800) -> str:
    """Pre-processes and compresses lecture text to dramatically minimize Gemini token consumption.
    
    1. Removes carriage returns, excessive blank lines, and whitespace clutter.
    2. Strips boilerplate disclaimers, page numbers, and URLs.
    3. Eliminates duplicate consecutive lines.
    4. Limits input to high-density content (~800-950 tokens) instead of 12,000 chars (~3,500 tokens).
    
    Returns high-density cleaned text ready for the quiz prompt.
    """
    if not text:
        return ""

    # Normalize line endings
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip known boilerplate noise
    for pat in _NOISE_PATTERNS:
        cleaned = pat.sub("", cleaned)

    # Normalize whitespace inside lines
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    # Normalize multiple newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Deduplicate consecutive identical lines
    lines = cleaned.split("\n")
    deduped_lines: list[str] = []
    prev_line = ""
    for line in lines:
        s = line.strip()
        if s and s == prev_line:
            continue
        deduped_lines.append(s)
        if s:
            prev_line = s

    result = "\n".join(deduped_lines).strip()

    # Cap to max_chars for strict token budget
    if len(result) > max_chars:
        # Cut at word or sentence boundary near max_chars
        boundary = result[:max_chars].rfind("\n")
        if boundary < max_chars // 2:
            boundary = result[:max_chars].rfind(" ")
        if boundary > 200:
            result = result[:boundary].strip()
        else:
            result = result[:max_chars].strip()

    return result
