"""Metadados de arquivo trafegados entre upload, backend e serviços."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    """Metadado completo de um arquivo já no Blob Storage.

    Usado pelo SDK e pelo frontend ao montar ``POST /api/(v1/)?requests``.
    Os campos opcionais (``pages``, ``duration_seconds``) são populados
    pelo cliente quando faz sentido para o serviço alvo (PDF -> ``pages``,
    áudio -> ``duration_seconds``); o backend usa esses valores para
    estimativa de custo.
    """

    name: str
    size_bytes: int = Field(ge=0)
    blob_path: str
    content_type: str | None = None
    pages: int | None = None
    duration_seconds: float | None = None


class FileInfo(BaseModel):
    """Subconjunto de :class:`FileMetadata` usado pelos serviços downstream.

    Os serviços (`services/<svc>/process`) só precisam saber onde baixar
    e como nomear o arquivo de saída. Mantemos como model próprio em vez
    de reusar :class:`FileMetadata` para que o serviço não precise validar
    campos que ele ignora.
    """

    name: str
    blob_path: str
    size_bytes: int | None = None
    content_type: str | None = None
