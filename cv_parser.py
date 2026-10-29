"""Leer un CV sin guardar el archivo subido."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

MAX_TEXT = 50_000
MAX_BYTES = 1_048_576


def load_cv_bytes(content: bytes, suffix: str) -> str:
    if len(content) > MAX_BYTES:
        raise ValueError("El archivo no puede superar 1 MB.")
    suffix = suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        raise ValueError("Subí un archivo PDF o TXT.")
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("El archivo no es un PDF válido.")
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("El PDF tiene contraseña. Usá otro archivo o pegá el texto.")
            if len(reader.pages) > 10:
                raise ValueError("El PDF no puede tener más de 10 páginas.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("No se pudo leer el PDF. Probá pegar el texto del CV.") from exc
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("El archivo de texto tiene que estar en UTF-8.") from exc
        if "\x00" in text:
            raise ValueError("El archivo no parece contener texto.")
    if len(text) > MAX_TEXT:
        raise ValueError("El CV es demasiado largo; el límite es de 50.000 caracteres.")
    return text.strip()


def load_cv_text(path: Path) -> str:
    path = Path(path)
    with path.open("rb") as fh:
        return load_cv_bytes(fh.read(MAX_BYTES + 1), path.suffix)
