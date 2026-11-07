# Orça AI — contexto para o Claude

**Projeto:** Orça AI, também chamado Orçamentista Autônomo. **Atualizado em 7 de novembro de 2026.** Este resumo reúne as conversas do projeto, as sessões locais do Claude Code, a memória do Obsidian e o estado do repositório. O pedido sobre o formulário está reservado para o fim deste texto.

## 1. Produto, público e problema

O Orça AI é um agente de orçamentação de materiais para arquitetos e escritórios de arquitetura no Brasil. Depois de projetar uma obra, o arquiteto tem uma lista de quantitativos e costuma pesquisar manualmente em várias lojas, conferir se os produtos são equivalentes, converter a quantidade da obra em unidades de compra, calcular frete e estimar se as escolhas cabem no orçamento do cliente. A hipótese de produto é poupar esse trabalho e tornar a estimativa verificável. Ela pode ajudar o arquiteto tanto a ajustar o projeto quanto a preparar uma lista de compra ou negociar com fornecedores.

O produto nasceu de uma conversa sobre ideias de agentes para startups. O primeiro rascunho falava em receber CSV ou Excel pelo Drive ou n8n e devolver um PDF. Nas conversas seguintes, o recorte evoluiu para um aplicativo web próprio, com revisão humana, pesquisa rastreável, comparação de lojas e relatório. Drive e n8n foram opções discutidas na fase de ideia. A arquitetura adotada no plano é site → FastAPI → agente e serviços. Também foram discutidas funcionalidades de comparação com propostas recebidas, versões e metas de custo, como possibilidades de evolução. O escopo da entrega é o definido na divisão do time.

A frase que guia a demo é “Ele pegou meu erro, lembrou do que eu esqueci, me disse o que comprar, onde comprar e se cabe no orçamento do cliente, e mostra de onde tirou cada preço.” O recorte é a estimativa e o plano de compra de materiais. Se faltar preço, especificação, estoque ou frete, o dado deve aparecer como pendente quando for relevante para a estimativa. Exemplos e valores do protótipo são sintéticos.

## 2. Jornada do arquiteto

1. Abre **Nova obra**, informa nome da obra, CEP e orçamento do cliente em reais.
2. Importa materiais, escolhe um dos três exemplos planejados ou monta a lista diretamente no site. O Revit é uma origem dos quantitativos. A pessoa exporta a tabela do software e traz o arquivo delimitado para o Orça. A Fatia A prevê CSV, Excel, TXT tabulado do Revit e PDF com texto selecionável.
3. Confere a tabela editável. O cadastro manual permite digitar material, especificação quando disponível, quantidade e unidade, e adicionar ou remover itens. Importação e cadastro chegam à mesma revisão. A lista editada deve ser preservada ao alternar de modo e ao recuperar uma falha.
4. Vê avisos sobre unidade incompatível, quantidade fora do plausível, duplicatas ou colunas trocadas. Também pode receber sugestões de complementos, como argamassa e rejunte para porcelanato. Cada correção ou complemento exige um clique de **Aceitar**. Uma edição invalida sugestões calculadas para uma versão anterior da lista.
5. Clica em **Enviar para a IA**. Os itens aparecem conforme a pesquisa avança. Um material vago pode gerar uma pergunta objetiva, por exemplo “Qual acabamento e litragem da tinta?”. Quando o arquiteto responde, o item volta para a pesquisa.
6. Consulta a faixa de preços por item, conversão em embalagens com perda, imagens, confiança e links das lojas. Vê a estratégia de compra, comparação entre loja única e compras divididas com frete pelo CEP, e se o total cabe na verba. O plano também prevê ganho de tempo, custo de IA e exportação em Excel/PDF.

**Regras de produto.** Todo preço apresentado precisa de fonte, inclusive um preço estimado. Quando não houver evidência suficiente, o item pode ficar sem preço ou com uma pergunta. Correções, complementos e substituições são sugestões para aprovação humana. A quantidade estimada de um complemento e o preço estimado de um item têm significados diferentes. Uma caixa de 2 m², por exemplo, exige arredondar para 31 caixas para cobrir 60,5 m² antes de qualquer perda adicional. A demo do Figma usa esse tipo de conversão com valores fictícios.

## 3. Design e decisões sobre o protótipo

- Samuel aprovou a direção **caderno de materiais digital** para todas as interfaces. Fundo de papel claro, títulos editoriais, azul cobalto para ações e seleção, divisórias finas, amostras dos materiais e informação técnica em destaque. A ideia é ter a aparência de uma ferramenta de escritório de arquitetura. Para carregamento dos itens, a divisão do time propõe cota tracejada e hachura de 45 graus.
- A navegação inclui **Projetos**, **Importar materiais**, **Revisar materiais**, **Pesquisa**, **Estimativa**, **Fontes e fornecedores**, **Digitar materiais no site** e **Documento de orçamento**. O **Acervo** era um catálogo demonstrativo do protótipo inicial. Samuel pediu a retirada e a entrada manual de materiais, ambas verificadas no protótipo atualizado.
- A preferência final é **oito telas lado a lado no mesmo canvas e arquivo**, em grade de duas fileiras de quatro. A organização temporária em páginas ou arquivos separados foi superada. As oito telas atuais são prévias em camadas de código interativas. Foi verificado no Figma que elas abrem juntas. Foram validados no protótipo o cadastro manual, decimais com vírgula, inclusão e remoção, alternância CSV/manual, revisão e estimativa simulada. [Canvas final com as oito telas](https://www.figma.com/design/ne5wG1A5f5EahJaBfp8LkG?node-id=0-1&p=f)
- Para navegar o fluxo como aplicativo, existe uma camada interativa separada com CSV, entrada manual e pesquisa simulada. As fontes e os preços desse protótipo são fictícios e o código do produto segue seu próprio plano. [Prévia navegável do Orça](https://www.figma.com/design/F8WbWoo1r5jbfhu9ZQMSMl?node-id=15-3&autoplay-code-preview=15-3)

## 4. Divisão atual do time

| Fatia | Responsável | Entrega |
| --- | --- | --- |
| **A — Entrada e revisão** | **Samuel** | Nova obra, cadastro manual, importadores, três exemplos, tabela editável, revisor E1, aceite de correções e complementos, `classificar_item()`, `revisar_itens(itens)`, `POST /revisao/sugestoes`, `POST /orcamentos`, SQL único das quatro tabelas e esqueleto do resultado com `useOrcamento(id)`. |
| **B — Pesquisa agêntica** | **Enzo** | `pesquisar_orcamento(id)`, checagem de produto e preço, fontes, imagens e confiança, cálculo de embalagens com perda, perguntas de especificação, `repesquisar_item(item_id)` e componente `ItemRow`. Ao final, aciona os cálculos da C. |
| **C — Complementos e resultado** | **João** | `sugerir_complementos(itens)`, cadastro de lojas, logística e frete, viabilidade contra o orçamento do cliente, ganho de tempo, exportação e componentes de resultado. |
| **D — Negócio e apresentação** | A definir no documento do time | Mercado, validação com arquitetos, modelo de cobrança, métricas, roteiro, slides, vídeo e submissão. |

Essa divisão de 07/11 substitui a anterior, que atribuía a criação das tabelas a João. Samuel consolida o SQL de `orcamentos`, `orcamento_itens`, `cache_precos` e `fornecedores`. João cadastra as lojas e mantém a lógica da C. A meta informada por Samuel era terminar a Fatia A até a noite de 07/11.

As funções essenciais E1–E11 cobrem revisão, itens esquecidos, embalagens com perda, pesquisa e nova tentativa, perguntas, fonte/confiança, frete, viabilidade, exemplos, ganho de tempo e exportação. Pedidos de cotação por loja e similares técnicos são extensões se houver tempo. O plano prevê acompanhamento por Realtime na A, com acabamento opcional de contador de progresso e detalhes da pesquisa na B. SINAPI, memória de marcas do escritório e integração a ERPs ficaram como ideias para o pitch.

## 5. Arquitetura e contratos relevantes

- **Interface:** Next.js + TypeScript em `frontend/`, escolha de Samuel registrada após o diagnóstico. Figma é a referência de interface. Importadores alimentam uma estrutura comum, com IDs estáveis por linha, preservação das edições, mensagens por campo e validação novamente na API. O plano usa PapaParse para CSV e TXT, força tab no Revit, trata CSV UTF‑8 e Windows‑1252, usa SheetJS do CDN oficial para Excel e prevê PDF.js para PDF com texto. Limites de arquivos, formatos exatos de Excel e amostras dependem do contrato e dos testes.
- **API e execução:** FastAPI/Pydantic e Python. `POST /revisao/sugestoes` reúne `{erros: [...], complementos: [...]}`. As regras do revisor E1 são Python, com LLM para redigir quando aplicável. `classificar_item()` é uma função única da A. B confirma e C lê. A classificação do material e o status da pesquisa são campos de significado distinto.
- **Envio:** `POST /orcamentos` valida e salva orçamento e itens em uma transação, com os itens em `buscando`. A requisição aguarda `pesquisar_orcamento(id)` da B, em vez de depender de execução após a resposta do ambiente serverless. A interface usa um UUID gerado antes do envio para acompanhar o orçamento com `useOrcamento(id)`, enquanto o POST segue aberto. Mesmo UUID e conteúdo recuperam o orçamento existente. Mesmo UUID com conteúdo diferente deve gerar conflito. Estados de item acordados: `buscando`, `definido`, `pendente_especificacao`, `nao_encontrado` e `erro`.
- **Pesquisa:** Python com loop ReAct e tool calling via Featherless, modelo principal `zai-org/GLM-5.2` e `Qwen/Qwen3-32B` para conferência rápida/reserva no plano da B. Tavily faz a busca planejada, DuckDuckGo é a contingência e o cache no Supabase tem validade planejada de sete dias. B confere produto, embalagem e preço, refaz a busca até duas vezes quando necessário e calcula mínimo, mediana e máximo. `fontes` guarda loja, domínio, URL, preço por embalagem e embalagem. Cache vencido deve indicar a data quando usado. O Langfuse registra iterações, ferramentas, custo e latência, com um trace por orçamento e spans por item no plano da B.
- **Persistência e resultado:** Supabase para dados e Realtime nas tabelas de orçamentos e itens. A chave de serviço fica no backend. A leitura pública prevista no SQL local é restrita ao contexto da demo com dados sintéticos. C cruza domínio normalizado da loja e CEP com o cadastro de fornecedores, usando cálculo de frete e viabilidade em Python. A forma de expor na tela os cálculos que João faz na hora ainda precisa ser acertada.
- **Ambiente:** Docker Compose foi usado para executar e testar a API localmente em `localhost:8000`, com Swagger em `/docs`. Vercel é o destino de hospedagem discutido para site/API, sujeito à configuração e ao tempo de execução efetivo. Docker local e deploy são etapas separadas. Featherless fornece a API de modelos. Loop, ferramentas, memória de negócio e persistência são controlados pelo código do time.

## 6. O que já existe e o que falta verificar

| Área | Estado observado em 07/11 |
| --- | --- |
| **Base do código** | Checkout local em `main`, HEAD `f981c92`, igual à referência local `origin/main` naquele momento. `src/main.py` expõe `/health` e `/agent/run`. A base tem loop ReAct, registro de ferramentas, configuração, Docker e `sql/001_agent_runs.sql`. Documentação, novas skills e `sql/002_orcamentos.sql` aparecem como alterações locais ainda fora do histórico. |
| **Teste histórico do agente** | Em conversa anterior houve um teste local com HTTP 200, `completed` e `get_current_time` após ajuste temporário de ambiente. Samuel pediu para desfazer as alterações experimentais, e o chat registrou a restauração. Essa evidência é do agente-base naquele teste. |
| **Etapa 01 da A** | Diagnóstico e exemplos de contrato feitos pelo Claude Code. Next.js + TypeScript e o UUID antecipado foram registrados como aprovados. O trabalho seguinte passou para o SQL. |
| **Etapa 02 da A** | SQL das quatro tabelas e script de testes existem localmente. O Claude relatou 47 verificações na versão inicial e 93 na revisão, em Postgres 16 descartável via Docker. A revisão passou a exigir fonte para os preços por embalagem e introduziu tentativas e heartbeat. Após as respostas de B/C, a etapa foi reaberta. Supabase real, entrega de eventos Realtime e integração com B/C ainda carecem de confirmação. |
| **Contratos B/C** | As mensagens de Enzo e João estão registradas em `CONTRATOS-B-C.md`. B quer reservar a pesquisa dentro de `pesquisar_orcamento`. Há divergências de nomes e tipos, preços por unidade, cache, estados da pesquisa e frete por km. A revisão identificou uma possível corrida entre validar uma tentativa e gravar o item. Fechar o protocolo com B e proteger gravações e finalização antigas de forma atômica. C informou que calcula os resultados sob demanda, então falta combinar a interface de leitura. |
| **Frontend, exemplos e testes de importação** | O protótipo no Figma está navegável. O checkout inspecionado ainda não tem `frontend/`, as rotas da A, `tests/importacao/contrato.py` ou os exemplos de `docs/arquivos-teste/`. O contexto mais antigo menciona 100 casos e 183 arquivos em 15 formatos. A existência desse acervo fora do checkout não foi confirmada nesta consolidação. |
| **Ambiente e deploy** | O `check_setup` anterior ficou bloqueado pelo alias `python.exe` do Windows. Há relato histórico de backend na Vercel. O deploy e suas integrações atuais não foram verificados nesta consolidação. |

**Ponto de retomada do plano:** ajustar o SQL e os testes aos requisitos registrados, preparar o SQL completo para Enzo e João conferirem e só então aplicar no Supabase. Samuel pediu preparar o SQL primeiro, antes de enviar nova rodada de perguntas. A próxima etapa de interface é a 03, Nova obra e cadastro manual. O formulário descrito no fim deste texto é um pedido separado até Samuel dizer como ele se encaixa no projeto.

## 7. Hackathon e apresentação

Converge Challenge powered by Tako, 7–8/11/2026, Porto Digital, Recife. Segundo o guia consultado nas conversas, a preparação de ambiente e pesquisa antecedia a construção, e código do projeto, build e material de apresentação estavam reservados à janela do evento. A `main` contém um scaffold marcado como pré-evento. O tratamento desse scaffold perante a organização não ficou resolvido nos registros consultados.

Marcos planejados: integrar entrada e pesquisa às 14h de sábado, demonstrar E1–E7 às 17h, avançar em E8–E11 à noite e congelar funcionalidades às 10h30 de domingo. O guia citado registrava prazo de submissão às 13h de domingo, com meta do time às 12h30, e Demo Day às 16h com três minutos por equipe. A banca avalia protótipo, viabilidade como startup, pitch e originalidade com pesos iguais. O pacote de entrega previa descrição, vídeo, link testável, apresentação e lista de ferramentas. Domínio próprio e e-mail no domínio foram mencionados para a premiação AWS.

Roteiro planejado para a demo: abrir um arquivo de exemplo, aceitar uma correção e um complemento, enviar, ver resultados aparecerem, responder à pergunta de um item, mostrar no Langfuse uma busca refeita e concluir com viabilidade, comparação de frete, ganho de tempo e exportação. Métricas de tempo, custo, resolução autônoma e novas buscas são resultados a medir. Números exibidos no material de demonstração podem ser sintéticos quando identificados assim.

## 8. Como o time usa Claude Code e Codex

`CLAUDE.md` carrega `AGENTS.md` e `CONTEXTO-DO-PROJETO.md`. Para o trabalho da A, leia também `FATIAS-DO-TIME.md`, `PLANO-FATIA-A.md` e, quando houver dependência de B/C, `CONTRATOS-B-C.md`. O plano tem 14 prompts, do diagnóstico à demo. Execute uma etapa por vez quando solicitado e registre decisões, evidências, bloqueios e próximo passo no contexto. Samuel prefere que o Codex confira a entrega do Claude e traduza dependências técnicas para linguagem simples antes de sugerir o próximo prompt. Coordene edições se o Claude Code estiver rodando e atualize o checkout com pull quando Samuel pedir.

Para uma tarefa de interface do Orça, a skill pertinente é `building-orca-ui`. Banco/contratos usam `managing-orcamento-data`, importação usa `importing-materials`, e agente, modelos e tracing têm `building-react-agents`, `integrating-featherless` e `tracing-with-langfuse`. As skills ficam em `.claude/skills/` e têm fontes em `skills/`. Carregue as aplicáveis antes de editar, reutilize o que já estiver no contexto e anote as regras usadas. O repositório pede configuração via `src/config.py` e `.env`, tools novas com `ToolArgs` e `@registry.tool`, dados sintéticos e, antes de concluir mudanças, `python -m scripts.check_setup`, um caminho feliz e uma exceção.

### De onde vem este resumo

- **Codex:** “Refinar ideia para arquitetos”, “Sugerir recursos de IA para arquitetos”, “Avaliar pesquisa de orçamento”, “Explicar tarefas da Fatia A”, “Entender agentes Fearthless no Converge”, “Prepare setup para o Converge Challenge”, “Install missing development tools” e “Guardar contexto no Obsidian”. A sessão importada de `/model` só registrava configuração de ferramenta.
- **ChatGPT:** “Ideias insanas de startups”, na parte em que aparece a ideia do agente orçamentista. Foram conferidos os títulos dos históricos ativos e arquivados disponíveis para localizar conversas relevantes. Os chats sem relação com o projeto ficaram fora.
- **Claude Code e arquivos locais:** sessões locais da pasta HACKATHON, `README.md`, `CLAUDE.md`, `AGENTS.md`, `CONTEXTO-DO-PROJETO.md`, `FATIAS-DO-TIME.md`, `PLANO-FATIA-A.md`, `CONTRATOS-B-C.md`, `sql/002_orcamentos.sql` e notas do Hackathon no Obsidian. Quando há diferença entre um resumo antigo e a divisão atual do time ou o checkout, vale a fonte mais recente para aquele assunto.

## 9. Pedido que vou fazer ao Claude

Claude, use o texto acima como contexto de referência. Depois que eu descrever o formulário, **escreva uma instrução pronta para eu usar para criá-lo**, em português do Brasil. Use a descrição para determinar a finalidade, o público e onde o formulário deve ser criado. Traga do Orça apenas as informações que ajudarem nesse objetivo. Preserve as decisões já confirmadas que forem pertinentes, sinalize suposições que mudem o resultado e me peça apenas informações indispensáveis. Primeiro me entregue a instrução em texto, para eu poder revisar e usar.

**Descrição do formulário:**

[Vou explicar aqui, ou na próxima mensagem, para que serve o formulário, quem vai preenchê-lo, onde quero criá-lo e o que preciso obter com as respostas.]
