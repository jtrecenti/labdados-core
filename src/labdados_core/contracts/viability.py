"""Schemas tipados do formulário e resultado da análise de viabilidade.

Hoje :func:`labdados_core.viabilidade.analyze_form` aceita e retorna
``dict[str, Any]`` cru (o template Jinja consome direto). Estes models
existem para:

- documentar o shape esperado num só lugar (substitui o docstring solto),
- permitir que consumidores (backend, SDK, frontend via TypeScript gen)
  validem inputs antes de chamar ``analyze_form``,
- preparar uma migração futura em que ``analyze_form`` aceite/retorne
  estes objetos diretamente (sem quebrar o template, que continuaria
  recebendo o ``.model_dump()``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    """Veredito automático produzido por ``analyze_form``."""

    viable = "viable"
    caveats = "caveats"
    unviable = "unviable"


class ViabilityForm(BaseModel):
    """Formulário cru do pedido de levantamento.

    Mesmo formato gravado em ``Request.config`` no backend e montado pelo
    SDK. Campos relevantes dependem de ``listagem``:

    - ``datajud``: usa ``filtro_classes_cnj`` e ``filtro_assuntos_cnj``.
    - ``jurisprudencia``/``sentencas``: usa ``filtro_palavras_chave``.

    Os strings de filtro são texto livre — códigos numéricos separados
    por vírgula ou quebras de linha. ``analyze_form`` faz o split.
    """

    listagem: str = ""  # "datajud" | "jurisprudencia" | "sentencas"
    tribunais_selecionados: list[str] = Field(default_factory=list)
    recorte_inicio: str = ""
    recorte_fim: str = ""
    filtro_classes_cnj: str = ""
    filtro_assuntos_cnj: str = ""
    filtro_palavras_chave: str = ""
    descricao_pesquisa: str = ""


class ViabilityResults(BaseModel):
    """Output de :func:`labdados_core.viabilidade.analyze_form`.

    Os campos ``tribunais`` e ``errors`` ficam como ``list[dict]`` porque
    o shape varia entre Datajud (``count``/``relation``) e juscraper
    (``count``/``relation="first_page"`` ou ``error``); colapsar num só
    model engessaria sem ganho real (o template Jinja já trata os dois
    casos).
    """

    listagem: str
    tribunais: list[dict[str, Any]] = Field(default_factory=list)
    total_aproximado: int = 0
    has_unbounded: bool = False
    errors: list[dict[str, str]] = Field(default_factory=list)
    verdict: Verdict
    highlights: list[str] = Field(default_factory=list)
