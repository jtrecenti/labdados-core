"""Formatação da saída do OCR.

O pipeline (:func:`labdados_core.ocr.pipeline.extract`) devolve só
``list[str]`` — uma string por página. Aqui ficam as 2 formas comuns de
empacotar essa saída:

- :func:`join_pages` — caminho do SDK (modo local). Devolve string única
  com separador entre páginas, opcionalmente com cabeçalho Markdown.
- :func:`build_pages_zip` — caminho do serviço. Devolve ``bytes`` de
  um ``.zip`` com ``<stem>/pagina_NNNN.<txt|md>``.

Centralizar essas funções aqui evita que SDK e serviço escrevam o mesmo
formato com pequenas diferenças (extensão, padding do número, separador).
"""

from __future__ import annotations

import io
import os
import zipfile
from typing import Literal

OutputFormat = Literal["txt", "md"]


def join_pages(pages: list[str], *, output_format: OutputFormat = "txt") -> str:
    """Junta as páginas de um PDF numa única string.

    No formato ``"md"``, cada página vira ``# Pagina N\\n\\n<texto>``.
    No formato ``"txt"``, separa apenas por linha em branco.
    """
    if output_format == "md":
        return "\n\n".join(
            f"# Pagina {i}\n\n{page}" for i, page in enumerate(pages, start=1)
        )
    return "\n\n".join(pages)


def build_pages_zip(
    files_data: list[tuple[str, list[str]]],
    *,
    output_format: OutputFormat = "txt",
) -> bytes:
    """Empacota ``[(filename, [pagina1, pagina2, ...]), ...]`` num ``.zip``.

    Estrutura: ``<stem>/pagina_NNNN.<txt|md>`` (4 dígitos, suporta até
    9999 páginas por documento — suficiente).
    """
    buf = io.BytesIO()
    ext = ".md" if output_format == "md" else ".txt"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_name, pages in files_data:
            stem = os.path.splitext(os.path.basename(file_name))[0] or "document"
            for i, page_text in enumerate(pages, start=1):
                content = page_text
                if output_format == "md":
                    content = f"# Pagina {i}\n\n{page_text}"
                zf.writestr(f"{stem}/pagina_{i:04d}{ext}", content)
    buf.seek(0)
    return buf.read()
