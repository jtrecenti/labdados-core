"""Testes do módulo de anonimização.

Foco: pipeline e estratégias de mascaramento (sem carregar o modelo
real, que é caro e fica para teste de integração). O engine é mockado
via ``monkeypatch`` em :func:`detectar_pii`.
"""

from __future__ import annotations

import pytest

from labdados_core.anonimizacao import (
    AnonimizacaoResult,
    Entidade,
    anonimizar,
    aplicar_mascaramento,
)
from labdados_core.anonimizacao.strategies import _Span


def test_aplicar_mascaramento_categoria():
    texto = "Meu nome é João Silva e meu email é joao@x.com"
    # Offsets calculados no texto acima (cada char Unicode = 1 posição):
    # "João Silva" começa em 11 (após "Meu nome é "), termina em 21.
    # "joao@x.com" começa em 36, termina em 46.
    spans = [
        _Span(start=11, end=21, label="private_person", texto="João Silva"),
        _Span(start=36, end=46, label="private_email", texto="joao@x.com"),
    ]
    out = aplicar_mascaramento(texto, spans, estrategia="categoria")
    assert out == "Meu nome é [PESSOA] e meu email é [EMAIL]"


def test_aplicar_mascaramento_asteriscos_preserva_tamanho():
    texto = "João Silva ligou"
    spans = [_Span(start=0, end=10, label="private_person", texto="João Silva")]
    out = aplicar_mascaramento(texto, spans, estrategia="asteriscos")
    assert out == "********** ligou"
    assert len(out) == len(texto)


def test_aplicar_mascaramento_pseudonimo_consistente():
    texto = "João Silva e Maria. João Silva voltou."
    spans = [
        _Span(start=0, end=10, label="private_person", texto="João Silva"),
        _Span(start=13, end=18, label="private_person", texto="Maria"),
        _Span(start=20, end=30, label="private_person", texto="João Silva"),
    ]
    out = aplicar_mascaramento(texto, spans, estrategia="pseudonimo")
    # João Silva (1ª e 3ª ocorrência) → PESSOA_1; Maria → PESSOA_2.
    assert "PESSOA_1" in out
    assert "PESSOA_2" in out
    assert out.count("PESSOA_1") == 2


def test_aplicar_mascaramento_sem_spans():
    assert aplicar_mascaramento("texto puro", []) == "texto puro"


def test_anonimizar_normaliza_input(monkeypatch):
    """``anonimizar("texto")`` deve retornar 1 resultado com doc_1."""
    from labdados_core.anonimizacao import pipeline as pmod

    monkeypatch.setattr(pmod, "detectar_pii", lambda *a, **kw: [])

    out = anonimizar("oi mundo")
    assert len(out) == 1
    assert out[0].doc_id == "doc_1"
    assert out[0].texto_anonimizado == "oi mundo"


def test_anonimizar_lista_com_ids(monkeypatch):
    from labdados_core.anonimizacao import pipeline as pmod

    monkeypatch.setattr(pmod, "detectar_pii", lambda *a, **kw: [])

    out = anonimizar([("a", "texto a"), ("b", "texto b")])
    assert [r.doc_id for r in out] == ["a", "b"]


def test_anonimizar_aplica_mascaramento_e_devolve_entidades(monkeypatch):
    from labdados_core.anonimizacao import pipeline as pmod

    # "Meu nome é " = 11 chars, "João Silva" começa em 11, termina em 21.
    fake_spans = [_Span(start=11, end=21, label="private_person", texto="João Silva")]
    monkeypatch.setattr(pmod, "detectar_pii", lambda *a, **kw: fake_spans)

    out = anonimizar("Meu nome é João Silva.")
    assert len(out) == 1
    res = out[0]
    assert res.texto_anonimizado == "Meu nome é [PESSOA]."
    assert len(res.entidades) == 1
    assert res.entidades[0].label == "private_person"
    assert res.entidades[0].texto == "João Silva"
    assert res.erro is None


def test_anonimizar_erro_no_engine_vira_dado_nao_excecao(monkeypatch):
    from labdados_core.anonimizacao import pipeline as pmod

    def _raise(*a, **kw):
        raise RuntimeError("modelo offline")

    monkeypatch.setattr(pmod, "detectar_pii", _raise)
    out = anonimizar("texto")
    assert len(out) == 1
    assert out[0].erro == "modelo offline"
    # Texto fica intacto se o modelo falhou.
    assert out[0].texto_anonimizado == "texto"


def test_anonimizar_texto_vazio_passa_direto(monkeypatch):
    from labdados_core.anonimizacao import pipeline as pmod

    called = {"n": 0}

    def _bump(*a, **kw):
        called["n"] += 1
        return []

    monkeypatch.setattr(pmod, "detectar_pii", _bump)
    out = anonimizar("   ")
    assert called["n"] == 0  # não chama o modelo
    assert out[0].texto_anonimizado == "   "


def test_entidade_to_dict():
    e = Entidade(start=0, end=5, label="private_person", texto="João")
    assert e.to_dict() == {"start": 0, "end": 5, "label": "private_person", "texto": "João"}


def test_anonimizacao_result_to_dict():
    r = AnonimizacaoResult(
        doc_id="x",
        texto_original="",
        texto_anonimizado="ok",
        entidades=[],
    )
    d = r.to_dict()
    assert d["doc_id"] == "x"
    assert d["texto_anonimizado"] == "ok"
    assert d["erro"] is None
    assert d["entidades"] == []


def test_aplicar_mascaramento_spans_sobrepostos_nao_quebram_offsets():
    """Spans fora de ordem devem ser aplicados de trás pra frente
    para não corromper offsets dos próximos."""
    texto = "AAAA BBBB CCCC"
    spans = [
        _Span(start=0, end=4, label="private_person", texto="AAAA"),
        _Span(start=10, end=14, label="private_email", texto="CCCC"),
        _Span(start=5, end=9, label="private_phone", texto="BBBB"),
    ]
    out = aplicar_mascaramento(texto, spans, estrategia="categoria")
    assert out == "[PESSOA] [TELEFONE] [EMAIL]"


@pytest.mark.integration
def test_pipeline_real_model_smoke():
    """Smoke test contra o modelo real. Requer transformers/torch
    instalados e download do modelo (~3GB). Pular se não disponível."""
    pytest.importorskip("transformers")
    pytest.importorskip("torch")
    out = anonimizar("My name is Alice Smith and my email is alice@example.com")
    assert len(out) == 1
    res = out[0]
    # O modelo deve detectar pelo menos a pessoa.
    labels = {e.label for e in res.entidades}
    assert "private_person" in labels or "private_email" in labels
