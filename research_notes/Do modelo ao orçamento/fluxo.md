# Fluxo de extração, revisão e orçamento do Orça

## Que programa lê o arquivo e como transformar isso em itens?

### Takeaway

Um importador converte o projeto em registros que o Orça sabe revisar. O mesmo contrato de itens recebe dados de IFC, DXF ou tabela, cada qual por seu leitor.

### Cited Findings

- IfcOpenShell oferece funções para consultar elementos, tipos, materiais, contêiner espacial, propriedades e quantitativos presentes no IFC. Os conjuntos de propriedades e quantidades são acessíveis separadamente. [API de elementos do IfcOpenShell](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/element/index.html)
- A biblioteca oferece ferramentas para obter e converter unidades do modelo e processar a geometria em vértices, arestas e faces quando necessário. Processar geometria fornece formas e coordenadas. O importador precisa aplicar o critério de medição apropriado. [Unidades do IFC](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/unit/index.html), [Processamento de geometria](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html)
- A especificação IFC4 distingue a área bruta do revestimento da área líquida, que desconta as aberturas. Um mesmo número ou área lida de outra entidade pode medir uma coisa diferente. O Revit tem opção de incluir quantitativos base na exportação IFC. [Quantidades do revestimento no IFC4](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcsharedbldgelements/qset/qto_coveringbasequantities.htm), [Configuração IFC do Revit](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-DocumentPresent/files/GUID-E029E3AD-1639-4446-A935-C9796BC34C95.htm)
- O ezdxf lê referências de blocos, nomes, posições e atributos quando existem. Também expõe a indicação de polilinha fechada. A unidade precisa ser determinada pelo contexto do desenho. [Blocos e atributos](https://ezdxf.readthedocs.io/en/stable/blocks/insert.html), [Polilinhas](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html), [Unidades DXF](https://ezdxf.readthedocs.io/en/stable/concepts/units.html)
- Uma tabela de levantamento de materiais do Revit permite listar materiais de elementos do modelo. A Autodesk documenta possíveis discrepâncias para certas condições de paredes. [Levantamento de materiais do Revit](https://help.autodesk.com/cloudhelp/2023/ENU/Revit-DocumentPresent/files/GUID-F8270A42-CA71-46C7-B145-85EC2CB8E4A1.htm)

### Inferences

- IFC como primeiro caminho, usando Python/IfcOpenShell. Importar apenas categorias definidas inicialmente. Contar ocorrências de porta em vez de tipos e usar a área do acabamento identificado conforme o critério de medição acordado. Nunca somar a área da laje e do acabamento como duas áreas do mesmo piso. Se faltar o quantitativo, calcular pela geometria apenas se a regra para essa categoria estiver implementada e validada. Caso contrário, encaminhar a medida para revisão.
- DXF em etapa posterior e condicionado a convenções. Contar referências reais de blocos no espaço de modelo e usar apenas as camadas selecionadas, com unidade conferida e polilinhas fechadas para áreas. Validar contornos internos/recortes quando suportados, bloco aninhado, referência externa e planta duplicada em uma prancha. Caso o desenho só contenha linhas ou código P01 sem significado, pedir seleção/correspondência ou complementar com tabela de esquadrias/memorial. Um leitor identifica a entidade linha ou bloco. A regra do Orça identifica quando aquilo representa uma porta.
- Proposta de registro de entrada para a A. Categoria, descrição original, quantidade, unidade, pavimento/ambiente se disponível, especificações, procedência e pendências. Procedência por campo com distinção entre lido no arquivo, calculado por regra, informado pelo usuário, estimado. Guardar versão do arquivo e chave de origem, por exemplo GlobalId do elemento IFC, identificador da entidade DXF com versão do desenho ou linha da tabela. Ao agrupar itens, manter os elementos de origem e só juntar especificações compatíveis.
- O leitor roda no backend e devolve rascunho revisável. O modelo de linguagem recebe o registro normalizado. Uma função Python aplica critérios de medição, unidades, agrupamento, consistência e contas. A IA pode sugerir categoria a partir da descrição e formular a pergunta, pesquisar fontes e comparar descrições de produtos. Uma categoria inferida fica marcada para validação se for ambígua.
- Validação proposta com modelo sintético do Revit, quantidades base no IFC, tabela do mesmo modelo e escopo controlado, inclusive fase e elementos vinculados. Conferir 8 portas com seus IDs e 48 m² de acabamento aplicando o mesmo critério na referência. Cobrir uma especificação ausente, um item duplicado ou fora de escopo, e uma medida com unidade incorreta. Definir tolerância para áreas, registrar divergências e evitar assumir igualdade entre métricas com definições diferentes.

### Gaps

- Nenhum modelo de exemplo foi executado nesta pesquisa. Classes, propriedades, unidades e cobertura reais precisam ser confirmadas no primeiro arquivo exportado. Estabilidade de identificadores entre exportações também exige teste.

## Como identificar pendências e encaixar as fatias?

### Takeaway

A comparação entre os campos de uma linha e as exigências da sua categoria gera as pendências. Separar o que bloqueia a quantidade, o que bloqueia a seleção do produto e o que bloqueia entrega ou total.

### Cited Findings

- A divisão do time prevê classificação única antes da busca, revisão por regras Python, intervalo estimado e pergunta para item genérico, repesquisa do item depois da resposta, fontes e quantidade por embalagem, e logística/viabilidade. [Divisão do time](../../FATIAS-DO-TIME.md), [Contratos B/C](../../CONTRATOS-B-C.md)
- A orientação de importação já prevê a mesma representação revisável, preservar origem da linha/página e exigir informação adicional para converter área, massa ou embalagem. [Skill de importação do Orça](../../skills/06-material-import.md)

### Inferences

- Regra global por obra. Pedir CEP uma vez para análise de entrega e frete. Pedir teto para comparar com o orçamento do cliente. A quantidade do modelo e uma cotação preliminar de preço podem ser calculadas sem CEP se o fornecedor não o exigir, mas disponibilidade, frete e comparação final ficam pendentes quando faltar o dado correspondente.
- Regra por categoria. Primeiro validar quantidade positiva e unidade, depois avaliar as especificações que alteram a escolha. Para piso, perguntar uso interno/externo e característica relevante ausente, como tamanho, acabamento ou antiderrapância quando exigida pelo uso. Marca é necessária se o cliente exigir uma específica. Se a especificação completa existe em memorial/legenda vinculada, aproveitar a fonte e perguntar apenas o que continuar em aberto. Agrupar pendências de itens com mesmo tipo e permitir revisão.
- Exemplo fictício. Leitor encontra 48 m² de revestimento no elemento do banheiro. A quantidade pode estar pronta enquanto o produto está pendente. Pergunta na tela: “Este revestimento é para o piso do box ou para a parede?” O campo confirmado aciona nova pesquisa apenas das linhas atingidas. Para um produto aprovado que cobre 2 m² por caixa, com 10% de perda assumida e explicitada para a demo, 48 × 1,10 = 52,8 m², arredondar 52,8 ÷ 2 para cima dá 27 caixas. A perda é premissa ajustável, e cobertura vem da embalagem ofertada.
- Uma área/unidade ausente ou incompatível bloqueia cálculo de quantidade. Especificação aberta permite estimativa com fonte e ressalva, sem apresentar um SKU como confirmado. Preço sem fonte fica pendente. Estoque, frete e prazo dependem de consulta ao fornecedor ou regra informada, com data e indicação de verificado/estimado. Verificar que a página refere a mesma variante, unidade e embalagem. Um link com preço não prova estoque ou frete para aquele CEP. Distinguir oferta anunciada de cotação formal e apresentar subtotal dos itens cotados separado do que ainda falta. Evitar mostrar orçamento como aprovado se o escopo estiver incompleto.
- A recebe arquivo, extrai, normaliza, aplica validação única e apresenta tabela para confirmação; C pode gerar complementos sugeridos, com aceite. B consulta ofertas e verifica correspondência, preço e embalagem, registra fontes e converte em número de caixas por regra. C usa os resultados para complementar o escopo, estimar entrega e comparar alternativas ao teto. Esse desenho aproveita a divisão existente e adiciona leitores ao começo. Revisão entre versões exige nova responsabilidade combinada.
- Para demo, usar duas versões sintéticas do mesmo projeto, mesmas opções de exportação e IDs verificados. Por exemplo, 48 m² passa a 54 m², cobertura e perda constantes, de 27 a 30 caixas. Congelar preço para isolar alteração de projeto, então mostrar atualização do total e alternativa compatível com especificação/teto. Separar mudanças de preço em nova cotação e solicitar conferência se correspondência de elemento entre versões for duvidosa.

### Gaps

- Não foram verificadas APIs, estoque real ou termos específicos de fornecedores nesta subpesquisa. Regra de entrega da C é previsão do projeto, sem validação para um fornecedor real.
- O briefing inicial fixa um comportamento de integração, mas o estado executável da aplicação e os contratos finais não foram testados nesta pesquisa.
