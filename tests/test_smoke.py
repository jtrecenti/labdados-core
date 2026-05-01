"""Testes de fumaça do labdados-core. Foco: superfície estável e que o
template é distribuído com o pacote.

Testes do fluxo Datajud agora mockam ``juscraper.scraper("datajud")``
em vez de ``httpx`` — desde a v0.4.0, o ``_datajud`` é um wrapper sobre
``juscraper.contar_processos`` (PR jtrecenti/juscraper#180).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

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


# ---------------------------------------------------------------------------
# Helpers para mockar o juscraper.scraper("datajud").contar_processos
# ---------------------------------------------------------------------------


class _FakeDatajudScraper:
    """Mock mínimo. Retorna o ``df`` configurado a cada chamada."""

    def __init__(self, df: pd.DataFrame, raise_exc: Exception | None = None) -> None:
        self._df = df
        self._raise = raise_exc
        self.calls: list[dict[str, Any]] = []

    def set_verbose(self, _v: int) -> None:  # noqa: D401
        pass

    def contar_processos(self, **kwargs: Any) -> pd.DataFrame:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        return self._df


@pytest.fixture()
def fake_juscraper(monkeypatch):
    """Substitui ``juscraper.scraper(...)`` por um mock controlável."""
    import juscraper as jus

    holder: dict[str, _FakeDatajudScraper] = {}

    def _factory(df: pd.DataFrame, *, raise_exc: Exception | None = None) -> _FakeDatajudScraper:
        fake = _FakeDatajudScraper(df, raise_exc=raise_exc)
        monkeypatch.setattr(jus, "scraper", lambda _alias: fake)
        holder["fake"] = fake
        return fake

    return _factory


# ---------------------------------------------------------------------------
# Datajud — caminho feliz e variações
# ---------------------------------------------------------------------------


def test_datajud_count_with_results(fake_juscraper):
    """juscraper devolve 12345 hits → veredito 'viable'."""
    df = pd.DataFrame(
        [{"tribunal": "TJSP", "alias": "api_publica_tjsp",
          "count": 12345, "relation": "eq", "error": None}]
    )
    fake_juscraper(df)

    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
            "filtro_classes_cnj": "7",
            "recorte_inicio": "2020-01-01",
            "recorte_fim": "2024-12-31",
        }
    )
    assert out["total_aproximado"] == 12345
    assert out["verdict"] == "viable"
    assert out["tribunais"][0]["count"] == 12345
    assert out["tribunais"][0]["relation"] == "eq"


def test_datajud_volume_above_threshold_yields_caveats(fake_juscraper):
    df = pd.DataFrame(
        [{"tribunal": "TJSP", "alias": "api_publica_tjsp",
          "count": 75_000, "relation": "eq", "error": None}]
    )
    fake_juscraper(df)

    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
        }
    )
    assert out["verdict"] == "caveats"
    assert any("fatiar" in h.lower() for h in out["highlights"])


def test_datajud_network_failure_yields_unviable_when_only_tribunal(fake_juscraper):
    fake_juscraper(pd.DataFrame(), raise_exc=ConnectionError("timeout"))

    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
        }
    )
    # Quando todas as chamadas erram, veredito é unviable
    assert out["verdict"] == "unviable"
    assert out["errors"]


def test_datajud_passa_data_ajuizamento_pro_juscraper(fake_juscraper):
    """O recorte ``recorte_inicio``/``_fim`` do form vira
    ``data_ajuizamento_inicio``/``_fim`` na chamada do juscraper."""
    df = pd.DataFrame(
        [{"tribunal": "TJSP", "alias": "api_publica_tjsp",
          "count": 100, "relation": "eq", "error": None}]
    )
    fake = fake_juscraper(df)

    analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
            "recorte_inicio": "2020-01-01",
            "recorte_fim": "2024-12-31",
        }
    )
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["tribunal"] == "TJSP"
    assert call["data_ajuizamento_inicio"] == "2020-01-01"
    assert call["data_ajuizamento_fim"] == "2024-12-31"


def test_datajud_multiplas_classes_geram_n_chamadas_e_somam(fake_juscraper):
    """juscraper aceita só 1 classe — várias classes viram N chamadas
    com soma final."""
    df = pd.DataFrame(
        [{"tribunal": "TJSP", "alias": "api_publica_tjsp",
          "count": 1000, "relation": "eq", "error": None}]
    )
    fake = fake_juscraper(df)

    out = analyze_form(
        {
            "listagem": "datajud",
            "tribunais_selecionados": ["tjsp"],
            "filtro_classes_cnj": "7\n198\n436",
        }
    )
    # 3 classes → 3 chamadas, count = 3 × 1000
    assert len(fake.calls) == 3
    classes_chamadas = [c["classe"] for c in fake.calls]
    assert classes_chamadas == ["7", "198", "436"]
    assert out["tribunais"][0]["count"] == 3000


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


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
            "recorte_inicio": "",
            "recorte_fim": "",
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
