# Imagens das pesquisas — 08/11/2026

Implementação local focada em imagens, compatível com o trabalho simultâneo do chat “Aprofundar pesquisa de materiais”. Não exige migração SQL, mudança dos prompts ou novos campos de API. Nenhum deploy realizado nesta tarefa.

## Comportamento

- Junta candidatas das buscas fixa, aberta e regional; preserva fotos do Tavily mesmo quando o texto vem de outro provedor.
- A busca aberta solicita descrições de imagens. URLs repetidas não ocupam as seis vagas de verificação; uma falha isolada não cancela as outras.
- Corrige URLs de CDN do Magalu com `{w}x{h}` ou `%7Bw%7Dx%7Bh%7D`, preservando a query. URLs HTTP são normalizadas para HTTPS.
- Se nenhuma candidata carregar, usa Serper Images com as chaves já configuradas. Limite de oito segundos para buscar e verificar a reserva; não chama LLM. Consome a cota de consultas do Serper quando acionada.
- Pode usar a miniatura do mesmo resultado quando a foto original bloqueia acesso. A conferência conserva a URL original como evidência de medida/cor, sem aceitar uma variante só porque a URL da miniatura é opaca.
- Preços vindos do cache sem foto podem receber uma imagem no resultado do orçamento, sem nova pesquisa de preço. Não altera `cache_precos`, pois o trigger existente renova a validade em qualquer atualização. Novos orçamentos que reutilizem esse cache ainda sem foto podem consumir uma nova consulta de imagens.
- Na repesquisa, a nova foto verificada tem prioridade sobre a antiga. Sem foto nova, mantém a anterior.
- `ImagemProduto` atende ItemRow, lista da estimativa e referência selecionada. Trata erro, troca de URL via Realtime, HTTPS e referrer. Fotos usam `contain` para não cortar o produto.
- Se a foto não existe ou falha, há uma ilustração vetorial local por tipo de material, identificada como **Ilustração**. Isso garante uma referência visual; não garante fotografia real de todo produto nem confirma a equivalência comercial do produto fotografado.

## Validação observada

- 128 testes offline de imagens, busca, cache, pesquisa e determinismo aprovados; nove testes reais separados da execução.
- 558 testes do frontend aprovados na execução completa. Typecheck passou após implementar os componentes. Uma execução posterior encontrou erro de tipagem em `frontend/src/lib/importar/fluxo-curto.test.ts:62`, arquivo novo de trabalho concorrente, fora desta alteração.
- Teste real de reserva para “Porcelanato Eliane Munari Cimento acetinado 60x60”: 18 candidatas, foto da Telhanorte verificada em 1,91 s, zero chamadas de LLM.
- Navegador local: seis fotos da prévia B carregadas, incluindo Magalu com template corrigido; sétimo item com ilustração. Falha de URL simulada e posterior troca para foto válida funcionaram no mesmo componente. A página temporária desse ensaio foi removida.
- Inspeção das prévias B/C em desktop e largura de celular; miniaturas e referência exibem o fallback. Sem overflow horizontal na largura de 390 px (375 px de conteúdo).
- `python -m scripts.check_setup` executado pelo Python de `.venv`: chat/tool calling Featherless, Langfuse, Supabase e DuckDuckGo responderam; Tavily 1/3 sem cota, outras duas chaves responderam. Duas chamadas de sondagem Qwen vieram vazias. Custo medido do diagnóstico: US$ 0,001036501, 199 tokens de entrada, 182 de saída, duas respostas sem custo informado. Esse diagnóstico é separado da recuperação de fotos, que não usa Featherless.

## Limites e publicação

Uma foto que já está no cache e tem URL válida não é revalidada em toda leitura. Se o host deixar de servi-la, a tela apresenta a ilustração; “Pesquisar de novo” pode substituí-la. Não foi feita uma migração retroativa dos orçamentos salvos. Hotlink, expiração de URLs e indisponibilidade das lojas continuam dependendo de terceiros.

As mudanças de especificações, preços, tokens, links de produto e importação dos outros chats foram preservadas. Revisar o conjunto antes do deploy.

Referências técnicas consultadas: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [Serper](https://serper.dev/). A resposta do endpoint de imagens foi verificada com uma consulta real usando a configuração existente.

## Integração para publicação — 08/11/2026

- A pedido do usuário, aplicada a melhoria de imagens sobre `origin/main` em checkout isolado, inicialmente na versão `1e00ec2`. Preservadas as novidades remotas, incluindo fotos do Google Shopping, links de lojas, cálculos e arquivos de demonstração.
- Removida da integração uma dependência de `linkDiretoProduto` que pertencia ao trabalho paralelo ainda não publicado. Os links da estimativa mantêm o comportamento da versão remota.
- Sincronizados ItemRow e os três arquivos do componente de imagem com `ui-fatia-b`, incluindo tipos de CSS Modules do Vite e proteção contra divergência entre site e prévia.
- Validação no checkout isolado: 400 testes offline da Fatia B aprovados; 557 testes do frontend aprovados e um ignorado; build Next.js e build Vite aprovados, ambos com checagem TypeScript. Chave sintética usada exclusivamente para habilitar caminhos de agentes simulados, sem chamadas reais de LLM nesses testes.
- Os arquivos não commitados dos outros chats e o commit local de importação não foram incluídos nesta integração de imagens. A pasta de trabalho original foi preservada.
