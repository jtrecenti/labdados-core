"""Orquestrador do OCR — escolhe o engine e devolve lista de páginas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

# Aliases aceitos como ``modelo``. Ambos apontam pro mesmo engine.
ModeloOCR = Literal["pymupdf-tesseract", "paddleocr"]


def extract(
    pdf: bytes | Path | str,
    *,
    modelo: str = "pymupdf-tesseract",
    languages: str = "por+eng",
    dpi: int = 200,
    deskew: bool = False,
    bw_fallback: bool = True,
    use_gpu: bool = False,
) -> list[str]:
    """Roda OCR num único PDF e devolve uma string por página.

    Parameters
    ----------
    pdf
        Bytes do arquivo PDF, ou caminho (``Path``/``str``) que será lido.
    modelo
        ``"pymupdf-tesseract"`` (default) ou ``"paddleocr"``.
    languages
        Códigos no formato Tesseract (``"por+eng"``, ``"chi_sim+eng"``).
        O engine paddleocr converte internamente para o formato dele.
    dpi
        Resolução da renderização das páginas. 150/200/300 são típicos.
    deskew
        Endireita páginas tortas antes do OCR (apenas pymupdf-tesseract;
        paddle aplica internamente).
    bw_fallback
        Se o resultado do Tesseract vier vazio, re-OCR em preto-e-branco
        binário. Resgata scans de baixo contraste sem perda de qualidade.
    use_gpu
        Apenas paddleocr — ativa CUDA se disponível.

    Returns
    -------
    list[str]
        Uma string por página do PDF (índice 0 = primeira página).
        Páginas sem texto são strings vazias.
    """
    if isinstance(pdf, (str, Path)):
        pdf_bytes = Path(pdf).read_bytes()
    else:
        pdf_bytes = pdf

    if modelo == "pymupdf-tesseract":
        from labdados_core.ocr._engines.pymupdf_tesseract import extract as _extract

        return _extract(
            pdf_bytes,
            languages=languages,
            dpi=dpi,
            deskew=deskew,
            bw_fallback=bw_fallback,
        )
    if modelo == "paddleocr":
        from labdados_core.ocr._engines.paddle import extract as _extract

        return _extract(
            pdf_bytes,
            languages=languages,
            dpi=dpi,
            deskew=deskew,
            bw_fallback=bw_fallback,
            use_gpu=use_gpu,
        )
    raise ValueError(
        f"modelo OCR desconhecido: {modelo!r} (use 'pymupdf-tesseract' ou 'paddleocr')"
    )
