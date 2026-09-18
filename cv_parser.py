"""Load CV text from PDF or plain text."""
from __future__ import annotations
from pathlib import Path
from pypdf import PdfReader


def load_cv_text(path: Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return path.read_text(encoding="utf-8", errors="ignore").strip()
