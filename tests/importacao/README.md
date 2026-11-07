# Testes de importação (CSV / TXT / XLSX)

100 casos (TC-001 a TC-100) para o fluxo **arquivo → front (PapaParse/SheetJS) → JSON padronizado → n8n/FastAPI**.
A especificação de cada caso, o contrato JSON e as decisões estão em [`docs/testes/casos-de-teste-importacao.md`](../../docs/testes/casos-de-teste-importacao.md).

| Arquivo | Para quê |
|---|---|
| `gerar_fixtures.py` | Gera as entradas (`fixtures/TC-XXX.*`) e os esperados (`fixtures/TC-XXX.esperado.json`) |
| `fixtures/manifest.json` | Índice dos 100 casos: bloco, prioridade, camada, tipo, entradas, esperado, status HTTP, notas |
| `contrato.py` | Contrato em Pydantic (estrito). **Use o mesmo modelo no corpo da rota de importação do FastAPI** |
| `run-front.mjs` | Executor do parser do front (Node, sem dependências) |
| `test_importacao.py` | pytest: integridade das fixtures + casos de API (094–099) |

## Comandos

```bash
pip install -r requirements-dev.txt
python tests/importacao/gerar_fixtures.py              # 105 arquivos (~2 MB, versionados)
python tests/importacao/gerar_fixtures.py --grandes    # + 4 pesados (~170 MB em fixtures/grandes, fora do git)

# Front: o módulo precisa exportar  async function importar({ nome, bytes }) -> JSON do contrato
node tests/importacao/run-front.mjs --parser front/src/importar.mjs
node tests/importacao/run-front.mjs --parser front/src/importar.mjs --prio P0
node tests/importacao/run-front.mjs --parser front/src/importar.mjs --caso TC-059
node tests/importacao/run-front.mjs --self-test        # confere o próprio executor (100 ok)

# API (com a API rodando):
pytest tests/importacao                                                   # integridade
IMPORTACAO_URL=http://localhost:8000/importacao pytest tests/importacao   # + API
```

No Windows (PowerShell): `$env:IMPORTACAO_URL="http://localhost:8000/importacao"; pytest tests/importacao`

## Decisões adotadas nos esperados

Os esperados seguem as sugestões da especificação. **Se o time decidir diferente, mude o caso em `gerar_fixtures.py` e gere de novo.**

| # | Decisão adotada | Casos |
|---|---|---|
| D1 | `.txt` aceito como texto delimitado por tab | 003, 057–066 |
| D2 | `.xls` aceito, `.ods` recusado (`FORMATO_NAO_SUPORTADO`) | 004, 006 |
| D3 | XLSX com várias abas: primeira aba **visível** e **com dados** | 071–073 |
| D4 | Número ambíguo: usa o padrão do resto do arquivo | 035, 036 |
| D5 | Não converte unidades: normaliza a grafia; imperial → `quantidade: null`, `unidade: "ft-in"` + aviso | 040, 041, 063, 069 |
| D6 | Limite de 20 MB e 100.000 itens | 085, 098 |
| D7 | API estrita: `quantidade` string → 422 | 096 |

Regras extras assumidas pelos esperados:
- `categoria` só vem de uma coluna. Nas tabelas do Revit (sem coluna de categoria) é `null`; não é deduzida do título.
- `extras` guarda o valor **bruto**: texto no CSV, número no XLSX. Exceção: moeda (`R$ 1.234,56` → `1234.56`).
- Coluna excedente sem nome vira `coluna_N` (N = posição, começando em 1). Duplicada vira `Nome_2`.
- Cabeçalho em 2 linhas vira `Grupo / Subcoluna`; o grupo se estende para a direita até o próximo.
- SketchUp: linhas `Group` que contêm outras entidades são descartadas; componentes são contados.
- Descrição truncada em 2.000 caracteres.

## ⚠️ Armadilhas encontradas ao validar as fixtures com as bibliotecas reais

Verificado com SheetJS 0.20.3 (CDN) e PapaParse 5.4.1:

1. **A detecção automática de delimitador do PapaParse erra nos `.txt` do Revit em pt-BR.** Valores como `12,50 m²` fazem ela escolher `,` em vez de tab (TC-059, 060, 061, 063, e também TC-046 com `;`). Recomendação: em `.txt`, forçar `delimiter: "\t"`; em `.csv`, contar `;`, `,` e tab **só na linha de cabeçalho** e escolher o mais frequente.
2. **O PapaParse não remove o BOM sozinho no texto decodificado**: tire o `﻿` do primeiro cabeçalho (TC-011).
3. **Codificação:** `TextDecoder('utf-8')` em arquivo Windows-1252 gera `T�rreo` (TC-012). Decodifique como UTF-8 com `{ fatal: true }` e, se der erro, tente `windows-1252`.
4. **SheetJS lê `.ods`** (TC-006). Se a decisão for recusar, recuse pela extensão antes de ler.
5. **Células mescladas** (TC-075): o SheetJS devolve `null` nas células cobertas. Preencha usando `ws['!merges']`.
6. **Aba oculta** (TC-072): consulte `wb.Workbook.Sheets[i].Hidden`.
7. **Arquivo com senha** (TC-081): o SheetJS lança `File is password-protected`. Mapeie para `ARQUIVO_PROTEGIDO`.
8. **Fórmulas** (TC-076/077): use o valor em cache (`cell.v`); erro vem com `cell.t === 'e'`.

## Casos que não são automáticos

- **TC-087:** enviar TC-086 e conferir no Langfuse que o LLM recebe um resumo, não 50 mil itens.
- **TC-090:** além do parser, conferir que a resposta do agente não muda por causa da instrução na célula.
- **TC-093:** checar a dependência do SheetJS (`npm ls xlsx`, `npm audit`).
- **TC-101/102 (extras):** rodar uma exportação **real** do Revit e uma do SketchUp antes da demo.
