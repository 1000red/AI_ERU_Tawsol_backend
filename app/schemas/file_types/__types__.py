from typing import Literal


CONTENT_TYPE = Literal[
    # ── Message types ─────────────────────────────────────────────────────────
    "text", "image", "voice", "video",
    # ── Documents ─────────────────────────────────────────────────────────────
    "pdf", "word", "ppt",
    # ── Code ──────────────────────────────────────────────────────────────────
    "python", "jupyter",
    "c", "cpp", "java", "javascript", "typescript",
    "html", "css", "sql", "r", "matlab",
    # ── Archives ──────────────────────────────────────────────────────────────
    "zip", "rar", "7z",
    # ── Other ─────────────────────────────────────────────────────────────────
    "link", "file",
]
