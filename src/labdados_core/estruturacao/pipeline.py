"""Orquestrador de alto nível: lê documento(s), monta prompt, chama LLM via DataFrameIt.

A função :func:`estruturar` é o ponto único compartilhado entre o backend
(``services/structuring/main.py``, que delega aqui) e o SDK
(``labdados/estruturacao.py``, modo ``local=True``).

Por baixo dos panos chama
`DataFrameIt <https://brunodcdo.com.br/dataframeit/>`_, que cuida de
paralelização, retry com backoff, rate-limit detection e structured
output via Pydantic. Aceita schema como ``BaseModel`` direto ou como
JSON Schema dict (convertido em ``BaseModel`` dinâmico) — preserva a
superfície atual do SDK enquanto migra para a API canônica baseada em
Pydantic.

Erros por documento NÃO interrompem o batch — viram entradas
``{"_error": "..."}`` no resultado. O caller decide se é warning ou
falha fatal a partir da contagem.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from labdados_core.estruturacao._llm import LlmConfig, to_dataframeit_kwargs
from labdados_core.estruturacao.prompts import DEFAULT_SYSTEM_PROMPT
from labdados_core.estruturacao.schema_utils import ensure_pydantic_model

DocumentInput = str | tuple[str, str]
SchemaInput = type[BaseModel] | dict[str, Any]

# Template do prompt enviado a cada linha. ``{texto}`` é substituído pelo
# DataFrameIt por linha (substituição literal — não usa str.format, então
# chaves no system_prompt são seguras).
DEFAULT_PROMPT_TEMPLATE = "{system_prompt}\n\nTexto a analisar:\n{texto}"

# Coluna interna usada no DataFrame que alimentamos ao DataFrameIt.
_TEXT_COL = "texto"
_DOC_ID_COL = "_doc_id"


def estruturar(
    textos: DocumentInput | list[DocumentInput],
    *,
    schema: SchemaInput,
    system_prompt: str = "",
    llm_config: LlmConfig,
    parallel_requests: int = 1,
    prompt_template: str | None = None,
) -> list[dict[str, Any]]:
    """Estrutura um ou mais textos via LLM, devolvendo um dict por entrada.

    Parameters
    ----------
    textos
        ``str``, ``(doc_id, texto)`` ou lista de qualquer um dos dois.
        Quando a entrada é só ``str``, o ``_doc_id`` no retorno fica
        ``"doc_<i>"``.
    schema
        ``BaseModel`` (Pydantic v2) **ou** JSON Schema dict.
        Se for dict, é convertido para Pydantic dinamicamente — ver
        :mod:`labdados_core.estruturacao.schema_utils` para o que cobre.
        Recomendado escrever como Pydantic direto (mais expressivo).
    system_prompt
        Contexto pra LLM. Vazio usa
        :data:`labdados_core.estruturacao.prompts.DEFAULT_SYSTEM_PROMPT`.
    llm_config
        Configuração do provider — ver :class:`LlmConfig`.
    parallel_requests
        Quantas linhas processar em paralelo. ``1`` (default) = sequencial.
        Para batches grandes (>20 docs) considere ``parallel_requests=4``
        ou mais; DataFrameIt faz auto-throttle se bater rate limit.
    prompt_template
        Template alternativo. Use ``{system_prompt}`` e ``{texto}``
        (este último é substituído por linha pelo DataFrameIt). Se
        ``None``, usa :data:`DEFAULT_PROMPT_TEMPLATE`.

    Returns
    -------
    list[dict]
        Um dict por entrada de ``textos``, com ``_doc_id``. Documentos
        com falha de chamada/parse vêm com chave ``_error``.
    """
    items = _normalize(textos)
    pyd_model = ensure_pydantic_model(schema)

    final_template = prompt_template or DEFAULT_PROMPT_TEMPLATE
    final_prompt = final_template.replace(
        "{system_prompt}", system_prompt or DEFAULT_SYSTEM_PROMPT
    )

    valid_items = [(doc_id, text) for doc_id, text in items if text.strip()]
    invalid_items = [(doc_id, text) for doc_id, text in items if not text.strip()]

    extracted_by_id: dict[str, dict[str, Any]] = {}
    for doc_id, _ in invalid_items:
        extracted_by_id[doc_id] = {"_doc_id": doc_id, "_error": "documento vazio"}

    if valid_items:
        try:
            extracted = _run_dataframeit(valid_items, pyd_model, final_prompt, llm_config, parallel_requests)
        except Exception as exc:  # noqa: BLE001 — propagar como dado, não levantar
            for doc_id, _ in valid_items:
                extracted_by_id[doc_id] = {"_doc_id": doc_id, "_error": str(exc)}
        else:
            for record in extracted:
                extracted_by_id[record["_doc_id"]] = record

    return [extracted_by_id[doc_id] for doc_id, _ in items]


def _run_dataframeit(
    valid_items: list[tuple[str, str]],
    pyd_model: type[BaseModel],
    prompt: str,
    llm_config: LlmConfig,
    parallel_requests: int,
) -> list[dict[str, Any]]:
    """Monta DataFrame, chama dataframeit() e devolve list[dict] por linha.

    Lazy import de pandas/dataframeit — assim ``import labdados_core.estruturacao``
    não força essas deps em quem só usa a parte de readers/contracts.
    """
    try:
        import pandas as pd
        from dataframeit import dataframeit
    except ImportError as exc:
        raise RuntimeError(
            "DataFrameIt/pandas não instalados. Adicione `labdados-core[estruturacao]`."
        ) from exc

    df = pd.DataFrame(
        {
            _DOC_ID_COL: [doc_id for doc_id, _ in valid_items],
            _TEXT_COL: [text for _, text in valid_items],
        }
    )

    df_kwargs = to_dataframeit_kwargs(llm_config)

    result_df = dataframeit(
        df,
        questions=pyd_model,
        prompt=prompt,
        text_column=_TEXT_COL,
        parallel_requests=parallel_requests,
        track_tokens=False,
        resume=False,
        **df_kwargs,
    )

    return _df_to_records(result_df, pyd_model)


def _df_to_records(result_df: Any, pyd_model: type[BaseModel]) -> list[dict[str, Any]]:
    field_names = list(pyd_model.model_fields.keys())
    records: list[dict[str, Any]] = []
    error_col = "_error_details"
    has_error_col = error_col in result_df.columns
    for _, row in result_df.iterrows():
        record: dict[str, Any] = {"_doc_id": row[_DOC_ID_COL]}
        if has_error_col and row.get(error_col):
            record["_error"] = str(row[error_col])
        else:
            for f in field_names:
                if f in result_df.columns:
                    value = row[f]
                    record[f] = _coerce(value)
        records.append(record)
    return records


def _coerce(value: Any) -> Any:
    """Converte tipos pandas/numpy nativos para Python puro."""
    try:
        import pandas as pd

        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
    except ImportError:
        if value is None:
            return None
    if hasattr(value, "item"):  # numpy scalar
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    return value


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
