# Releasing `labdados-core`

Procedimento para publicar uma nova versão no PyPI.

## Pré-requisitos (uma vez só)

1. **Trusted Publisher no PyPI** (necessário antes da PRIMEIRA release):
   - Acesse <https://pypi.org/manage/account/publishing/> logado como mantenedor.
   - Em "Add a new pending publisher", preencha:
     - PyPI Project Name: `labdados-core`
     - Owner: `lab-dados`
     - Repository: `labdados-core`
     - Workflow filename: `release.yml`
     - Environment name: `pypi`
   - Salvar. Após o primeiro upload bem-sucedido, vira "Trusted Publisher" normal.
2. **GitHub Environment**: criar environment `pypi` em
   `Settings → Environments → New environment` (no repo). Sem proteções é OK,
   ou exigir branch `main` + review se quiser dois passos.
3. **`juscraper>=0.3` no PyPI**: a v0.2.1 atual não tem o PR #180 (merged em
   2026-05-01). Sem juscraper 0.3, o `pyproject.toml` continua com
   `juscraper @ git+https://...` e o **PyPI rejeita o upload** (direct refs
   proibidos em metadata). Cortar release nova do juscraper antes desta.

## Release

1. Trocar a dep direta:
   ```diff
   - "juscraper @ git+https://github.com/jtrecenti/juscraper@main",
   + "juscraper>=0.3,<1.0",
   ```
   Pode-se remover `[tool.hatch.metadata] allow-direct-references = true`
   depois (não há mais direct refs).
2. Bump em `src/labdados_core/_version.py` e duplicar em `pyproject.toml`
   (`version = ...`).
3. Mover o conteúdo de `[Unreleased]` para uma nova seção `[X.Y.Z] - YYYY-MM-DD`
   no `CHANGELOG.md`.
4. `uv run pytest -m "not integration"` — confirmar que CI passa.
5. Commit + tag:
   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```
6. O workflow `release.yml` dispara no push da tag, builda sdist+wheel e
   publica no PyPI via OIDC. Acompanhar em
   <https://github.com/lab-dados/labdados-core/actions>.

## Smoke test pós-release

```bash
pip install labdados-core==X.Y.Z
python -c "import labdados_core; print(labdados_core.__version__)"
```

## Em caso de problema

- Se a versão for publicada errada, **não dá pra apagar** — só `yank` (PyPI
  marca como inviável para nova install, mas instalações antigas continuam).
  Lance uma versão patch.
- Para testar antes do real: aponte o workflow para TestPyPI primeiro
  (`repository-url: https://test.pypi.org/legacy/` no step de publish).
