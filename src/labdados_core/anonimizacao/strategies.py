"""Estratégias de mascaramento aplicadas após a detecção de spans PII.

A detecção devolve uma lista de :class:`Entidade` (vide
:mod:`labdados_core.anonimizacao.pipeline`); estas funções recebem o
texto original + entidades e produzem o texto anonimizado.

Três estratégias:

- ``"categoria"`` (default): substitui o span pelo rótulo da categoria
  entre colchetes — ``"João Silva"`` → ``"[PESSOA]"``. É a estratégia
  mais legível e não preserva tamanho/formato.
- ``"asteriscos"``: substitui cada caractere por ``*`` — preserva
  o tamanho exato e mantém o layout (útil em CSVs com colunas
  largura-fixa).
- ``"pseudonimo"``: substitui por ``"PESSOA_1"``, ``"EMAIL_2"`` etc.,
  mantendo consistência por (categoria, valor) **dentro do mesmo
  texto**: o segundo aparecimento de "João Silva" vira o mesmo
  ``PESSOA_1``. Útil para preservar referências em análises.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EstrategiaMascaramento = Literal["categoria", "asteriscos", "pseudonimo"]

# Mapa label técnico → rótulo em português (mostrado ao usuário final).
# Cobre as 8 categorias do openai/privacy-filter e as 6 do LeNER-Br
# (pierreguillou/ner-bert-base-cased-pt-lenerbr).
LABEL_PT: dict[str, str] = {
    # privacy-filter
    "account_number": "CONTA",
    "private_address": "ENDERECO",
    "private_email": "EMAIL",
    "private_person": "PESSOA",
    "private_phone": "TELEFONE",
    "private_url": "URL",
    "private_date": "DATA",
    "secret": "SEGREDO",
    # LeNER-Br (já vêm em maiúsculas; explicitar evita depender do fallback)
    "PESSOA": "PESSOA",
    "ORGANIZACAO": "ORGANIZACAO",
    "LOCAL": "LOCAL",
    "TEMPO": "DATA",
    "LEGISLACAO": "LEGISLACAO",
    "JURISPRUDENCIA": "JURISPRUDENCIA",
}


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    label: str
    texto: str


def aplicar_mascaramento(
    texto: str,
    spans: list[_Span] | list,
    *,
    estrategia: EstrategiaMascaramento = "categoria",
) -> str:
    """Substitui cada span pelo seu mascaramento e devolve o texto resultante.

    Os spans podem se sobrepor ou estar fora de ordem; a função ordena
    por ``start`` decrescente e aplica de trás pra frente para preservar
    os offsets originais.
    """
    if not spans:
        return texto

    items = sorted(spans, key=lambda s: s.start, reverse=True)
    out = texto
    surrogate_idx: dict[tuple[str, str], int] = {}
    counters: dict[str, int] = {}

    for span in items:
        replacement = _build_replacement(
            span,
            estrategia=estrategia,
            surrogate_idx=surrogate_idx,
            counters=counters,
        )
        out = out[: span.start] + replacement + out[span.end :]
    return out


def _build_replacement(
    span,
    *,
    estrategia: EstrategiaMascaramento,
    surrogate_idx: dict[tuple[str, str], int],
    counters: dict[str, int],
) -> str:
    label_pt = LABEL_PT.get(span.label, span.label.upper())
    if estrategia == "asteriscos":
        return "*" * max(1, span.end - span.start)
    if estrategia == "pseudonimo":
        key = (span.label, span.texto.lower().strip())
        if key not in surrogate_idx:
            counters[span.label] = counters.get(span.label, 0) + 1
            surrogate_idx[key] = counters[span.label]
        return f"{label_pt}_{surrogate_idx[key]}"
    # categoria (default)
    return f"[{label_pt}]"
