"""Conversão JSON Schema (dict) ↔ Pydantic model.

A superfície pública de :func:`labdados_core.estruturacao.estruturar`
aceita tanto um ``BaseModel`` quanto um JSON Schema cru (compatibilidade
com a superfície atual do SDK ``labdados.estruturacao(schema=dict, ...)``).

DataFrameIt internamente exige Pydantic — então esta função normaliza
ambos para Pydantic antes de chamar.

Cobertura intencionalmente parcial: tipos primitivos (``string``,
``integer``, ``number``, ``boolean``), ``array`` com ``items`` simples,
``object`` aninhado com ``properties``. Casos avançados (``oneOf``,
``anyOf``, ``$ref``, enums complexos) levantam :class:`UnsupportedSchema`
com mensagem útil — quem precisa de mais já está numa zona em que vale
escrever o ``BaseModel`` à mão.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel, Field, create_model


class UnsupportedSchema(ValueError):
    """JSON Schema usa construção que esta versão não converte automaticamente."""


def ensure_pydantic_model(schema: type[BaseModel] | dict[str, Any]) -> type[BaseModel]:
    """Normaliza ``schema`` para um ``BaseModel``.

    Se já for ``BaseModel``, devolve direto. Se for dict (JSON Schema),
    constrói um model dinâmico via :func:`pydantic.create_model`.
    """
    if inspect.isclass(schema) and issubclass(schema, BaseModel):
        return schema
    if isinstance(schema, dict):
        return _dict_to_model(schema, name="ExtractionModel")
    raise TypeError(
        f"schema deve ser BaseModel ou dict (JSON Schema), recebido {type(schema).__name__}"
    )


def _dict_to_model(schema: dict[str, Any], *, name: str) -> type[BaseModel]:
    if schema.get("type") and schema["type"] != "object":
        raise UnsupportedSchema(
            f"Schema raiz precisa ser type=object (recebido {schema.get('type')!r})"
        )
    properties = schema.get("properties") or {}
    if not properties:
        raise UnsupportedSchema(
            "Schema sem 'properties' — não há campos para extrair."
        )
    required = set(schema.get("required") or [])

    fields: dict[str, tuple[Any, Any]] = {}
    for fname, fdef in properties.items():
        py_type = _json_to_python_type(fdef, parent_name=f"{name}_{fname}")
        is_required = fname in required
        if not is_required:
            py_type = py_type | None
        description = fdef.get("description")
        default: Any = ... if is_required else None
        if description:
            fields[fname] = (py_type, Field(default=default, description=description))
        else:
            fields[fname] = (py_type, default)
    return create_model(name, **fields)


def _json_to_python_type(fdef: dict[str, Any], *, parent_name: str) -> Any:
    if "enum" in fdef:
        # Enum vira Literal[...] — DataFrameIt + langchain lidam bem.
        from typing import Literal

        values = tuple(fdef["enum"])
        return Literal[values]  # type: ignore[valid-type]

    for unsupported_key in ("anyOf", "oneOf", "allOf", "$ref"):
        if unsupported_key in fdef:
            raise UnsupportedSchema(
                f"Construção {unsupported_key!r} não é convertida automaticamente — "
                "defina o schema como Pydantic BaseModel."
            )

    t = fdef.get("type")
    if t == "string":
        return str
    if t == "integer":
        return int
    if t == "number":
        return float
    if t == "boolean":
        return bool
    if t == "array":
        items = fdef.get("items") or {}
        item_type = _json_to_python_type(items, parent_name=f"{parent_name}_item") if items else Any
        return list[item_type]
    if t == "object":
        return _dict_to_model(fdef, name=parent_name)
    if t is None:
        # Sem type explícito — deixa Any, langchain trata.
        return Any
    raise UnsupportedSchema(f"Tipo JSON Schema não suportado: {t!r}")
