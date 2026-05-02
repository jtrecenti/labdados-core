"""Test de integração que toca a OpenAI real.

Skipa se ``OPENAI_API_KEY`` não estiver disponível (no env do shell ou
num ``.env`` na raiz do repo). Usa ``gpt-4o-mini`` (mais barato/rápido).

Roda assim:

    cd labdados-core
    uv run pytest tests/test_estruturacao_integration.py -v

Ou, pra ignorar nas runs comuns:

    uv run pytest -m "not integration"

"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

# Carrega .env se houver — assim o test funciona sem precisar exportar
# OPENAI_API_KEY no shell.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY não setada (defina no shell ou em labdados-core/.env)",
    ),
]


class Sentimento(BaseModel):
    sentimento: str = Field(description="positivo, negativo ou neutro")
    confianca: str = Field(description="alta, media ou baixa")


def test_estruturar_real_openai_pydantic_model():
    """Sanity check: 1 chamada real à OpenAI com schema Pydantic."""
    from labdados_core.estruturacao import LlmConfig, estruturar

    config = LlmConfig(
        provider="openai",
        model="gpt-4o-mini",
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0.0,
        max_tokens=200,
    )

    result = estruturar(
        "O produto é absolutamente incrível, superou todas as expectativas!",
        schema=Sentimento,
        system_prompt="Analise o sentimento do texto a seguir.",
        llm_config=config,
    )

    assert len(result) == 1
    record = result[0]
    assert "_error" not in record, f"Erro inesperado: {record.get('_error')}"
    assert record["_doc_id"] == "doc_1"
    assert record["sentimento"].lower() in {"positivo", "positive"}


def test_estruturar_real_openai_dict_schema_and_batch():
    """Schema como JSON Schema dict + batch de 2 textos."""
    from labdados_core.estruturacao import LlmConfig, estruturar

    schema = {
        "type": "object",
        "properties": {
            "sentimento": {
                "type": "string",
                "enum": ["positivo", "negativo", "neutro"],
                "description": "sentimento do texto",
            },
        },
        "required": ["sentimento"],
    }

    config = LlmConfig(
        provider="openai",
        model="gpt-4o-mini",
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0.0,
        max_tokens=100,
    )

    result = estruturar(
        [
            ("pos", "Adorei o atendimento, foi muito atencioso."),
            ("neg", "Demorou demais e veio errado."),
        ],
        schema=schema,
        llm_config=config,
    )

    assert [r["_doc_id"] for r in result] == ["pos", "neg"]
    for record in result:
        assert "_error" not in record, f"Erro: {record.get('_error')}"
        assert record["sentimento"] in {"positivo", "negativo", "neutro"}
    assert result[0]["sentimento"] == "positivo"
    assert result[1]["sentimento"] == "negativo"
