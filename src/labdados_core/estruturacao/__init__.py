"""Extração estruturada com LLMs — núcleo compartilhado.

Este subpacote unifica a lógica que hoje vive em
``services/structuring/main.py`` (backend) e
``labdados/estruturacao.py`` (SDK em modo local). Os dois consumidores
montavam prompts e cliente OpenAI próprios — com risco real de divergir
quando alguém ajustasse o template num só lado.

Componentes:

- :mod:`estruturacao.prompts` — montagem das mensagens (system + user).
  Schema vai na mensagem user por padrão (mais robusto com
  ``response_format=json_schema``).
- :mod:`estruturacao._llm` — :class:`LlmConfig` e :func:`call_llm`,
  cliente OpenAI-compatible que cobre OpenAI, Azure OpenAI, vLLM e
  Ollama com o mesmo código. Streaming opcional (obrigatório no caminho
  Container Apps → vLLM).
- :mod:`estruturacao.readers` — leitura de ``.txt/.md/.docx/.csv/.xlsx``
  produzindo a lista ``(doc_id, texto)`` que o pipeline consome.
- :mod:`estruturacao.pipeline` — :func:`estruturar`, função de alto nível
  que orquestra ``read → prompt → LLM → parse``.

A intenção futura é trocar isto por
`DataFrameIt <https://brunodcdo.com.br/dataframeit/>`_ — ver
``.dev-notes/dataframeit-issue-draft.md`` no repo do escritório.
"""

from labdados_core.estruturacao._llm import LlmConfig, call_llm, to_dataframeit_kwargs
from labdados_core.estruturacao.pipeline import estruturar
from labdados_core.estruturacao.prompts import build_messages
from labdados_core.estruturacao.readers import read_document
from labdados_core.estruturacao.schema_utils import UnsupportedSchema, ensure_pydantic_model

__all__ = [
    "LlmConfig",
    "UnsupportedSchema",
    "build_messages",
    "call_llm",
    "ensure_pydantic_model",
    "estruturar",
    "read_document",
    "to_dataframeit_kwargs",
]
