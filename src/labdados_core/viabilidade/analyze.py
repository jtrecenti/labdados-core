"""
Orquestrador da análise de viabilidade.

Recebe o ``form`` cru (mesmo formato gravado em ``Request.config`` no
backend e mesmo formato montado pelo SDK), consulta os tribunais
selecionados e devolve um dicionário com:

- contagens por tribunal,
- total aproximado,
- erros parciais,
- veredito automático (``viable`` / ``caveats`` / ``unviable``),
- highlights (lista textual de pontos de atenção).

Esse formato de saída é **estável** — o backend e o SDK ambos esperam
exatamente este shape. Mudanças aqui afetam:

- ``backend/app/services/viability_runner.py`` (consumidor)
- ``labdados/analise_viabilidade.py`` (consumidor)
- ``backend/app/templates/viability_report.qmd`` (consome via Jinja, mas
  o template real fica em ``labdados_core/templates/viability_report.qmd``)
"""

from __future__ import annotations

from typing import Any

from labdados_core.viabilidade._datajud import count_for_tribunal as _datajud_count
from labdados_core.viabilidade._juscraper import count_first_page as _juscraper_count

# Datajud só conta como "viável" até esse volume — acima disso forçamos
# veredito ``caveats`` (recomendação: fatiar a coleta). Mantenho como
# constante pra poder ser ajustado num lugar só.
DATAJUD_VOLUME_THRESHOLD = 50_000


def analyze_form(form: dict[str, Any]) -> dict[str, Any]:
    """Roda a análise de viabilidade de um pedido de levantamento.

    Parameters
    ----------
    form
        Form JSON cru. Chaves esperadas:

        - ``listagem``: ``"datajud"`` | ``"jurisprudencia"`` | ``"sentencas"``
        - ``tribunais_selecionados``: list[str] (ex.: ``["tjsp", "tjrj"]``)
        - ``recorte_inicio``, ``recorte_fim``: ``"YYYY-MM-DD"`` ou string
          vazia. Recorte por data — mapeia para
          ``data_ajuizamento_inicio``/``_fim`` do juscraper (PR #176)
          quando a migração para ``juscraper.contar_processos`` for feita.
        - Datajud-only: ``filtro_classes_cnj``, ``filtro_assuntos_cnj`` (texto
          livre — códigos numéricos, separados por vírgula ou linha).
        - jurisprudencia/sentencas: ``filtro_palavras_chave``.

    Returns
    -------
    dict
        ``{
            "listagem": str,
            "tribunais": list[{"code", "count", "relation"} | {"code", "error"}],
            "total_aproximado": int,
            "has_unbounded": bool,
            "errors": list[{"tribunal", "error"}],
            "verdict": "viable" | "caveats" | "unviable",
            "highlights": list[str],
        }``
    """
    listagem = str(form.get("listagem") or "")
    tribunais = [str(t).lower() for t in (form.get("tribunais_selecionados") or [])]
    inicio = (form.get("recorte_inicio") or None) or None
    fim = (form.get("recorte_fim") or None) or None

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    if listagem == "datajud":
        classes = _split_lines(form.get("filtro_classes_cnj"))
        assuntos = _split_lines(form.get("filtro_assuntos_cnj"))
        for code in tribunais:
            r = _datajud_count(code, inicio, fim, classes, assuntos)
            if "error" in r:
                errors.append({"tribunal": code, "error": r["error"]})
            results.append(r)
    elif listagem in ("jurisprudencia", "sentencas"):
        method = "cjsg" if listagem == "jurisprudencia" else "cjpg"
        pesquisa = str(form.get("filtro_palavras_chave") or "").strip()
        if not pesquisa:
            errors.append(
                {
                    "tribunal": "(geral)",
                    "error": "Filtro de palavras-chave vazio — não foi possível consultar.",
                }
            )
        else:
            for code in tribunais:
                r = _juscraper_count(method, code, pesquisa)
                if "error" in r:
                    errors.append({"tribunal": code, "error": r["error"]})
                results.append(r)
    else:
        errors.append(
            {"tribunal": "(geral)", "error": f"Tipo de listagem desconhecido: {listagem}"}
        )

    total_known = sum(r.get("count", 0) for r in results if isinstance(r.get("count"), int))
    has_unbounded = any(r.get("relation") in ("gte", "first_page") for r in results)

    highlights: list[str] = []
    if errors:
        highlights.append(f"{len(errors)} erro(s) durante a coleta — ver lista no relatório.")
    if listagem == "datajud":
        if total_known > DATAJUD_VOLUME_THRESHOLD:
            highlights.append(
                f"Volume estimado em {total_known:,} processos — recomenda-se fatiar a coleta "
                "(ex.: por classe ou por janela menor de datas)."
            )
        elif total_known > 0:
            highlights.append(
                f"Volume estimado em {total_known:,} processos — gerenciável."
            )
    elif results:
        highlights.append(
            "Cada tribunal listou ao menos a 1ª página — contagem total não disponível "
            "na busca pública. Use o número como indicação de viabilidade, não de volume."
        )

    if not results:
        verdict = "unviable"
    elif errors and len(errors) >= len(results):
        verdict = "unviable"
    elif (listagem == "datajud" and total_known > DATAJUD_VOLUME_THRESHOLD) or errors:
        verdict = "caveats"
    else:
        verdict = "viable"

    return {
        "listagem": listagem,
        "tribunais": results,
        "total_aproximado": total_known,
        "has_unbounded": has_unbounded,
        "errors": errors,
        "verdict": verdict,
        "highlights": highlights,
    }


def _split_lines(raw: Any) -> list[str]:
    """Aceita textão com vírgulas E/OU quebras de linha — devolve lista
    sem espaços e sem entradas vazias."""
    if not raw:
        return []
    return [line.strip() for line in str(raw).replace(",", "\n").splitlines() if line.strip()]
