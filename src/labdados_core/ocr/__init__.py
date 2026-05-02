"""OCR de PDFs — pipeline compartilhado entre o SDK (modo local) e o
serviço ``services/ocr`` no escritório.

API:

- :func:`extract` — função principal. Recebe ``bytes`` ou ``Path``,
  devolve ``list[str]`` (uma string por página).
- :func:`join_pages` / :func:`build_pages_zip` — utilidades para
  empacotar a saída no formato esperado pelo caller (texto único pro
  SDK, zip por página pro serviço).

Engines (lazy import via extras opcionais):

- ``modelo="pymupdf-tesseract"`` — CPU, leve. Extra: ``ocr-cpu``.
- ``modelo="paddleocr"`` — Mais preciso em layouts complexos.
  Extra: ``ocr-gpu``. Roda em CPU se a GPU não estiver disponível,
  mas vale muito menos a pena.

A escolha entre engines fica no caller; o pipeline faz só o dispatch.
"""

from labdados_core.ocr.exceptions import EngineUnavailable, TesseractNotFound
from labdados_core.ocr.formatters import build_pages_zip, join_pages
from labdados_core.ocr.pipeline import extract

__all__ = [
    "EngineUnavailable",
    "TesseractNotFound",
    "build_pages_zip",
    "extract",
    "join_pages",
]
