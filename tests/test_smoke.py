"""Testes de fumaça do labdados-core. Foco: superfície estável e que o
template é distribuído com o pacote."""

from __future__ import annotations

import re

import httpx
import respx

from labdados_core import __version__
from labdados_core.viabilidade import analyze_form, render_report


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2  # MAJOR.MINOR.PATCH


def test_analyze_form_unviable_when_listagem_unknown():
    out = analyze_form({"listagem": "inexistente", "tribunais_selecionados": []})
    assert out["verdict"] == "unviable"
    assert out["errors"]
    assert out["listagem"] == "inexistente"


def test_analyze_form_no_tribunals_is_unviable():
    out = analyze_form({"listagem": "datajud", "tribunais_selecionados": []})
    assert out["verdict"] == "unviable"


def test_analyze_form_missing_palavras_chave_for_jurisprudencia():
    out = analyze_form(
        {
            "listagem": "jurisprudencia",
            "tribunais_selecionados": ["tjsp"],
            "filtro_palavras_chave": "",
        }
    )
    assert out["errors"]
    assert "palavras-chave vazio" in out["errors"][0]["error"].lower()


@respx.mock
def test_datajud_count_with_results():
    """Datajud responde 12345 hits → veredito 'viable' e total certinho."""
    respx.post(re.compile(r"^https://api-publica\.datajud\.cnj\.jus\.br/.*")).mock(
        return_value=httpx.Response(
            200,
            json={"hits": {"total": {"value": 12345, "relation": "eq"}}},
        )
    )
    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
            "filtro_classes_cnj": "7",
            "ano_inicio": 2020,
            "ano_fim": 2024,
        }
    )
    assert out["total_aproximado"] == 12345
    assert out["verdict"] == "viable"
    assert out["tribunais"][0]["count"] == 12345
    assert out["tribunais"][0]["relation"] == "eq"


@respx.mock
def test_datajud_volume_above_threshold_yields_caveats():
    respx.post(re.compile(r"^https://api-publica\.datajud\.cnj\.jus\.br/.*")).mock(
        return_value=httpx.Response(
            200,
            json={"hits": {"total": {"value": 75_000, "relation": "eq"}}},
        )
    )
    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
        }
    )
    assert out["verdict"] == "caveats"
    assert any("fatiar" in h.lower() for h in out["highlights"])


@respx.mock
def test_datajud_network_failure_yields_unviable_when_only_tribunal():
    respx.post(re.compile(r"^https://api-publica\.datajud\.cnj\.jus\.br/.*")).mock(
        side_effect=httpx.ConnectError("timeout")
    )
    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
        }
    )
    # Quando todos os tribunais erram, veredito é unviable
    assert out["verdict"] == "unviable"
    assert out["errors"]


def test_render_report_returns_md_even_without_quarto(monkeypatch, tmp_path):
    """Sem Quarto no PATH, render_report ainda devolve o markdown."""
    import shutil as _sh

    monkeypatch.setattr(_sh, "which", lambda _name: None)

    out = render_report(
        request_id="abc-123",
        form={
            "listagem": "datajud",
            "descricao_pesquisa": "teste",
            "tribunais_selecionados": ["tjsp"],
            "filtro_classes_cnj": "7",
            "filtro_assuntos_cnj": "",
            "filtro_grau": [],
            "ano_inicio": "",
            "ano_fim": "",
        },
        results={
            "listagem": "datajud",
            "tribunais": [{"code": "tjsp", "count": 100, "relation": "eq"}],
            "total_aproximado": 100,
            "errors": [],
            "verdict": "viable",
            "highlights": ["teste"],
        },
        request_meta={
            "researcher_name": "Fulano",
            "institution": "FGV",
            "email": "x@y",
            "created_at": None,
        },
    )
    assert out is not None
    pdf, md = out
    assert pdf == b""  # sem Quarto
    assert b"abc-123" in md
    assert b"VIABLE" in md
