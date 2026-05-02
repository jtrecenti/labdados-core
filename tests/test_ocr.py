"""Tests do pipeline de OCR.

Estratégia:

- Geramos PDFs minimalistas em memória via PyMuPDF (1 ou 2 páginas).
- Para o engine pymupdf-tesseract, mockamos ``pytesseract.image_to_string``
  para não exigir o binário do Tesseract instalado no CI.
- O caminho "página com texto nativo" é exercitado direto (PDFs de
  texto, sem mock).

Não há test do paddleocr — o engine é GPU-pesado e exige instalar o
modelo. Esse caminho deve ser validado em integração (Container App).
"""

from __future__ import annotations

import io
import zipfile

import pytest

from labdados_core.ocr import (
    EngineUnavailable,
    TesseractNotFound,
    build_pages_zip,
    extract,
    join_pages,
)

# ---------------------------------------------------------------------------
# Fixture: PDF minimalista em memória
# ---------------------------------------------------------------------------


def _make_pdf(pages_text: list[str]) -> bytes:
    """PDF com uma página por entrada, contendo texto nativo selecionável."""
    import fitz

    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    return doc.tobytes()


def _make_image_only_pdf(num_pages: int = 1) -> bytes:
    """PDF com páginas em branco (sem texto nativo) — força o caminho OCR."""
    import fitz

    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page()
    return doc.tobytes()


# ---------------------------------------------------------------------------
# pipeline.extract — caminho de texto nativo (sem OCR)
# ---------------------------------------------------------------------------


def test_extract_native_text_skips_ocr():
    pdf = _make_pdf(["Página um nativa.", "Página dois nativa."])
    pages = extract(pdf, modelo="pymupdf-tesseract")
    assert len(pages) == 2
    assert "Página um nativa" in pages[0]
    assert "Página dois nativa" in pages[1]


def test_extract_accepts_path(tmp_path):
    pdf = _make_pdf(["Olá mundo."])
    path = tmp_path / "doc.pdf"
    path.write_bytes(pdf)
    pages = extract(path, modelo="pymupdf-tesseract")
    assert "Olá mundo" in pages[0]


def test_extract_unknown_model_raises():
    with pytest.raises(ValueError, match="modelo OCR desconhecido"):
        extract(b"%PDF-1.4 dummy", modelo="abracadabra")


# ---------------------------------------------------------------------------
# pipeline.extract — caminho OCR (mocka pytesseract)
# ---------------------------------------------------------------------------


def test_extract_ocr_path_calls_tesseract(monkeypatch):
    """Páginas sem texto nativo devem cair no Tesseract."""
    import pytesseract

    calls: list[str] = []

    def fake_image_to_string(img, lang=None):
        calls.append(lang or "")
        return "TEXTO RECONHECIDO POR OCR"

    monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string)

    pdf = _make_image_only_pdf(num_pages=2)
    pages = extract(pdf, modelo="pymupdf-tesseract", languages="por+eng")
    assert pages == ["TEXTO RECONHECIDO POR OCR", "TEXTO RECONHECIDO POR OCR"]
    assert calls == ["por+eng", "por+eng"]


def test_extract_bw_fallback_retries_when_first_pass_empty(monkeypatch):
    """Se a primeira passagem do Tesseract vier vazia, tenta de novo em BW."""
    import pytesseract

    call_count = [0]

    def fake_image_to_string(img, lang=None):
        call_count[0] += 1
        # primeira chamada (img colorida) devolve vazio; segunda (BW) acerta.
        if call_count[0] == 1:
            return "   \n  "
        return "AHA, BW funcionou."

    monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string)

    pdf = _make_image_only_pdf(1)
    pages = extract(pdf, modelo="pymupdf-tesseract", bw_fallback=True)
    assert call_count[0] == 2
    assert "BW funcionou" in pages[0]


def test_extract_bw_fallback_disabled_keeps_empty(monkeypatch):
    import pytesseract

    monkeypatch.setattr(pytesseract, "image_to_string", lambda img, lang=None: "")
    pdf = _make_image_only_pdf(1)
    pages = extract(pdf, modelo="pymupdf-tesseract", bw_fallback=False)
    assert pages[0] == ""


def test_extract_raises_tesseract_not_found(monkeypatch):
    import pytesseract

    def fake(img, lang=None):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", fake)

    pdf = _make_image_only_pdf(1)
    with pytest.raises(TesseractNotFound, match="binário do Tesseract"):
        extract(pdf, modelo="pymupdf-tesseract")


def test_extract_engine_unavailable_when_pymupdf_missing(monkeypatch):
    """Se a dep estiver ausente, mensagem deve apontar pro extra."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in ("fitz", "pytesseract", "PIL"):
            raise ImportError(f"sem {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(EngineUnavailable, match=r"ocr-cpu"):
        extract(b"%PDF-1.4", modelo="pymupdf-tesseract")


# ---------------------------------------------------------------------------
# formatters
# ---------------------------------------------------------------------------


def test_join_pages_txt():
    out = join_pages(["pagina 1", "pagina 2"])
    assert out == "pagina 1\n\npagina 2"


def test_join_pages_md_adds_headers():
    out = join_pages(["pagina 1", "pagina 2"], output_format="md")
    assert "# Pagina 1" in out
    assert "# Pagina 2" in out
    assert "pagina 1" in out


def test_build_pages_zip_layout():
    payload = build_pages_zip(
        [("doc.pdf", ["a", "b"]), ("outro.pdf", ["c"])],
        output_format="txt",
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = sorted(zf.namelist())
        assert names == [
            "doc/pagina_0001.txt",
            "doc/pagina_0002.txt",
            "outro/pagina_0001.txt",
        ]
        assert zf.read("doc/pagina_0001.txt").decode() == "a"


def test_build_pages_zip_md_format():
    payload = build_pages_zip([("x.pdf", ["pag"])], output_format="md")
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        content = zf.read("x/pagina_0001.md").decode()
        assert content.startswith("# Pagina 1")
        assert "pag" in content


def test_build_pages_zip_handles_no_extension():
    payload = build_pages_zip([("noext", ["a"])], output_format="txt")
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        assert "noext/pagina_0001.txt" in zf.namelist()


# ---------------------------------------------------------------------------
# tesseract command discovery
# ---------------------------------------------------------------------------


def test_configure_tesseract_command_uses_env(monkeypatch):
    from unittest.mock import MagicMock

    from labdados_core.ocr._tesseract import configure_tesseract_command

    monkeypatch.setenv("TESSERACT_CMD", "/custom/path/tesseract")
    fake_module = MagicMock()
    configure_tesseract_command(fake_module)
    assert fake_module.pytesseract.tesseract_cmd == "/custom/path/tesseract"


def test_configure_tesseract_command_falls_back_to_which(monkeypatch):
    from unittest.mock import MagicMock

    from labdados_core.ocr import _tesseract

    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(_tesseract.shutil, "which", lambda _: "/usr/bin/tesseract")
    fake_module = MagicMock()
    _tesseract.configure_tesseract_command(fake_module)
    assert fake_module.pytesseract.tesseract_cmd == "/usr/bin/tesseract"
