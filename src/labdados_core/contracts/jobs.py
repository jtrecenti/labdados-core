"""Payloads dos endpoints ``/process`` e ``/status/{job_id}`` dos serviços.

Cada container de serviço (``services/ocr``, ``services/transcription``,
etc.) expõe estes contratos. O ``app/workers/job_consumer.py`` do backend
fala neles. Mantê-los aqui evita que cada serviço/cliente reimplemente
sua versão e elas divirjam silenciosamente.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from labdados_core.contracts.files import FileInfo


class JobStatus(StrEnum):
    """Estados que um job pode ter ao ser consultado por ``/status/{job_id}``.

    Reflete os literais já usados em ``services/structuring/main.py`` e em
    ``backend/app/workers/job_consumer.py``.
    """

    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProcessRequest(BaseModel):
    """Payload aceito por ``POST /process`` em todos os serviços.

    O ``request_meta`` só é consumido por ``services/viability`` (alimenta
    o cabeçalho do relatório); demais serviços ignoram. Mantido no schema
    base para permitir que o worker chame todos uniformemente.
    """

    request_id: str
    model_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    files: list[FileInfo] = Field(default_factory=list)
    request_meta: dict[str, Any] = Field(default_factory=dict)


class ProcessResponse(BaseModel):
    """Resposta de ``POST /process``.

    Pode representar:

    - **Sync**: ``status="completed"`` + ``result_blob_path`` preenchido.
    - **Async**: ``status="processing"`` + ``job_id`` preenchido (worker
      passa a fazer polling em ``/status/{job_id}``).

    O ``analysis`` só é populado por viability (espelha o shape de
    ``Request.analysis``); ``result_container`` permite que o serviço
    indique container alternativo (ex.: ``viability-reports``) em vez do
    default ``temp-results``.
    """

    status: JobStatus
    job_id: str | None = None
    result_blob_path: str | None = None
    result_container: str | None = None
    files_processed: int | None = None
    files_errored: int | None = None
    error_summary: str | None = None
    analysis: dict[str, Any] | None = None


class JobStatusResponse(BaseModel):
    """Resposta de ``GET /status/{job_id}`` para serviços assíncronos."""

    status: JobStatus
    result_blob_path: str | None = None
    result_container: str | None = None
    files_processed: int | None = None
    files_errored: int | None = None
    error_summary: str | None = None
    analysis: dict[str, Any] | None = None
    error: str | None = None
