"""Smoke tests para os Pydantic models compartilhados.

Não testa lógica (não há lógica) — só garante que os imports funcionam,
os campos obrigatórios são exigidos, os opcionais têm default e a
serialização produz o shape esperado pelos consumidores atuais.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from labdados_core.contracts import (
    FileInfo,
    FileMetadata,
    JobStatus,
    JobStatusResponse,
    ProcessRequest,
    ProcessResponse,
    Verdict,
    ViabilityForm,
    ViabilityResults,
)

# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------


def test_file_metadata_minimal():
    m = FileMetadata(name="a.pdf", size_bytes=10, blob_path="uploads/a.pdf")
    assert m.content_type is None
    assert m.pages is None
    assert m.duration_seconds is None


def test_file_metadata_rejects_negative_size():
    with pytest.raises(ValidationError):
        FileMetadata(name="a.pdf", size_bytes=-1, blob_path="uploads/a.pdf")


def test_file_info_strips_metadata_only_fields():
    info = FileInfo(name="a.pdf", blob_path="uploads/a.pdf")
    assert info.size_bytes is None
    assert "pages" not in info.model_dump()


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------


def test_process_request_defaults():
    req = ProcessRequest(request_id="r1", model_id="m1")
    assert req.config == {}
    assert req.files == []
    assert req.request_meta == {}


def test_process_request_with_files():
    req = ProcessRequest(
        request_id="r1",
        model_id="m1",
        files=[FileInfo(name="a.pdf", blob_path="uploads/a.pdf")],
    )
    assert len(req.files) == 1
    assert req.files[0].name == "a.pdf"


def test_process_response_sync_completed():
    resp = ProcessResponse(status=JobStatus.completed, result_blob_path="results/r1.zip")
    assert resp.status is JobStatus.completed
    assert resp.job_id is None


def test_process_response_async_processing():
    resp = ProcessResponse(status=JobStatus.processing, job_id="job-1")
    assert resp.result_blob_path is None


def test_job_status_enum_string_compat():
    """Worker compara com string literal — garantimos que o enum bate."""
    assert JobStatus.completed == "completed"
    assert JobStatus.processing == "processing"
    assert JobStatus.failed == "failed"


def test_job_status_response_failed_with_error():
    resp = JobStatusResponse(status=JobStatus.failed, error="modelo indisponível")
    assert resp.error == "modelo indisponível"
    assert resp.result_blob_path is None


# ---------------------------------------------------------------------------
# viability
# ---------------------------------------------------------------------------


def test_verdict_string_compat():
    assert Verdict.viable == "viable"
    assert Verdict.caveats == "caveats"
    assert Verdict.unviable == "unviable"


def test_viability_form_all_optional():
    f = ViabilityForm()
    assert f.listagem == ""
    assert f.tribunais_selecionados == []


def test_viability_form_typical():
    f = ViabilityForm(
        listagem="datajud",
        tribunais_selecionados=["tjsp", "tjrj"],
        filtro_classes_cnj="436, 1116",
    )
    assert f.tribunais_selecionados == ["tjsp", "tjrj"]


def test_viability_results_minimal():
    r = ViabilityResults(listagem="datajud", verdict=Verdict.viable)
    assert r.total_aproximado == 0
    assert r.has_unbounded is False
    assert r.tribunais == []


def test_viability_results_round_trip_dict():
    """Garante que o shape dump bate com o que ``analyze_form`` devolve hoje
    (dict cru consumido pelo template Jinja)."""
    raw = {
        "listagem": "datajud",
        "tribunais": [{"code": "tjsp", "count": 1234, "relation": "eq"}],
        "total_aproximado": 1234,
        "has_unbounded": False,
        "errors": [],
        "verdict": "viable",
        "highlights": ["Volume estimado em 1,234 processos — gerenciável."],
    }
    r = ViabilityResults.model_validate(raw)
    dumped = r.model_dump(mode="json")
    assert dumped == raw
