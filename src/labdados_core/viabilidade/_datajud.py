"""
Cliente direto pra API pública do Datajud (Elasticsearch do CNJ).

Vive como módulo privado: o público é :func:`labdados_core.viabilidade.analyze_form`,
que orquestra Datajud + juscraper. Mantemos o ``_DATAJUD_KEY`` em código (é a
mesma chave pública usada pelo juscraper, divulgada no portal do CNJ).
"""

from __future__ import annotations

from typing import Any

import httpx

_DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br"
_DATAJUD_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="


def _alias(tribunal_code: str) -> str:
    """``"tjsp"`` → ``"api_publica_tjsp"``."""
    return f"api_publica_{tribunal_code.lower()}"


def _digits(s: Any) -> str:
    return "".join(c for c in str(s) if c.isdigit())


def count_for_tribunal(
    tribunal_code: str,
    inicio: str | None,
    fim: str | None,
    classes: list[str] | None,
    assuntos: list[str] | None,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Conta processos no Datajud para um tribunal.

    Usa ``track_total_hits=True`` e ``size=0`` — só pega o ``hits.total``,
    sem baixar documento nenhum. Datas em ``YYYY-MM-DD``.

    Retorna ``{"code", "count", "relation"}`` em caso de sucesso, ou
    ``{"code", "error"}`` em falha de rede / 4xx / 5xx.
    """
    must: list[dict[str, Any]] = []
    if inicio or fim:
        rng: dict[str, str] = {}
        if inicio:
            rng["gte"] = f"{inicio}T00:00:00.000Z"
        if fim:
            rng["lte"] = f"{fim}T23:59:59.999Z"
        must.append({"range": {"dataAjuizamento": rng}})
    if classes:
        codes = [_digits(c) for c in classes if _digits(c)]
        if codes:
            must.append({"terms": {"classe.codigo": codes}})
    if assuntos:
        codes = [_digits(a) for a in assuntos if _digits(a)]
        if codes:
            must.append({"terms": {"assuntos.codigo": codes}})

    payload: dict[str, Any] = {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"must": must}} if must else {"match_all": {}},
    }
    url = f"{_DATAJUD_BASE}/{_alias(tribunal_code)}/_search"
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"APIKey {_DATAJUD_KEY}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        total = data.get("hits", {}).get("total", {})
        return {
            "code": tribunal_code,
            "count": int(total.get("value") or 0),
            "relation": total.get("relation", "eq"),  # "eq" ou "gte"
        }
    except Exception as exc:  # noqa: BLE001
        return {"code": tribunal_code, "error": str(exc)[:200]}
