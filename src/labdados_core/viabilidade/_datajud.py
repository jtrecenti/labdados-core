"""
Contagem de processos no DataJud — wrapper fino sobre
``juscraper.scraper("datajud").contar_processos`` (PR jtrecenti/juscraper#180).

Antes desta versão (labdados-core <= 0.3.0), o módulo tinha um cliente
HTTP próprio que duplicava regras (alias, query DSL, fallback de 504,
auth) já presentes no juscraper. Migrado para reusar tudo via API
pública — o ``juscraper`` é a única fonte da verdade pra DataJud no
ecossistema labdados.

Nota sobre múltiplas classes
----------------------------
``juscraper.contar_processos`` aceita apenas **uma** ``classe: str``
(não lista). Quando o form do escritório passa várias classes, fazemos
N chamadas (uma por classe) e somamos as contagens. É ineficiente mas
correto — se virar gargalo, abrimos PR no juscraper estendendo
``classe`` pra ``str | list[str]``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def count_for_tribunal(
    tribunal_code: str,
    inicio: str | None,
    fim: str | None,
    classes: list[str] | None,
    assuntos: list[str] | None,
) -> dict[str, Any]:
    """Conta processos no DataJud para um tribunal.

    Recorte por data ISO ``YYYY-MM-DD`` (inclusivo). Múltiplas classes
    viram N chamadas e somam.

    Retorna ``{"code", "count", "relation"}`` em caso de sucesso, ou
    ``{"code", "error"}`` em falha (todas as chamadas falharam).
    """
    try:
        import juscraper as jus
    except ImportError:
        return {
            "code": tribunal_code,
            "error": (
                "juscraper não instalado. Instale com: "
                "pip install labdados-core[juscraper]"
            ),
        }

    scraper = jus.scraper("datajud")
    scraper.set_verbose(0)

    # Lista de classes — quando vazia, faz uma chamada sem ``classe``.
    classes_iter: list[str | None] = list(classes) if classes else [None]

    total_count = 0
    relation = "eq"  # sobe pra "gte" se algum tribunal saturou
    last_error: str | None = None
    chamadas_ok = 0

    for classe in classes_iter:
        kwargs: dict[str, Any] = {"tribunal": tribunal_code.upper()}
        if inicio:
            kwargs["data_ajuizamento_inicio"] = inicio
        if fim:
            kwargs["data_ajuizamento_fim"] = fim
        if classe:
            kwargs["classe"] = classe
        if assuntos:
            kwargs["assuntos"] = assuntos

        try:
            df = scraper.contar_processos(**kwargs)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            logger.warning(
                "datajud_contar_failed: %s classe=%s err=%s",
                tribunal_code, classe, last_error,
            )
            continue

        if df.empty:
            last_error = "juscraper devolveu DataFrame vazio"
            continue

        row = df.iloc[0]
        # juscraper.contar_processos devolve {tribunal, alias, count, relation, error}
        # com count/error mutuamente exclusivos.
        row_error = row.get("error")
        if row_error and row.get("count") is None:
            last_error = str(row_error)[:200]
            continue

        count_val = row.get("count")
        if count_val is not None:
            total_count += int(count_val)
            chamadas_ok += 1
            if row.get("relation") == "gte":
                relation = "gte"

    if chamadas_ok == 0:
        return {
            "code": tribunal_code,
            "error": last_error or "todas as chamadas ao juscraper falharam",
        }
    return {
        "code": tribunal_code,
        "count": total_count,
        "relation": relation,
    }
