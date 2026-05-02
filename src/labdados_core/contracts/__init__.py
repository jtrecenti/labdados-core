"""Pydantic models compartilhados entre o backend e o SDK.

Cada submódulo modela uma fronteira de comunicação:

- :mod:`contracts.files` — metadados de arquivos enviados pelo usuário.
- :mod:`contracts.jobs` — payloads dos endpoints ``/process`` e ``/status``
  expostos por cada serviço de processamento.
- :mod:`contracts.viability` — formulário de viabilidade e shape do resultado
  produzido por :func:`labdados_core.viabilidade.analyze_form`.

Estes models são intencionalmente **lenientes** (campos opcionais, sem
``extra="forbid"``) para que upgrades do core não quebrem consumidores
mais antigos. Quando precisar de validação estrita, faça-a no consumidor.
"""

from labdados_core.contracts.files import FileInfo, FileMetadata
from labdados_core.contracts.jobs import (
    JobStatus,
    JobStatusResponse,
    ProcessRequest,
    ProcessResponse,
)
from labdados_core.contracts.viability import Verdict, ViabilityForm, ViabilityResults

__all__ = [
    "FileInfo",
    "FileMetadata",
    "JobStatus",
    "JobStatusResponse",
    "ProcessRequest",
    "ProcessResponse",
    "Verdict",
    "ViabilityForm",
    "ViabilityResults",
]
