"""Helpers para localizar o binário ``tesseract`` quando ele não está
no PATH — útil principalmente no Windows (instaladores comuns colocam
em ``C:\\Program Files\\Tesseract-OCR\\``).

Originalmente extraído do SDK (``labdados-sdk/src/labdados/ocr.py``).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def configure_tesseract_command(pytesseract_module: Any) -> None:
    """Configura ``pytesseract.pytesseract.tesseract_cmd`` em best-effort.

    Ordem de busca:

    1. Variável de ambiente ``TESSERACT_CMD`` (override explícito).
    2. ``shutil.which("tesseract")`` (PATH).
    3. Locais convencionais por OS (Windows).
    """
    configured_cmd = os.environ.get("TESSERACT_CMD")
    if configured_cmd:
        pytesseract_module.pytesseract.tesseract_cmd = configured_cmd
        return

    discovered_cmd = shutil.which("tesseract")
    if discovered_cmd:
        pytesseract_module.pytesseract.tesseract_cmd = discovered_cmd
        return

    for candidate in _tesseract_candidates():
        if candidate.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(candidate)
            return


def _tesseract_candidates() -> list[Path]:
    candidates: list[Path] = []
    if os.name == "nt":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
            root = os.environ.get(env_name)
            if not root:
                continue
            candidates.append(Path(root) / "Tesseract-OCR" / "tesseract.exe")
            candidates.append(Path(root) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
    return candidates


def tesseract_not_found_message() -> str:
    """Mensagem amigável quando o binário não foi encontrado."""
    message = (
        "OCR local requer o binário do Tesseract instalado e acessível. "
        "Instale-o no sistema (https://tesseract-ocr.github.io) e garanta "
        "que `tesseract` esteja no PATH."
    )
    if os.name == "nt":
        message += (
            " No Windows, o pacote tenta localizar automaticamente em "
            "`C:\\Program Files\\Tesseract-OCR\\tesseract.exe`. "
            "Se estiver em outro lugar, defina a variável de ambiente "
            "`TESSERACT_CMD` com o caminho completo do executável."
        )
    return message
