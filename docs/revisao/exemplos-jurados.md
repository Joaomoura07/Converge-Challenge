# Exemplos para os jurados — 08/11/2026

Os três atalhos da entrada agora carregam cinco itens cada, substituindo as listas de 47, 53 e 33 itens na apresentação. O acervo anterior continua disponível para os testes históricos.

Foram refeitos os 21 arquivos de `/exemplos/demo`: MODELO, teste_1 e teste_2 em CSV, Excel, TXT, PDF, DXF, IFC e SKP. Os testes têm de três a cinco itens. `componentes.csv` alimenta o terceiro atalho. Nenhum desses arquivos contém cotações ou resultados de pesquisa pré-preenchidos.

O teste 1 tem especificações para observar a pesquisa e a lista de compra. O teste 2 permite observar revisão, complementos e perguntas ao arquiteto. Planilhas e PDFs incluem uma tomada propositalmente em m²; o SKP inclui um piso sem medida de compra. Os arquivos IFC e DXF preservam áreas e contagens de acordo com seus dados, sem introduzir erros artificiais de unidade em elementos do modelo.

O roteiro público `frontend/public/exemplos/demo/ROTEIRO.md`, também disponível para download na interface, informa os quantitativos e passos esperados. Orienta aceitar apenas os complementos pertinentes, mantendo no máximo dez itens na apresentação. Os modelos são esquemáticos e não são projetos executivos.

## Validação

- Leitura dos 21 arquivos pelos importadores reais do frontend, com conferência de limites e pendências documentadas.
- Fixture extraída dos arquivos comparada nos testes; quantitativos independentes garantem que 40 kg da lista não sejam confundidos com dois componentes de saco de 20 kg.
- 36 verificações de exemplo no backend: materiais especificados, correção da tomada, complementos, itens genéricos e cálculo com duas ofertas sintéticas por material.
- Suíte completa: **967 aprovados, 16 ignorados e 16 testes reais excluídos**; inclui TypeScript e testes do frontend. Conexões Python externas bloqueadas e tracing desativado.
- PDFs dos dois percursos renderizados e inspecionados visualmente. Planilhas têm cabeçalhos, filtros, congelamento da primeira linha e comentários sobre a origem sintética dos quantitativos.
- Build Next.js local aprovado. PDF, SKP e Excel marcados como binários no Git para preservar seus bytes em Windows e Linux.

Sem servidor iniciado, chamadas reais de pesquisa, `check_setup` ou migração de produção. O resultado das fontes ao vivo não foi verificado nesta rodada e depende dos serviços configurados. Os valores de teste ficam exclusivamente nos testes automatizados, não nos arquivos para os jurados.

## Regeneração

Fonte dos dados: `docs/arquivos-teste/demo-jurados.json`. Executar `python -m scripts.gerar_demo_jurados` e `node scripts/gerar_demo_skp.mjs` na raiz. Em `frontend`, rodar `npm test -- src/lib/demo/exemplos.test.ts` com `ATUALIZAR_FIXTURE_DEMO=1` e depois repetir sem essa variável. Os geradores precisam de ReportLab/openpyxl no Python e da dependência openskp já fixada no frontend.
