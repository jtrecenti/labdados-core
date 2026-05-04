"""Orquestrador de alto nível: detecta PII e aplica mascaramento.

A função :func:`anonimizar` é o ponto único compartilhado entre o
serviço (``services/anonimizacao/main.py``) e o SDK em modo local
(``labdados/anonimizacao.py``).

Aceita um único texto ou uma lista (com IDs opcionais), e devolve um
:class:`AnonimizacaoResult` por entrada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from labdados_core.anonimizacao._engine import detectar_pii
from labdados_core.anonimizacao.strategies import (
    EstrategiaMascaramento,
    aplicar_mascaramento,
)

DocumentInput = str | tuple[str, str]


@dataclass
class Entidade:
    """Span de PII detectado no texto."""

    start: int
    end: int
    label: str  # categoria técnica: "private_person", "private_email", etc.
    texto: str

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "label": self.label, "texto": self.texto}


@dataclass
class AnonimizacaoResult:
    """Resultado da anonimização de um único texto."""

    doc_id: str
    texto_original: str
    texto_anonimizado: str
    entidades: list[Entidade] = field(default_factory=list)
    erro: str | None = None

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "texto_original": self.texto_original,
            "texto_anonimizado": self.texto_anonimizado,
            "entidades": [e.to_dict() for e in self.entidades],
            "erro": self.erro,
        }


def anonimizar(
    textos: DocumentInput | list[DocumentInput],
    *,
    estrategia: EstrategiaMascaramento = "categoria",
    modelo: str = "openai/privacy-filter",
    use_gpu: bool = False,
    threshold: float = 0.0,
    incluir_texto_original: bool = False,
) -> list[AnonimizacaoResult]:
    """Detecta PII e aplica mascaramento em um ou mais textos.

    Parameters
    ----------
    textos
        ``str``, ``(doc_id, texto)`` ou lista de qualquer um dos dois.
        Quando a entrada é só ``str``, o ``doc_id`` no retorno fica
        ``"doc_<i>"``.
    estrategia
        Como mascarar os spans detectados — ``"categoria"`` (default,
        substitui por ``[PESSOA]``/``[EMAIL]``...), ``"asteriscos"``
        (preserva tamanho), ``"pseudonimo"`` (substitui por
        ``PESSOA_1`` etc., consistente por texto).
    modelo
        Identificador HuggingFace do modelo. Default
        ``"openai/privacy-filter"``.
    use_gpu
        Roda em CUDA quando disponível. Em CPU o modelo funciona mas
        é ~10x mais lento (1.5B params).
    threshold
        Score mínimo (softmax) pra considerar um token como PII.
        ``0.0`` (default) usa argmax — equivalente ao ``pipeline``
        do HF. Subir para ``0.7+`` reduz falsos positivos.
    incluir_texto_original
        Se ``True``, devolve o texto original junto. Por padrão omite
        para reduzir payload (o caller já tem o input).

    Returns
    -------
    list[AnonimizacaoResult]
        Um resultado por entrada de ``textos``.
    """
    items = _normalize(textos)
    results: list[AnonimizacaoResult] = []

    for doc_id, texto in items:
        if not texto.strip():
            results.append(
                AnonimizacaoResult(
                    doc_id=doc_id,
                    texto_original=texto if incluir_texto_original else "",
                    texto_anonimizado=texto,
                    entidades=[],
                )
            )
            continue
        try:
            spans = detectar_pii(
                texto, modelo=modelo, use_gpu=use_gpu, threshold=threshold
            )
            anonimizado = aplicar_mascaramento(texto, spans, estrategia=estrategia)
            results.append(
                AnonimizacaoResult(
                    doc_id=doc_id,
                    texto_original=texto if incluir_texto_original else "",
                    texto_anonimizado=anonimizado,
                    entidades=[
                        Entidade(start=s.start, end=s.end, label=s.label, texto=s.texto)
                        for s in spans
                    ],
                )
            )
        except Exception as exc:  # noqa: BLE001 — erro vira dado, não levanta
            results.append(
                AnonimizacaoResult(
                    doc_id=doc_id,
                    texto_original=texto if incluir_texto_original else "",
                    texto_anonimizado=texto,
                    entidades=[],
                    erro=str(exc),
                )
            )

    return results


def _normalize(value: DocumentInput | list[DocumentInput]) -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [("doc_1", value)]
    if isinstance(value, tuple):
        return [value]
    out: list[tuple[str, str]] = []
    for i, item in enumerate(value, start=1):
        if isinstance(item, str):
            out.append((f"doc_{i}", item))
        else:
            out.append(item)
    return out
