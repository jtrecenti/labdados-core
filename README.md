# labdados-core

Núcleo Python compartilhado entre o **backend** do escritório de apoio do
LabDados ([`escritorio-servicos`](https://github.com/jtrecenti/escritorio-servicos))
e o **SDK Python** ([`labdados-sdk`](https://github.com/lab-dados/labdados-sdk)).

## O que mora aqui

Apenas a lógica que precisa ficar **idêntica nos dois lados** (sem HTTP, sem
autenticação, sem armazenamento). Hoje:

- `labdados_core.viabilidade` — análise de viabilidade de levantamento de
  dados (Datajud + juscraper) e renderização do relatório PDF/MD.

Outras módulos podem ser adicionados conforme aparecer duplicação real entre
o backend e o SDK.

## Instalação

```bash
pip install labdados-core               # base — só Datajud + render markdown
pip install labdados-core[juscraper]    # + jurisprudência / sentenças
pip install labdados-core[all]          # tudo
```

Para gerar o **PDF** do relatório, instale também o binário do
[Quarto](https://quarto.org) no sistema (com Typst — incluído nas builds
oficiais ≥ 1.4). Sem o Quarto, `render_report()` devolve apenas o markdown.

## Uso

```python
from labdados_core.viabilidade import analyze_form, render_report

results = analyze_form({
    "listagem": "datajud",
    "tribunais_selecionados": ["tjsp", "tjrj"],
    "filtro_classes_cnj": "7",
    "recorte_inicio": "2020-01-01",
    "recorte_fim": "2024-12-31",
})

print(results["verdict"])                # "viable" / "caveats" / "unviable"
print(results["total_aproximado"])

# Renderiza PDF + MD (precisa Quarto pra gerar PDF)
report = render_report(
    request_id="abc-123",
    form={...},
    results=results,
    request_meta={"researcher_name": "Fulano", "institution": "FGV", "email": "..."},
)
if report:
    pdf_bytes, md_bytes = report
```

## Por que existe

O backend usa essa lógica em `viability_runner.py` quando o admin dispara a
análise. O SDK usa a **mesma** lógica em `analise_viabilidade.py` quando o
usuário pede `local=True`. Antes deste pacote, o código estava duplicado nos
dois lugares — bug em um → bug eventual no outro.

A regra geral: tudo que precisa ficar **byte-equivalente** entre os dois
lados vem pra cá. Tudo que é específico de um (ex: cliente HTTP do SDK,
worker da fila do backend) **não** vem.

## Licença

[MIT](./LICENSE)
