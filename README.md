# labdados-core

Núcleo Python compartilhado entre o **backend** do escritório de apoio do
LabDados ([`escritorio-servicos`](https://github.com/lab-dados/escritorio-servicos))
e o **SDK Python** ([`labdados-sdk`](https://github.com/lab-dados/labdados-sdk)).

A regra: tudo que precisa ficar **byte-equivalente** entre os dois lados
(prompts, formatadores de saída, schemas, regras de domínio) vem pra cá.
Tudo que é específico de um (cliente HTTP do SDK, worker de fila do
backend, app FastAPI) **não** vem.

## O que mora aqui

| Subpacote | O que faz | Extras necessários |
|---|---|---|
| `contracts` | Pydantic models compartilhados (`FileMetadata`, `ProcessRequest/Response`, `JobStatus`, `ViabilityForm/Results`). | (nenhum — `pydantic` é dep base) |
| `viabilidade` | Análise de viabilidade (Datajud + juscraper) + render do relatório PDF/MD via Quarto. | (nenhum) |
| `estruturacao` | Pipeline LLM via [DataFrameIt](https://brunodcdo.com.br/dataframeit/), readers de `.txt/.md/.docx/.csv/.xlsx`, prompts canônicos. | `[estruturacao]` |
| `ocr` | Pipeline OCR com 2 engines (PyMuPDF+Tesseract / PaddleOCR), formatters (`join_pages`, `build_pages_zip`), descoberta automática do binário Tesseract. | `[ocr-cpu]` ou `[ocr-gpu]` |
| `transcricao` | Formatadores TXT/SRT/VTT compartilhados, helpers de timestamp e `Segment` TypedDict. | (nenhum — engine fica nos consumidores) |

## Instalação

Requer **Python ≥ 3.11**.

```bash
pip install labdados-core                       # base (contracts + viabilidade)
pip install labdados-core[estruturacao]         # + DataFrameIt + openai + openpyxl
pip install labdados-core[ocr-cpu]              # + PyMuPDF + pytesseract + Pillow
pip install labdados-core[ocr-gpu]              # + PaddleOCR (GPU)
pip install labdados-core[all]                  # alias para [estruturacao]
```

Para gerar o **PDF** do relatório de viabilidade, instale também o binário do
[Quarto](https://quarto.org) no sistema (com Typst, incluído nas builds
oficiais ≥ 1.4). Sem o Quarto, `render_report()` devolve apenas o markdown.

## Uso

### Análise de viabilidade

```python
from labdados_core.viabilidade import analyze_form, render_report

results = analyze_form({
    "listagem": "datajud",
    "tribunais_selecionados": ["tjsp", "tjrj"],
    "filtro_classes_cnj": "7",
    "recorte_inicio": "2020-01-01",
    "recorte_fim": "2024-12-31",
})

print(results["verdict"])           # "viable" / "caveats" / "unviable"
print(results["total_aproximado"])

report = render_report(
    request_id="abc-123",
    form={...},
    results=results,
    request_meta={"researcher_name": "Fulano", "institution": "FGV", "email": "..."},
)
if report:
    pdf_bytes, md_bytes = report
```

### Estruturação com LLM

```python
from labdados_core.estruturacao import LlmConfig, estruturar
from pydantic import BaseModel

class Decisao(BaseModel):
    procedente: bool
    valor_causa: float | None

config = LlmConfig(
    provider="openai",
    model="gpt-4o-mini",
    api_key="sk-...",
)

results = estruturar(
    ["A demanda foi julgada procedente, com valor de R$ 5.000,00."],
    schema=Decisao,            # ou um JSON Schema dict — converte automaticamente
    system_prompt="Você extrai decisões judiciais.",
    llm_config=config,
)
print(results)  # [{"procedente": True, "valor_causa": 5000.0, "_doc_id": "doc_1"}]
```

`LlmConfig.provider` aceita `"openai"`, `"azure_openai"` ou `"openai_compat"`
(cobre vLLM, Ollama, LM Studio via `base_url`).

### OCR

```python
from labdados_core.ocr import extract, join_pages

pages = extract(
    "documento.pdf",
    modelo="pymupdf-tesseract",     # ou "paddleocr" (precisa [ocr-gpu])
    languages="por+eng",
    dpi=200,
    deskew=True,
)
print(join_pages(pages, output_format="md"))
```

### Formatadores de transcrição

```python
from labdados_core.transcricao import format_segments

segments = [
    {"start": 0.0, "end": 2.5, "text": "Olá."},
    {"start": 2.5, "end": 5.0, "text": "Tudo bem?", "speaker": "SPEAKER_00"},
]
print(format_segments(segments, output_format="srt", with_speaker=True))
```

(O engine de transcrição em si — faster-whisper, WhisperX, pyannote — não
mora aqui; cada consumidor instancia o seu.)

## Por que existe

Antes deste pacote, prompts, formatadores e schemas viviam duplicados no
backend (`escritorio-servicos`) e no SDK (`labdados-sdk`). Bug em um → bug
eventual no outro. Com o core, ambos importam do mesmo lugar e ficam
forçadamente em sintonia. A versão fica pinada nos dois consumidores via
`>=0.x,<0.(x+1)`.

## Versionamento

SemVer com pin estrito de minor enquanto não atinge 1.0:

- **patch** (0.x.**y**): bug fix sem mudança de assinatura.
- **minor** (0.**x**.0): nova função / argumento opcional. Backwards-compat.
- **major** (**x**.0.0): mudança no shape de retorno ou no contrato. Coordenar bump nos dois consumidores.

Ver [CHANGELOG.md](./CHANGELOG.md).

## Licença

[MIT](./LICENSE)
