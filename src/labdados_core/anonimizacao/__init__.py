"""Anonimização de PII em texto — núcleo compartilhado.

Detecta e mascara dados pessoais com classificadores de tokens. Dois
modelos suportados:

- `openai/privacy-filter <https://huggingface.co/openai/privacy-filter>`_
  — multilíngue, 8 categorias PII (``account_number``,
  ``private_address``, ``private_email``, ``private_person``,
  ``private_phone``, ``private_url``, ``private_date``, ``secret``),
  1.5B params.
- `pierreguillou/ner-bert-base-cased-pt-lenerbr
  <https://huggingface.co/pierreguillou/ner-bert-base-cased-pt-lenerbr>`_
  — BERT base PT-BR fine-tuned em LeNER-Br (decisões judiciais), 6
  categorias (``PESSOA``, ``ORGANIZACAO``, ``LOCAL``, ``TEMPO``,
  ``LEGISLACAO``, ``JURISPRUDENCIA``), 110M params, foco jurídico
  brasileiro.

Componentes:

- :mod:`anonimizacao.pipeline` — :func:`anonimizar`, função de alto nível
  que recebe um ou mais textos e devolve :class:`AnonimizacaoResult`
  com ``texto_anonimizado`` + ``entidades`` detectadas.
- :mod:`anonimizacao.strategies` — funções de mascaramento:
  ``[CATEGORIA]``, asteriscos do tamanho do span ou pseudônimos
  consistentes por categoria.
- :mod:`anonimizacao._engine` — wrapper do HF Transformers que carrega
  o modelo uma única vez e roda inference token-by-token. CPU ou GPU
  CUDA, escolhido pelo caller.

A escolha CPU/GPU fica no caller. O serviço em produção roda em GPU
T4 (rápido); modo local do SDK roda em CPU (basta ``pip install
labdados[anonimizacao]``, sem bibliotecas Nvidia).
"""

from labdados_core.anonimizacao.exceptions import ModeloIndisponivel
from labdados_core.anonimizacao.pipeline import (
    AnonimizacaoResult,
    Entidade,
    anonimizar,
)
from labdados_core.anonimizacao.strategies import (
    EstrategiaMascaramento,
    aplicar_mascaramento,
)

__all__ = [
    "AnonimizacaoResult",
    "Entidade",
    "EstrategiaMascaramento",
    "ModeloIndisponivel",
    "anonimizar",
    "aplicar_mascaramento",
]
