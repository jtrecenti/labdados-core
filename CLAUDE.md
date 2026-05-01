# CLAUDE.md — `labdados-core`

Núcleo Python compartilhado entre dois repositórios:

- [`escritorio-servicos`](https://github.com/jtrecenti/escritorio-servicos)
  (backend FastAPI + Container Apps + worker)
- [`labdados-sdk`](https://github.com/lab-dados/labdados-sdk)
  (SDK Python externo — `pip install labdados`)

## A regra de ouro

**Só vem pra cá o que precisa ficar byte-equivalente nos dois lados.**

Se uma função é específica de um deles (cliente HTTP do SDK, worker da fila
do backend, FastAPI app, etc.), ela **não** vem. Nem por DRY.

Hoje só a análise de viabilidade está aqui. Conforme aparecer duplicação
genuína, abrir um módulo novo seguindo o padrão de `viabilidade/`:

- pasta com `__init__.py` re-exportando a API pública,
- `analyze.py` (lógica pura) + helpers privados em `_*.py`,
- `templates/<nome>.qmd` se houver render Quarto,
- testes em `tests/test_<nome>.py`.

## O que **não** vem pra cá

- Cliente HTTP do SDK → `labdados-sdk/src/labdados/client.py`.
- Routers FastAPI, `services_catalog`, `email`, `storage` → backend.
- OCR/transcrição/estruturação locais do SDK — são implementações
  **diferentes** das do backend (`services/<svc>/`), não duplicações.
  PaddleOCR + vLLM + Container Apps GPU vivem só no backend; tesseract +
  faster-whisper + ollama vivem só no SDK.

## Versionamento e compatibilidade

Este pacote tem dois consumidores que vivem no GitHub e deployam em
ritmos diferentes (backend deploya em Azure Container Apps; SDK é um
pacote PyPI). Para evitar surpresas:

- **Bumps de patch (0.1.x)**: bug fix, sem mudança de assinatura. Both
  consumers podem atualizar quando quiserem.
- **Bumps de minor (0.x.0)**: nova função/argumento opcional. Backwards
  compatible.
- **Bumps de major (x.0.0)**: mudança no shape do dict de retorno de
  `analyze_form` ou no schema esperado por `render_report`. Coordenar:
  bumpar aqui → bumpar pin nos dois consumidores no mesmo ciclo de
  release.

Os dois consumidores devem **pinar** este pacote em range `>=0.1,<0.2`
até bater 1.0.

## Por que `juscraper` é extra

`juscraper` traz pandas, lxml, beautifulsoup, selenium-via-requests etc.
~50MB instalado, lento de resolver via uv/pip. Hoje, todos os caminhos
de `analyze_form` precisam do juscraper (Datajud via `contar_processos`,
jurisprudência/sentenças via `cjsg`/`cjpg`). Mantemos `juscraper` em
`[juscraper]` para que **outros usos futuros** do labdados-core (que
não envolvam viabilidade) não paguem por essa dep — quem importa
`labdados_core.viabilidade` instala o extra.

## TODO — quando o PR jtrecenti/juscraper#177 for merged

Hoje o `_datajud.py` tem um cliente HTTP próprio que duplica o que o
`juscraper.scraper("datajud").contar_processos()` agora faz nativamente
(PR jtrecenti/juscraper#177). Migração planejada:

1. Bumpar pin: `juscraper>=0.X` (versão que inclui `contar_processos`).
2. Substituir `_datajud.count_for_tribunal()` por chamada a
   `juscraper.scraper("datajud").contar_processos(tribunal=..., ...)`.
3. Apagar `_datajud.py` (e o `_DATAJUD_KEY` hardcoded).
4. Bumpar `_version.py` (minor — sem mudança de assinatura no
   `analyze_form`, mas mudança de dependência).

## Por que o template `.qmd` mora aqui

O template Jinja é parte do contrato: as variáveis que ele consome
(`results.tribunais[*].relation`, `results.verdict`, ...) precisam estar
presentes no dict que `analyze_form` devolve. Manter no mesmo pacote
garante que nunca caímos numa situação de "template antigo + analyze
novo" ou vice-versa.

`importlib.resources.files()` lê o template a partir do wheel — funciona
direto sem precisar dar path absoluto.

## Workflow de mudança

Quando precisar mudar algo aqui:

1. **Mude aqui** (`labdados-core`), com testes.
2. Bumpe `_version.py`.
3. Publique tag → CI publica no PyPI (workflow de release ainda a montar
   — por enquanto `pip install git+https://github.com/lab-dados/labdados-core`).
4. Suba o pin nos dois consumidores em PRs simultâneos.

Não dá pra pular o passo 1 — se você "patchear" diretamente em
`viability_runner.py` ou em `labdados.analise_viabilidade.py`, o outro
lado vai divergir. Sempre passe por aqui.
