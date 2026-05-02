"""Orquestrador de alto nível: lê documento(s), monta prompt, chama LLM.

A função :func:`estruturar` é o ponto único compartilhado entre o backend
(``services/structuring/main.py``, que vai delegar aqui após a
refatoração) e o SDK (``labdados/estruturacao.py``, modo ``local=True``).

Erros por documento NÃO interrompem o batch — viram entradas
``{"_error": "..."}`` no resultado. O caller decide se é warning ou
falha fatal a partir da contagem.
"""

from __future__ import annotations

from typing import Any

from labdados_core.estruturacao._llm import LlmConfig, call_llm
from labdados_core.estruturacao.prompts import SchemaPosition, build_messages

DocumentInput = str | tuple[str, str]


def estruturar(
    textos: DocumentInput | list[DocumentInput],
    *,
    schema: dict[str, Any] | None = None,
    system_prompt: str = "",
    llm_config: LlmConfig,
    schema_position: SchemaPosition = "user",
) -> list[dict[str, Any]]:
    """Estrutura um ou mais textos via LLM, devolvendo um dict por entrada.

    Parameters
    ----------
    textos
        ``str``, ``(doc_id, texto)`` ou lista de qualquer um dos dois.
        Quando a entrada é só ``str``, o ``_doc_id`` no retorno fica
        ``"doc_<i>"``.
    schema
        JSON Schema da extração. Quando preenchido, o LLM é chamado com
        ``response_format={"type": "json_schema", ...}``; quando ``None``,
        usa ``json_object`` simples (LLM responde com JSON livre).
    system_prompt
        Contexto pra LLM. Vazio usa
        :data:`labdados_core.estruturacao.prompts.DEFAULT_SYSTEM_PROMPT`.
    llm_config
        Configuração do provider — ver :class:`LlmConfig`.
    schema_position
        ``"user"`` (default, recomendado) ou ``"system"`` (legacy SDK).

    Returns
    -------
    list[dict]
        Um dict por entrada de ``textos``, incluindo ``_doc_id``. Documentos
        com falha de chamada/parse vêm com chave ``_error``.
    """
    items = _normalize(textos)
    out: list[dict[str, Any]] = []
    for doc_id, text in items:
        if not text.strip():
            out.append({"_doc_id": doc_id, "_error": "documento vazio"})
            continue
        messages = build_messages(
            system_prompt, text, schema, schema_position=schema_position
        )
        try:
            result = call_llm(messages, config=llm_config, schema=schema)
        except Exception as exc:  # noqa: BLE001 — propagar como dado, não levantar
            out.append({"_doc_id": doc_id, "_error": str(exc)})
            continue
        result["_doc_id"] = doc_id
        out.append(result)
    return out


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
