# Ferramentas existentes do modelo à compra

## Quais produtos já leem projetos e geram orçamentos?

### Takeaway

Já há concorrentes no Brasil que conectam arquivos BIM, quantitativos, orçamento e compras. Os dois mais relevantes para o Orça são OrçaFascio e AltoQi Visus.

### Cited Findings

- **OrçaFascio / OrçaBIM Web** anuncia IFC e RVT no navegador, visualização e seleção de elementos 3D, ligação dos quantitativos a itens de orçamento e vínculo de mais de um modelo ao mesmo orçamento. O Revit não precisa estar instalado para esse fluxo. [OrçaBIM Web](https://www.orcafascio.com/modulos-e-plugins/orcabim-web).
- **OrçaBIM para Revit** funciona dentro do Revit. Seu editor escolhe critérios de categoria, material ou fórmula para quantificar. Vincula os resultados ao orçamento e bases como SINAPI. O fornecedor também anuncia atualização de quantitativos e auditoria de elementos sem vínculo no orçamento. [Documentação de quantificação](https://suporte.orcafascio.com/artigos-suporte/quantificando-elementos-modelados-no-projeto), [produto](https://www.orcafascio.com/modulos-e-plugins/orcabim).
- **Compras OrçaFascio** permite importar insumos do orçamento ou de composições, ajustar quantidades, cotar com fornecedores cadastrados, comparar preços e emitir ordens. A documentação descreve um processo que passa pela aprovação do responsável técnico e pelo setor de compras. **OF IA** anuncia geração de composições com insumos sugeridos e importação de listas em PDF para revisão. Uma página comercial também menciona um agente de cotação, porém não detalha sua operação. [Compras](https://www.orcafascio.com/modulos-e-plugins/compras), [processo de pedido](https://suporte.orcafascio.com/artigos-suporte/criando-um-pedido), [OF IA](https://www.orcafascio.com/modulos-e-plugins/of-ia), [oferta comercial](https://www.orcafascio.com/ofertas-black).
- **AltoQi Visus** recebe modelos IFC, anuncia agentes de IA para auditar informação por elemento contra requisitos do empreendimento, sinaliza não conformidades, liga quantitativos ao 3D, atualiza diante de novas revisões e associa quantidades a composições, bases próprias ou públicas como SINAPI. O Cost Management também documenta trabalho híbrido com planilhas. Alguns planos específicos restringem a origem do IFC. **Visus Bid** pega o orçamento publicado e solicita propostas para insumos/serviços a fornecedores, que podem informar frete, condições e validade. [Visus](https://altoqi.com.br/produtos/visus), [plataforma e fluxo híbrido](https://suporte.altoqi.com.br/hc/pt-br/articles/14192490408343), [limites por aplicação](https://suporte.altoqi.com.br/hc/pt-br/articles/6296874439703), [Visus Bid](https://suporte.altoqi.com.br/hc/pt-br/como-utilizar-solu%C3%A7%C3%A3o-altoqi-visus-bid), [frete na proposta](https://suporte.altoqi.com.br/hc/pt-br/como-acessar-e-utilizar-o-ambiente-do-fornecedor).
- **Autodesk Forma Takeoff + Forma Estimate** mede comprimentos, contagens e áreas em 2D, extrai quantidades em modelos 3D, aplica fórmulas e guarda/exporta snapshots. Estimate associa quantidades a custos, materiais, mão de obra, equipamentos e outras parcelas. O fabricante cita exportação para Excel e outras soluções. [Takeoff](https://construction.autodesk.com/tools/construction-takeoff-software/), [Estimate](https://help.autodesk.com/cloudhelp/ENG/Precon-Estimate/files/est-get-started/What_is_Estimate.html), [snapshots XLS](https://help.autodesk.com/cloudhelp/ENU/Takeoff-Takeoff/files/Snapshot.html).
- **RIB CostX** mede desenhos 2D e BIM, vincula planilhas a desenhos/bases, tem rastreabilidade de revisões, atualização das quantidades e comparação de propostas de subcontratados segundo edição/disponibilidade. [Brochura oficial](https://www.rib-software.com/pdf/en/rib-costx-brochure.pdf).

### Inferences

- Leitura de IFC ou RVT, extração automática, auditoria de lacunas com IA, revisão rastreável e ligar BIM a suprimentos já têm precedentes. O Orça precisa avaliar experiência e economia para o público, e não se apresentar como primeiro produto dessas categorias.

### Gaps

- Páginas de produto e documentação foram pesquisadas, sem teste prático. Não verificados acesso público a APIs de OrçaFascio/AltoQi para terceiros, compatibilidade de toda versão de arquivo, nem ofertas instantâneas com estoque, CEP e substitutos de varejo em cada produto. A menção comercial do agente OF IA de compras não basta para inferir como coleta preços.

## Quais ferramentas cotam e podem se integrar?

### Takeaway

Uma base de referência, uma oferta anunciada e uma proposta de fornecedor são fontes distintas. Já existem integrações reais de cotações e sistemas focados em compras ou no dia a dia de escritórios.

### Cited Findings

- **SINAPI (IBGE e CAIXA)** publica preços de referência de insumos e custos de composições mensalmente. Uma composição é uma receita de custo unitário para executar um serviço, com insumos e mão de obra quando aplicável. É referência de orçamento, não preço firme de um produto com estoque e frete para a obra. [Metodologia oficial da CAIXA, cap. 4](https://www.caixa.gov.br/Downloads/sinapi-metodologia/Livro_SINAPI_Metodologias_Conceitos.pdf).
- **Sienge + Construcompras** é uma integração de mercado documentada. Sincroniza solicitações, cotações, fornecedores e preços. O fluxo aguarda as propostas dos fornecedores, registra comparação e o Sienge cita frete nas propostas. O fluxo atualizado exige contratação, módulo de Suprimentos e pacote de APIs, entre outros pré-requisitos. [FAQ da integração](https://ajuda.sienge.com.br/support/solutions/articles/153000221303), [pré-requisitos e permissões](https://ajuda.sienge.com.br/support/solutions/articles/153000246439-solicitac%C3%A3o-de-compras-integrac%C3%A3o-construcompras-x-sienge), [frete nas propostas](https://sienge.com.br/blog/como-integrar-construcompras-e-sienge/).
- **Corbi** anuncia um agente de compras que recebe lista por texto, áudio, foto ou planilha, pede propostas a fornecedores, compara preço/prazo, confere especificações com apoio técnico e acompanha a entrega após aprovação. A página não documenta leitura de BIM. [Corbi](https://corbi.com.br/).
- **ConstruOferta** anuncia que aceita lista ou projeto por WhatsApp/app, busca fornecedores e compara preço, prazo e pagamento. Descreve serviço de assessoria + plataforma, sem evidência pública ali de quais formatos BIM lê ou se automatiza o levantamento. [ConstruOferta](https://www.construoferta.com.br/).
- **MalhaPop** anuncia um fluxo muito próximo para uma categoria: lê projeto estrutural em PDF/imagem ou lista para obter bitolas, peso e quantidades de aço. Preço firme vem após fornecedor confirmar disponibilidade e frete para o CEP. [Formulário e descrição](https://malhapop.com.br/orcamento-ia).
- **Nurbie**, direcionado também a escritórios brasileiros, registra produtos, embalagens, frete e ofertas, compara por item e guarda histórico e aprovação de compra. Seu FAQ descreve cadastro de fornecedores e registro de ofertas pelo usuário e informa que não captura preço por link de loja. [Nurbie](https://nurbie.com.br/solucoes/cotacao).
- **Programa**, focado em interiores, transforma URL de fornecedor em ficha de produto, registra especificações de móveis/acabamentos e oferece orçamento e aprovação pelo cliente. O fluxo documentado parte de links/listas/biblioteca, sem demonstração ali de extração BIM. [Programa](https://programa.design/specifications-with-programa).

### Inferences

- Sim, é possível combinar componentes existentes. Um arranjo de menor dependência é leitor IFC/planilha → lista estruturada e revisável → catálogo/planilha de ofertas ou integração oficial de cotação → relatório. Produtos de terceiros só entram em produção após confirmar formatos, endpoints, contratos, licenças e permissões. Nem toda funcionalidade de interface pode ser acionada por API.
- Proposta de valor a testar: pequenos escritórios de interiores/residencial, recorte de pisos e revestimentos, importar revisão de projeto, explicar origem da quantidade e pergunta de alto impacto, transformar em caixas, mostrar alternativa comprável em uma região dentro do teto preservando exigências e escolhas aprovadas. Testar caso real ou sintético equivalente contra OrçaBIM Web/Visus e fluxos de compras, medindo minutos, correções, cobertura real e fonte de cada item. Revisão, auditoria, aprovação e cotação existem isoladamente, e a combinação como diferencial comercial segue hipótese.
- Uma estimativa de frete modelado deve ser marcada como estimativa. Cesta com frete de verdade depende do vendedor, CEP, quantidade, estoque, peso, mínimo de compra e condições vigentes. Uma oferta anunciada por loja tem menos certeza que proposta confirmada.

### Gaps

- Não foi feita demonstração prática dos fornecedores nem verificada a cobertura de cada rede no CEP do protótipo.
- Não foi demonstrado por pesquisa documental que o recorte proposto seja único. Pode haver outras soluções ou combinações equivalentes, e páginas comerciais podem omitir recursos.
