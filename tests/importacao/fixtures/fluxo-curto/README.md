# Regressões PDF, DXF, IFC e SKP — 08/11/2026

Arquivos sintéticos, com 1 a 3 linhas de materiais cada (teto do pedido: 10).
Não contêm dados de clientes. Nenhum teste desta pasta precisa de serviço externo.

| Arquivo | Resultado de referência |
|---|---|
| `quadro-fragmentado.pdf` | Sala: Porcelanato 12,5 m² e Tinta 20 m²; a primeira célula é escrita em dois operadores PDF |
| `tabela-quantidade-ausente.pdf` | Cimento 2 un, Areia com quantidade pendente e Rejunte 3 kg; não juntar as duas primeiras descrições |
| `curvas.dxf` | Semicírculo de raio 1: comprimento 3,14 m e área 1,57 m² |
| `unidade-local.ifc` | 12.500.000 mm² declarados em uma quantidade local = 12,5 m², apesar da unidade global ser m² |
| `componentes.skp` | Duas portas e uma cobertura; portas contam 2 un, cobertura exige medida humana |
| `*-envio.json` | Saída de `montarCorpo`, depois de revisão sintética, conservando descrição original, nível e extras |

## Reproduzir sem servidor

Na raiz: `.venv/Scripts/python.exe scripts/gerar_fixtures_fluxo_curto.py` recria PDF, DXF e IFC.

Em `frontend`: `npm test -- src/lib/importar/fluxo-curto.test.ts` confere os arquivos e contratos.
Os testes normais não escrevem arquivos. Para regenerar SKP e contratos intencionalmente,
defina `UPDATE_FLOW_FIXTURES=1` somente durante essa execução e remova a variável depois.

`tests/test_fluxo_arquivos_curto.py` usa esses contratos para testar A/B/C e Excel/PDF em memória,
com preços e banco simulados. Não inicia uvicorn nem acessa o servidor publicado.

Os modelos IFC são amostras STEP mínimas para o leitor, não projetos executivos completos.
O SKP foi criado com OpenSKP; não comprova compatibilidade com todas as versões do SketchUp.
