# Orça — roteiro dos exemplos para os jurados

Todos os arquivos representam obras fictícias. As quantidades são sintéticas e nenhum arquivo contém preço, loja ou resultado previamente aprovado. A pesquisa continua consultando as fontes configuradas; encontrar um produto depende da disponibilidade dessas fontes.

## Comece por teste_1.csv, .xlsx, .txt ou .pdf

Os quatro formatos trazem os mesmos cinco materiais: 6 tomadas Tramontina Liz brancas 20A, 4 spots Stella 7W 3000K, 8 joelhos Tigre soldáveis 25mm, 40 kg de argamassa Quartzolit AC-III cinza e 18 L de tinta Suvinil Toque de Seda Branco Neve.

1. Importe e confira os cinco itens. Não há erro intencional de quantidade ou unidade.
2. Informe nome, CEP da obra fictícia e orçamento disponível. Esses dados não estão embutidos no arquivo.
3. Revise os complementos sugeridos. Para uma demonstração curta, aceite apenas os pertinentes e mantenha no máximo dez itens; não é necessário aceitar todos.
4. Envie para pesquisa. Observe as fontes diretas, as especificações, a faixa de preço, o número de embalagens e o consumo informado.
5. Abra uma fonte e compare produto, embalagem e valor. A demo mostra o preço de venda lido na própria página. Se só houver parcela, cupom, valor ambíguo ou se a página estiver indisponível, o preço não é confirmado. Se a loja atualizar o valor depois, use **Pesquisar de novo** para consultar a página novamente.

## Teste 2: revisão antes da pesquisa

CSV, Excel, TXT e PDF têm cinco itens. A tomada foi propositalmente escrita em m²: a revisão deve sugerir `un`, mantendo a quantidade 4. A tinta é genérica e deve pedir marca/linha e demais detalhes. O porcelanato e a tinta devem produzir sugestões de complementos.

Aceite a correção da tomada, examine até três complementos e complete a tinta com as especificações que o usuário escolher. Por exemplo, para exercitar a repesquisa, use a descrição da tinta do teste 1; isso é uma escolha para o exemplo, não uma decisão automática do sistema.

## Modelos DXF, IFC e SKP

| Arquivo | O que observar |
|---|---|
| teste_1.dxf | Três tipos de bloco especificados: 4 spots, 8 joelhos e 1 lata de tinta. A contagem de instâncias vira quantidade de compra. |
| teste_2.dxf | Piso com 18 m², rodapé com 18 m, 2 portas e 4 pontos elétricos. Descreva o material: “ponto elétrico” não informa sozinho qual produto comprar. |
| teste_1.ifc | Cinco tipos de componente com contagens 6, 4, 8, 2 e 1. Os últimos são sacos de 20 kg e lata de 18 L, não kg e litros diretamente. |
| teste_2.ifc | Porcelanato com 18 m² e tinta com 30 m² declarados; tomada em unidades. Observe também pavimento e referências da origem. |
| teste_1.skp | Cinco definições de componente com contagens 6, 4, 8, 2 e 1, equivalentes à lista de componentes. |
| teste_2.skp | Um piso sem área declarada, três componentes especificados e uma torneira genérica. Informe **18 m²** para o piso como dado sintético deste roteiro; depois revise complementos e especifique a torneira. |

Os modelos são esquemáticos para demonstrar leitura de dados, não projetos executivos. O DXF contém blocos e geometria simples; o IFC contém nomes e quantitativos; o SKP contém componentes de geometria simplificada. A geometria de um componente SKP não define sua área de compra.

## Arquivos MODELO

São padrões para adaptação. Nas tabelas, edite descrição, quantidade, unidade e categoria. No SKP, confira se uma instância corresponde a uma peça, um saco ou uma lata. No IFC, preserve as quantidades base. No DXF, mantenha a unidade do desenho e nomes úteis de blocos e camadas.

## O que já foi verificado

Leitura pelos importadores reais do site, contagens e unidades, correção da tomada, identificação dos itens genéricos, sugestões de complementos e cálculo com ofertas exclusivamente simuladas nos testes. A pesquisa real, disponibilidade das lojas, CEP e serviços externos não foram retestados nesta preparação, respeitando o pedido de não testar em servidor.
