"""Engine OCR baseado em PyMuPDF (renderização) + Tesseract (reconhecimento).

CPU-only, leve. Extra opcional: ``labdados-core[ocr-cpu]``.

Estratégia (consolidada do SDK e do service):

1. Para cada página, tenta o texto nativo do PDF (``page.get_text("text")``)
   — se houver texto embutido, evita o OCR.
2. Caso contrário, renderiza a página em ``dpi`` desejado via ``get_pixmap``,
   aplica ``deskew`` opcional e roda Tesseract.
3. Se o resultado vier vazio (e ``bw_fallback`` ligado), converte pra
   preto-e-branco binário e tenta de novo — costuma resgatar scans de
   baixo contraste.

Dispara :class:`labdados_core.ocr.exceptions.EngineUnavailable` se faltar
``pymupdf``/``pytesseract``/``Pillow``, e
:class:`labdados_core.ocr.exceptions.TesseractNotFound` se o binário
``tesseract`` não estiver no PATH.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from labdados_core.ocr.exceptions import EngineUnavailable, TesseractNotFound


def extract(
    pdf_bytes: bytes,
    *,
    languages: str = "por+eng",
    dpi: int = 200,
    deskew: bool = False,
    bw_fallback: bool = True,
) -> list[str]:
    """Extrai texto de cada página de um PDF — uma string por página."""
    fitz, pytesseract, Image = _import_deps()
    from labdados_core.ocr._tesseract import (
        configure_tesseract_command,
        tesseract_not_found_message,
    )

    configure_tesseract_command(pytesseract)

    pages: list[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc:
            embedded = page.get_text("text")
            if embedded and embedded.strip():
                pages.append(embedded)
                continue

            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = Image.open(BytesIO(pix.tobytes("png")))
            if deskew:
                img = _deskew(img)
            try:
                text = pytesseract.image_to_string(img, lang=languages)
            except pytesseract.TesseractNotFoundError as exc:
                raise TesseractNotFound(tesseract_not_found_message()) from exc

            if not text.strip() and bw_fallback:
                text = _retry_bw(img, languages, pytesseract)

            pages.append(text)
    finally:
        doc.close()
    return pages


def _import_deps():
    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise EngineUnavailable(
            "Engine pymupdf-tesseract requer extras opcionais.\n"
            "    pip install 'labdados-core[ocr-cpu]'\n"
            "Em seguida, instale o binário do Tesseract no seu sistema "
            "(https://tesseract-ocr.github.io)."
        ) from exc
    return fitz, pytesseract, Image


def _deskew(img: Any) -> Any:
    """Deskew leve via PIL — corrige só rotação por EXIF, sem opencv."""
    try:
        from PIL import ImageOps

        return ImageOps.exif_transpose(img)
    except Exception:  # noqa: BLE001
        return img


def _retry_bw(img: Any, languages: str, pytesseract: Any) -> str:
    """Re-OCR com binarização — resgata scans de baixo contraste."""
    from PIL import ImageOps

    gray = ImageOps.grayscale(img)
    bw = gray.point(lambda x: 0 if x < 140 else 255, "1")
    return pytesseract.image_to_string(bw, lang=languages)
