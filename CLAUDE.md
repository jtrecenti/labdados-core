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
~50MB instalado, lento de resolver via uv/pip. A maior parte dos pedidos
de viabilidade é Datajud (que precisa só de `httpx`) — não vale a pena
pagar esse custo de instalação por padrão. Quem quer jurisprudência ou
sentenças instala `labdados-core[juscraper]`.

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
