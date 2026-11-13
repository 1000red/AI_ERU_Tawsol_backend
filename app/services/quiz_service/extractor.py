import os
import re
from fastapi import HTTPException


def _extract_pdf(path: str) -> str:
    import fitz  # PDF

    doc = fitz.open(path)
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        pages.append(text)
    doc.close()

    raw = "\n".join(pages)
    return _clean(raw)


def _extract_pptx(path: str) -> str:
    from pptx import Presentation # powerpoint

    prs = Presentation(path)
    chunks: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = " ".join(run.text for run in para.runs).strip()
                    if line:
                        chunks.append(line)
    return _clean("\n".join(chunks))


def _extract_docx(path: str) -> str:
    from docx import Document # word

    doc = Document(path)
    lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    return _clean("\n".join(lines))


def extract_text(file_path: str) -> str:
    temp_path = None
    try:
        path_to_parse = file_path

        # 1. If it's a remote HTTP/HTTPS URL
        if file_path.startswith("http://") or file_path.startswith("https://"):
            import urllib.request
            import tempfile
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(file_path, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
                content = resp.read()
            ext = os.path.splitext(file_path.split("?")[0])[1].lower() or ".pdf"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                temp_path = tmp.name
            path_to_parse = temp_path

        # 2. If it's not on local disk, try resolving via Neon S3 storage
        elif not os.path.exists(file_path):
            from app.services.neon_storage import neon_storage
            key = file_path.lstrip("/")
            if key.startswith("tmp/"):
                key = key[4:]
            if key.startswith("uploads/"):
                key = key[8:]
            data, _ = neon_storage.get_object(key)
            if data:
                import tempfile
                ext = os.path.splitext(key)[1].lower() or ".pdf"
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(data)
                    temp_path = tmp.name
                path_to_parse = temp_path
            else:
                # Also check relative candidates
                found = False
                for cand in (
                    os.path.join(os.getcwd(), file_path),
                    os.path.join("/tmp", file_path.lstrip("/")),
                    os.path.join("uploads", file_path.lstrip("/")),
                ):
                    if os.path.exists(cand) and os.path.isfile(cand):
                        path_to_parse = cand
                        found = True
                        break
                if not found:
                    raise HTTPException(status_code=404, detail="File not found on server or storage.")

        ext = os.path.splitext(path_to_parse)[1].lower()

        if ext == ".pdf":
            return _extract_pdf(path_to_parse)
        elif ext in (".pptx", ".ppt"):
            return _extract_pptx(path_to_parse)
        elif ext in (".docx", ".doc"):
            return _extract_docx(path_to_parse)
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Quiz generation is not supported for '{ext}' files. "
                       "Please use PDF, PPTX, or DOCX.",
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text from the file: {exc}",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ── Pre-processing ──────────────────────────────────────────────────────────────

_PAGE_NUMBER  = re.compile(r"^\s*\d+\s*$", re.MULTILINE)
_SHORT_LINE   = re.compile(r"^.{1,3}$", re.MULTILINE)
_WHITESPACE   = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    text = _PAGE_NUMBER.sub("", text)
    text = _SHORT_LINE.sub("", text)
    text = _WHITESPACE.sub("\n\n", text)
    return text.strip()
