# Changelog

Todas as mudanças notáveis neste pacote são documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
versionamento seguindo [SemVer](https://semver.org/lang/pt-BR/) — ver
"Versionamento e compatibilidade" no `CLAUDE.md`.

## [Unreleased]

## [0.7.0] - 2026-05-02

### Mudado
- `labdados_core.estruturacao.estruturar` passa a usar
  [DataFrameIt](https://brunodcdo.com.br/dataframeit/) internamente.
  Ganha paralelização (`parallel_requests=N`), retry com backoff, rate-limit
  detection e structured output via Pydantic — tudo built-in.
- Schema agora aceita **`BaseModel` Pydantic** ou JSON Schema dict
  (convertido em Pydantic dinamicamente via novo
  `schema_utils.ensure_pydantic_model`). A superfície atual do SDK
  (`estruturacao(schema=dict, ...)`) continua funcionando sem mudança
  para o usuário final.
- Novo helper `_llm.to_dataframeit_kwargs(LlmConfig)` mapeia a config
  unificada para os kwargs que `dataframeit()` espera. Mantém OpenAI,
  Azure OpenAI e endpoints OpenAI-compatible (vLLM/Ollama/LM Studio,
  via `provider="openai_compat"` que vira `provider="openai"` +
  `model_kwargs={"base_url": ...}` no LangChain).

### Adicionado
- `schema_utils.ensure_pydantic_model` + `UnsupportedSchema`. Cobre
  `string/integer/number/boolean`, `array` com items simples, `object`
  aninhado, e `enum` (vira `Literal`). Construções avançadas
  (`anyOf/oneOf/$ref`) levantam erro com mensagem útil.
- Novo extra dep `dataframeit[openai]>=0.6` em `[estruturacao]`.
- Tests de integração em `tests/test_estruturacao_integration.py`
  rodam com `OPENAI_API_KEY` real (skipa se ausente). Marker
  `pytest.mark.integration` permite filtrar com `-m "not integration"`.
- `.env` adicionado ao `.gitignore`.

### Mantido (sem mudança de API)
- `call_llm`, `build_messages`, `read_document`, `LlmConfig` continuam
  exportados e funcionando — `services/structuring/main.py` ainda os
  consome diretamente. Migração pra `estruturar()` (que ganha o
  paralelismo) fica para um PR posterior.

## [0.6.0] - 2026-05-02

### Adicionado
- Subpacote `labdados_core.estruturacao` — núcleo compartilhado entre
  `services/structuring` e `labdados.estruturacao` (modo local). Substitui
  os prompts/readers/cliente OpenAI duplicados nos dois lados:
  - `prompts.build_messages(system, text, schema, *, schema_position)` —
    posição do schema configurável (`"user"` default, `"system"` legacy SDK).
  - `_llm.LlmConfig` + `_llm.call_llm(...)` — cliente unificado para
    OpenAI, Azure OpenAI e endpoints OpenAI-compatible (vLLM, Ollama,
    LM Studio). Suporta streaming (necessário no caminho Container Apps
    → vLLM) e `response_format=json_schema` (structured outputs / guided
    decoding) quando há schema válido.
  - `readers.read_document(content, filename, *, csv_text_column)` — lê
    `.txt/.md/.docx/.csv/.xlsx` para `[(doc_id, texto), ...]`.
  - `pipeline.estruturar(textos, *, schema, system_prompt, llm_config)` —
    orquestra read → prompt → LLM → parse. Erros viram `{"_error": ...}`
    no resultado em vez de levantar.
- Novo extra `labdados-core[estruturacao]` (`openai>=1.40`, `openpyxl>=3.1`).

### Notas
- Backend e SDK ainda redefinem essa lógica localmente; consumir o core
  em ambos é a próxima fase (PRs 2/PR 3 do plano).
- Avaliação de [DataFrameIt](https://brunodcdo.com.br/dataframeit/) como
  núcleo futuro está em pausa — issue de discussão em aberto, ver
  `escritorio-servicos/.dev-notes/dataframeit-issue-draft.md`.

## [0.5.0] - 2026-05-02

### Mudado (breaking)
- `requires-python` apertado de `>=3.10` para `>=3.11`. `juscraper` (dep
  direta desde 0.4.0) já exigia 3.11 — o pin antigo não era resolvível.

### Adicionado
- Subpacote `labdados_core.contracts` com Pydantic v2 models compartilhados
  entre backend (`escritorio-servicos`) e SDK (`labdados-sdk`):
  - `contracts.files`: `FileMetadata`, `FileInfo`.
  - `contracts.jobs`: `ProcessRequest`, `ProcessResponse`, `JobStatusResponse`,
    `JobStatus` (enum).
  - `contracts.viability`: `ViabilityForm`, `ViabilityResults`, `Verdict` (enum).
- `pydantic>=2.7` como dependência direta.
- `pytest-cov` em `[dev]` para acompanhar cobertura.

### Notas de migração
- Backend e SDK podem migrar incrementalmente: importar de
  `labdados_core.contracts` no lugar de redefinir cada model. Os schemas são
  superset-compatible com os atuais (adicionam campos opcionais que já
  existiam em alguns lugares e em outros não).

## [0.4.0] - 2026-04

### Mudado
- `juscraper` agora é dependência direta (não mais extra opcional).
  `analyze_form` chama Datajud via `juscraper.scraper("datajud")` em vez
  do cliente HTTP próprio `_datajud.py`. Eliminou ~120 linhas de
  duplicação e o `_DATAJUD_KEY` hardcoded.
- Requer PR
  [jtrecenti/juscraper#180](https://github.com/jtrecenti/juscraper/pull/180)
  (`data_ajuizamento_inicio/fim` em `contar_processos`). Pinado no `main`
  até sair release com `>=0.3`.

### Sem mudança de comportamento
- `analyze_form` e `render_report` ficaram byte-equivalentes ao
  comportamento anterior.
