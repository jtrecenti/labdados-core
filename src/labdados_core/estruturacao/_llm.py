"""Cliente LLM unificado para os três caminhos que usamos hoje.

Os três providers que aparecem no projeto são todos OpenAI-compatible
no nível da API:

- **OpenAI** direto — ``provider="openai"``.
- **Azure OpenAI** — ``provider="azure_openai"`` + ``azure_endpoint``,
  ``api_version``, ``deployment``.
- **OpenAI-compat self-host** (vLLM em Container Apps, Ollama local,
  LM Studio, OpenRouter) — ``provider="openai_compat"`` + ``base_url``.

O cliente real é sempre o ``openai`` SDK; o que varia é como
instanciar. Centralizar essa decisão aqui evita que cada consumidor
reimplemente a mesma matriz de if/else.

Notas operacionais:

- ``stream=True`` é **necessário** para vLLM atrás do ingress do Azure
  Container Apps — gerações longas sem stream batem em "stream timeout"
  ~240s mesmo com ``timeout=None`` no cliente.
- Quando há ``schema`` válido, usamos ``response_format={"type":
  "json_schema", ...}`` (structured outputs / guided decoding); senão,
  caímos para ``json_object``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

Provider = Literal["openai", "azure_openai", "openai_compat"]


@dataclass
class LlmConfig:
    """Configuração para uma chamada LLM.

    Atributos relevantes por provider:

    - ``openai``: ``model``, ``api_key``.
    - ``azure_openai``: ``model`` (= deployment name), ``api_key``,
      ``base_url`` (Azure endpoint), ``api_version``.
    - ``openai_compat``: ``model``, ``base_url``, ``api_key`` (pode ser
      ``"unused"``/``"EMPTY"`` para vLLM/Ollama).
    """

    model: str
    provider: Provider = "openai"
    api_key: str | None = None
    base_url: str | None = None
    api_version: str | None = None
    temperature: float = 0.0
    max_tokens: int = 4096
    stream: bool = False
    timeout: float | None = 120.0
    extra: dict[str, Any] = field(default_factory=dict)


def _make_client(config: LlmConfig):
    """Instancia o cliente OpenAI/AzureOpenAI conforme o provider.

    Lazy import para que ``import labdados_core.estruturacao`` não force
    o openai SDK em quem não precisa (ex.: backend que importa só
    ``contracts``).
    """
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai não instalado. Adicione `labdados-core[estruturacao]` às deps."
        ) from exc

    if config.provider == "azure_openai":
        if not config.base_url:
            raise ValueError("azure_openai requer base_url (azure_endpoint)")
        if not config.api_version:
            raise ValueError("azure_openai requer api_version")
        return AzureOpenAI(
            azure_endpoint=config.base_url,
            api_key=config.api_key,
            api_version=config.api_version,
            timeout=config.timeout,
        )

    kwargs: dict[str, Any] = {"api_key": config.api_key or "unused", "timeout": config.timeout}
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return OpenAI(**kwargs)


def _build_response_format(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not schema:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {"name": "extraction", "schema": schema, "strict": True},
    }


def _parse_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError:
        return {"_raw_response": content}


def call_llm(
    messages: list[dict[str, str]],
    *,
    config: LlmConfig,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Faz uma chamada chat completion e devolve o dict JSON parseado.

    Em caso de JSON inválido, devolve ``{"_raw_response": "..."}`` em
    vez de levantar — assim o caller (worker, pipeline) consegue
    persistir e marcar o documento como falho sem abortar o batch.
    """
    client = _make_client(config)
    response_format = _build_response_format(schema)

    create_kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "response_format": response_format,
        **config.extra,
    }

    if config.stream:
        create_kwargs["stream"] = True
        stream = client.chat.completions.create(**create_kwargs)
        chunks: list[str] = []
        for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                chunks.append(piece)
        return _parse_json("".join(chunks))

    resp = client.chat.completions.create(**create_kwargs)
    return _parse_json(resp.choices[0].message.content or "")
