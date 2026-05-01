"""
Renderiza o relatório de viabilidade (PDF + Markdown) usando Quarto.

O template (``viability_report.qmd``) é distribuído junto com o pacote em
``labdados_core/templates/`` — leia via ``importlib.resources``. O Jinja2
preenche as variáveis e o Quarto faz o render para Typst (PDF) e GFM
(Markdown). Sem o Quarto no PATH, devolvemos só o markdown (que já é
syntactically válido).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def render_report(
    *,
    request_id: str,
    form: dict[str, Any],
    results: dict[str, Any],
    request_meta: dict[str, Any],
    quarto_timeout: int = 120,
) -> tuple[bytes, bytes] | None:
    """Renderiza o relatório a partir do template embutido.

    Parameters
    ----------
    request_id
        ID da Request (vai pro callout do PDF).
    form, results
        Mesmos dicts que entram/saem de :func:`analyze_form`.
    request_meta
        ``{"researcher_name": str, "institution": str, "email": str,
        "created_at": str | None}`` — usado no cabeçalho do relatório.
    quarto_timeout
        Limite, em segundos, para cada chamada do binário Quarto.

    Returns
    -------
    tuple[bytes, bytes] | None
        ``(pdf_bytes, md_bytes)`` em sucesso. Se o Quarto não estiver
        instalado **mas** o template puder ser preenchido, devolve
        ``(b"", md_bytes)`` — caller decide se grava só o md. Em falha
        completa de jinja2 (extra ``[render]`` ausente), devolve
        ``None``.
    """
    template_text = _load_template()
    if template_text is None:
        return None

    try:
        from jinja2 import Template
    except ImportError:
        logger.warning("jinja2_not_available_for_render")
        return None

    payload = {
        "request_id": request_id,
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "form": form,
        "results": results,
        "request_meta": request_meta,
    }

    rendered_qmd = Template(template_text).render(**payload, json=json)
    md_bytes = rendered_qmd.encode("utf-8")

    if not shutil.which("quarto"):
        logger.warning("quarto_binary_not_found — devolvendo apenas markdown")
        return b"", md_bytes

    pdf_bytes: bytes | None = None
    md_via_quarto: bytes | None = None
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        report_qmd = work / "report.qmd"
        report_qmd.write_text(rendered_qmd, encoding="utf-8")

        try:
            subprocess.run(
                ["quarto", "render", str(report_qmd), "--to", "typst"],
                check=True,
                cwd=str(work),
                capture_output=True,
                timeout=quarto_timeout,
            )
            pdf_path = work / "report.pdf"
            if pdf_path.exists():
                pdf_bytes = pdf_path.read_bytes()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            stderr = getattr(exc, "stderr", b"") or b""
            logger.exception("quarto_pdf_failed: %s", stderr.decode(errors="ignore")[:500])

        try:
            subprocess.run(
                ["quarto", "render", str(report_qmd), "--to", "gfm"],
                check=True,
                cwd=str(work),
                capture_output=True,
                timeout=max(30, quarto_timeout // 2),
            )
            md_path = work / "report.md"
            if md_path.exists():
                md_via_quarto = md_path.read_bytes()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            stderr = getattr(exc, "stderr", b"") or b""
            logger.exception("quarto_md_failed: %s", stderr.decode(errors="ignore")[:500])

    # Se o Quarto não conseguiu gerar md (improvável quando o pdf foi ok),
    # caímos no markdown puro do Jinja — já é GFM válido.
    final_md = md_via_quarto or md_bytes
    if pdf_bytes is None:
        # PDF falhou; devolvemos pdf vazio + md — caller decide.
        return b"", final_md
    return pdf_bytes, final_md


def _load_template() -> str | None:
    """Carrega o template ``.qmd`` embutido. ``None`` se o package não
    foi instalado corretamente."""
    try:
        return (
            resources.files("labdados_core")
            .joinpath("templates", "viability_report.qmd")
            .read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("template_missing_in_package: %s", exc)
        return None
