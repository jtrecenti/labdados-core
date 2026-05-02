"""Engine OCR baseado em PaddleOCR 3.x.

Mais preciso em layouts complexos (tabelas, colunas, scans ruidosos);
em GPU é significativamente mais rápido. Extra: ``labdados-core[ocr-gpu]``.

PaddleOCR 3.x tem APIs diferentes da 2.x — usamos ``predict(input=...)``.
``rec_texts`` é extraído defensivamente (a estrutura do retorno mudou
entre versões patch).

Mantém um cache singleton da instância indexado pelo ``lang`` — recriar
o detector/recognizer a cada chamada quase dobra o tempo do primeiro PDF.
"""

from __future__ import annotations

from typing import Any

from labdados_core.ocr.exceptions import EngineUnavailable

_PADDLE_INSTANCE: Any = None
_PADDLE_LANG: str = ""


def extract(
    pdf_bytes: bytes,
    *,
    languages: str = "por+eng",
    dpi: int = 200,
    deskew: bool = False,  # noqa: ARG001 — paddleocr aplica internamente
    bw_fallback: bool = False,  # noqa: ARG001 — sem efeito aqui
    use_gpu: bool = False,
) -> list[str]:
    fitz, np = _import_deps()

    paddle = _get_paddle(_paddle_lang(languages), use_gpu=use_gpu)
    pages: list[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc:
            embedded = page.get_text("text").strip()
            if embedded:
                pages.append(embedded)
                continue
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            result = paddle.predict(input=img)
            pages.append("\n".join(_extract_texts(result)))
    finally:
        doc.close()
    return pages


def _paddle_lang(languages: str) -> str:
    """Mapeia o formato Tesseract (``por+eng``) para o PaddleOCR (``pt``)."""
    if "por" in languages:
        return "pt"
    if "eng" in languages:
        return "en"
    return "en"


def _get_paddle(lang: str, *, use_gpu: bool) -> Any:
    global _PADDLE_INSTANCE, _PADDLE_LANG
    if _PADDLE_INSTANCE is not None and _PADDLE_LANG == lang:
        return _PADDLE_INSTANCE

    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise EngineUnavailable(
            "Engine paddleocr requer extras opcionais.\n"
            "    pip install 'labdados-core[ocr-gpu]'"
        ) from exc

    kwargs: dict[str, Any] = {
        "lang": lang,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": True,
    }
    if use_gpu:
        kwargs["device"] = "gpu"

    try:
        _PADDLE_INSTANCE = PaddleOCR(**kwargs)
    except (TypeError, ValueError):
        # Fallback: alguns idiomas (português) podem não estar no build
        # corrente do PaddleOCR — caímos para inglês para não derrubar
        # o pipeline inteiro.
        kwargs["lang"] = "en"
        _PADDLE_INSTANCE = PaddleOCR(**kwargs)
    _PADDLE_LANG = lang
    return _PADDLE_INSTANCE


def _extract_texts(result: Any) -> list[str]:
    """Extrai ``rec_texts`` de cada item do retorno (3.x)."""
    lines: list[str] = []
    if not result:
        return lines
    for res in result:
        texts: Any = None
        if isinstance(res, dict):
            texts = res.get("rec_texts")
        else:
            texts = getattr(res, "rec_texts", None)
            if texts is None and hasattr(res, "get"):
                texts = res.get("rec_texts")
        if texts:
            lines.extend(t for t in texts if t)
    return lines


def _import_deps():
    try:
        import fitz  # PyMuPDF
        import numpy as np
    except ImportError as exc:
        raise EngineUnavailable(
            "Engine paddleocr requer pymupdf + numpy.\n"
            "    pip install 'labdados-core[ocr-gpu]'"
        ) from exc
    return fitz, np
