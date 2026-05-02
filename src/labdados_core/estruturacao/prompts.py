"""Construção das mensagens enviadas ao LLM.

Adotamos a variante do backend (`services/structuring/main.py`) como
default — schema vai na mensagem `user`, perto do texto. Isso bate
melhor com ``response_format={"type": "json_schema", ...}`` (vLLM
guided decoding e OpenAI structured outputs) e mantém a system message
livre para instrução pura.

A variante histórica do SDK (schema na system) fica disponível via
``schema_position="system"`` para evitar quebra de comportamento durante
a migração.
"""

from __future__ import annotations

import json
from typing import Any, Literal

SchemaPosition = Literal["user", "system"]

DEFAULT_SYSTEM_PROMPT = "Você extrai informações estruturadas de documentos jurídicos."


def build_messages(
    system_prompt: str,
    text: str,
    schema: dict[str, Any] | None = None,
    *,
    schema_position: SchemaPosition = "user",
) -> list[dict[str, str]]:
    """Monta a lista ``[{role, content}, ...]`` para o chat completion.

    Parameters
    ----------
    system_prompt
        Instrução de contexto. Se vazio, usa :data:`DEFAULT_SYSTEM_PROMPT`.
    text
        Texto do documento a estruturar.
    schema
        JSON Schema (dict). Se ``None``, schema não é injetado no prompt
        (use só com ``response_format={"type": "json_object"}``).
    schema_position
        Onde injetar o schema. ``"user"`` (default, igual ao backend)
        coloca após o texto. ``"system"`` (legacy SDK) coloca após a
        instrução de contexto.
    """
    base_system = system_prompt or DEFAULT_SYSTEM_PROMPT
    messages: list[dict[str, str]] = []

    if schema and schema_position == "system":
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        messages.append(
            {
                "role": "system",
                "content": (
                    f"{base_system}\n\n"
                    f"Responda EXCLUSIVAMENTE com JSON válido seguindo este schema:\n{schema_str}"
                ),
            }
        )
        messages.append({"role": "user", "content": text})
        return messages

    messages.append({"role": "system", "content": base_system})
    if schema and schema_position == "user":
        schema_str = json.dumps(schema, ensure_ascii=False)
        user_content = (
            "Extraia as informações do texto abaixo de acordo com o schema JSON definido.\n\n"
            f"Texto:\n{text}\n\n"
            f"Schema esperado:\n{schema_str}"
        )
    else:
        user_content = text
    messages.append({"role": "user", "content": user_content})
    return messages
