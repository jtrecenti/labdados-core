"""Tests para o pipeline de estruturação.

Mockam o openai SDK no nível da fábrica de cliente para que os tests
não dependam de chave nem de rede.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any
from unittest.mock import MagicMock

import pytest

from labdados_core.estruturacao import (
    LlmConfig,
    build_messages,
    call_llm,
    estruturar,
    read_document,
)
from labdados_core.estruturacao.prompts import DEFAULT_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------


def test_build_messages_default_user_position():
    msgs = build_messages("contexto", "texto do doc", {"type": "object"})
    assert msgs[0] == {"role": "system", "content": "contexto"}
    assert msgs[1]["role"] == "user"
    assert "Texto:\ntexto do doc" in msgs[1]["content"]
    assert "Schema esperado:" in msgs[1]["content"]


def test_build_messages_system_position_legacy_sdk():
    msgs = build_messages("ctx", "txt", {"type": "object"}, schema_position="system")
    assert "JSON válido seguindo este schema" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "txt"}


def test_build_messages_default_system_when_blank():
    msgs = build_messages("", "txt", None)
    assert msgs[0]["content"] == DEFAULT_SYSTEM_PROMPT
    assert msgs[1]["content"] == "txt"


def test_build_messages_no_schema_means_user_text_only():
    msgs = build_messages("ctx", "texto puro", None)
    assert msgs[1] == {"role": "user", "content": "texto puro"}


# ---------------------------------------------------------------------------
# _llm
# ---------------------------------------------------------------------------


def _fake_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _patch_client(monkeypatch, response_content: str = '{"ok": true}'):
    client = MagicMock()
    client.chat.completions.create.return_value = _fake_response(response_content)
    monkeypatch.setattr(
        "labdados_core.estruturacao._llm._make_client", lambda config: client
    )
    return client


def test_call_llm_basic_json(monkeypatch):
    client = _patch_client(monkeypatch, '{"x": 1}')
    config = LlmConfig(model="gpt-4o-mini", api_key="sk-test")
    result = call_llm([{"role": "user", "content": "hi"}], config=config)
    assert result == {"x": 1}
    create_kwargs = client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == "gpt-4o-mini"
    assert create_kwargs["response_format"] == {"type": "json_object"}


def test_call_llm_with_schema_uses_json_schema(monkeypatch):
    client = _patch_client(monkeypatch, '{"a": "b"}')
    config = LlmConfig(model="gpt-4o-mini")
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    call_llm([{"role": "user", "content": "hi"}], config=config, schema=schema)
    rf = client.chat.completions.create.call_args.kwargs["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"] == schema


def test_call_llm_invalid_json_returns_raw(monkeypatch):
    _patch_client(monkeypatch, "isso não é json {")
    config = LlmConfig(model="gpt-4o-mini")
    result = call_llm([{"role": "user", "content": "hi"}], config=config)
    assert result == {"_raw_response": "isso não é json {"}


def test_call_llm_streaming(monkeypatch):
    client = MagicMock()

    def make_event(piece):
        delta = MagicMock()
        delta.content = piece
        choice = MagicMock()
        choice.delta = delta
        ev = MagicMock()
        ev.choices = [choice]
        return ev

    client.chat.completions.create.return_value = iter(
        [make_event('{"ok"'), make_event(": "), make_event("true}")]
    )
    monkeypatch.setattr(
        "labdados_core.estruturacao._llm._make_client", lambda config: client
    )

    config = LlmConfig(model="m", stream=True)
    result = call_llm([{"role": "user", "content": "hi"}], config=config)
    assert result == {"ok": True}
    assert client.chat.completions.create.call_args.kwargs["stream"] is True


def test_llm_config_azure_requires_endpoint():
    from labdados_core.estruturacao._llm import _make_client

    config = LlmConfig(model="dep", provider="azure_openai", api_version="2024-12-01")
    with pytest.raises(ValueError, match="base_url"):
        _make_client(config)


# ---------------------------------------------------------------------------
# readers
# ---------------------------------------------------------------------------


def test_read_txt():
    docs = read_document(b"linha 1\nlinha 2", "doc.txt")
    assert docs == [("doc", "linha 1\nlinha 2")]


def test_read_md_treats_as_plain_text():
    docs = read_document(b"# titulo", "notas.md")
    assert docs[0][1] == "# titulo"


def test_read_csv_per_row_with_text_column():
    csv_bytes = b"id,texto\n1,primeiro\n2,segundo\n"
    docs = read_document(csv_bytes, "data.csv", csv_text_column="texto")
    assert [d[1] for d in docs] == ["primeiro", "segundo"]
    assert docs[0][0] == "data__row0001"


def test_read_csv_concat_when_no_text_column():
    csv_bytes = b"id,a,b\n1,foo,bar\n"
    [(_, text)] = read_document(csv_bytes, "data.csv")
    assert "id: 1" in text
    assert "a: foo" in text
    assert "b: bar" in text


def test_read_csv_text_column_case_insensitive():
    csv_bytes = b"ID,Texto\n1,hello\n"
    [(_, text)] = read_document(csv_bytes, "x.csv", csv_text_column="texto")
    assert text == "hello"


def test_read_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Extensão não suportada"):
        read_document(b"...", "foo.pdf")


def test_read_xlsx_per_row():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["id", "texto"])
    ws.append([1, "alpha"])
    ws.append([2, "beta"])
    buf = io.BytesIO()
    wb.save(buf)

    docs = read_document(buf.getvalue(), "data.xlsx", csv_text_column="texto")
    assert [d[1] for d in docs] == ["alpha", "beta"]


def test_read_docx_extracts_paragraphs():
    """Build a minimal valid DOCX inline (zip + word/document.xml)."""
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:r><w:t>Primeiro paragrafo.</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Segundo paragrafo.</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
    [(_, text)] = read_document(buf.getvalue(), "doc.docx")
    assert text == "Primeiro paragrafo.\nSegundo paragrafo."


# ---------------------------------------------------------------------------
# pipeline (estruturar)
# ---------------------------------------------------------------------------


def _patch_call_llm(monkeypatch, returns: dict[str, Any] | list[dict[str, Any]]):
    """Substitui call_llm para que estruturar() não toque rede."""
    calls: list[Any] = []
    seq = returns if isinstance(returns, list) else [returns]
    iterator = iter(seq)

    def fake(messages, *, config, schema=None):
        calls.append({"messages": messages, "schema": schema, "config": config})
        try:
            return next(iterator)
        except StopIteration:
            return seq[-1]

    monkeypatch.setattr("labdados_core.estruturacao.pipeline.call_llm", fake)
    return calls


def test_estruturar_single_string(monkeypatch):
    calls = _patch_call_llm(monkeypatch, {"x": 1})
    result = estruturar("texto", llm_config=LlmConfig(model="m"))
    assert result == [{"x": 1, "_doc_id": "doc_1"}]
    assert len(calls) == 1


def test_estruturar_list_of_strings_assigns_ids(monkeypatch):
    _patch_call_llm(monkeypatch, [{"i": 1}, {"i": 2}])
    result = estruturar(["a", "b"], llm_config=LlmConfig(model="m"))
    assert [r["_doc_id"] for r in result] == ["doc_1", "doc_2"]


def test_estruturar_preserves_explicit_doc_ids(monkeypatch):
    _patch_call_llm(monkeypatch, [{"i": 1}, {"i": 2}])
    result = estruturar(
        [("alfa", "texto a"), ("beta", "texto b")],
        llm_config=LlmConfig(model="m"),
    )
    assert [r["_doc_id"] for r in result] == ["alfa", "beta"]


def test_estruturar_skips_empty_text(monkeypatch):
    calls = _patch_call_llm(monkeypatch, {"never": "called"})
    result = estruturar(["", "  "], llm_config=LlmConfig(model="m"))
    assert all(r["_error"] == "documento vazio" for r in result)
    assert calls == []  # LLM nunca chamado


def test_estruturar_captures_per_doc_errors(monkeypatch):
    def fake(messages, *, config, schema=None):
        if "fail" in messages[-1]["content"]:
            raise RuntimeError("boom")
        return {"ok": True}

    monkeypatch.setattr("labdados_core.estruturacao.pipeline.call_llm", fake)
    result = estruturar(["bom", "fail aqui"], llm_config=LlmConfig(model="m"))
    assert result[0] == {"ok": True, "_doc_id": "doc_1"}
    assert result[1]["_error"] == "boom"
    assert result[1]["_doc_id"] == "doc_2"


def test_estruturar_passes_schema_through(monkeypatch):
    calls = _patch_call_llm(monkeypatch, {"x": 1})
    schema = {"type": "object"}
    estruturar("t", schema=schema, llm_config=LlmConfig(model="m"))
    assert calls[0]["schema"] == schema
    # E o build_messages injetou o schema na user message:
    user_msg = calls[0]["messages"][1]["content"]
    assert "Schema esperado:" in user_msg
    assert json.dumps(schema, ensure_ascii=False) in user_msg
