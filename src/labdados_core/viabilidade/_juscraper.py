"""
Wrapper sobre ``juscraper`` para listagens de jurisprudência (cjsg) e
sentenças (cjpg). O import é lazy — o pacote ``juscraper`` só é importado
quando o usuário escolhe esses tipos de listagem (``[juscraper]`` extra).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def count_first_page(method: str, tribunal_code: str, pesquisa: str) -> dict[str, Any]:
    """Conta itens na 1ª página da busca pública do tribunal.

    A maior parte dos tribunais não expõe contagem total na busca pública —
    usamos a 1ª página (geralmente 20–25 itens) como **indicação** de
    viabilidade, marcando ``relation="first_page"``.

    Retorna ``{"code", "count", "relation"}`` ou ``{"code", "error"}``.
    """
    try:
        import juscraper
    except ImportError as exc:
        return {
            "code": tribunal_code,
            "error": (
                "juscraper não está instalado. Instale com: "
                "pip install labdados-core[juscraper]"
            ),
            "_exc": str(exc),
        }
    try:
        scraper = juscraper.scraper(tribunal_code.lower())
        scraper.set_verbose(0)
        df = getattr(scraper, method)(pesquisa=pesquisa, paginas=1)
        return {
            "code": tribunal_code,
            "count": int(len(df)),
            "relation": "first_page",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("juscraper_count_failed: %s/%s: %s", tribunal_code, method, exc)
        return {"code": tribunal_code, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
