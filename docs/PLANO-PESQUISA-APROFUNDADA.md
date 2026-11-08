# Pesquisa específica com consumo limitado

08/11/2026. Base revisada: `345c78c`; GitHub `9142716` tem a mesma árvore de arquivos.
Escopo: evolução da pesquisa existente, sem publicar nem alterar credenciais.

1. Pedir especificações por família (marca/referência, dimensão, acabamento, aplicação e características técnicas), preservando a descrição editável e a escolha explícita de aceitar uma estimativa.
2. Ler até duas páginas de produto por rodada via Tavily Extract, com prazo, deduplicação e trechos limitados. Aproveitar a extração existente em lote, sem um LLM por página.
3. Conferir em Python marca/linha reconhecida, cor, acabamento, medidas com unidades e códigos informados. Ausência de evidência não confirma identidade. Revalidar cache; não promover similares automaticamente depois de responder.
4. Preferir reformulação curta com Qwen3, limitar saída e chamadas, desativar corrida especulativa de modelos por padrão. Manter fallback sequencial.
5. Medir todas as respostas, inclusive vazias e inválidas: entrada, saída, chamadas, custo informado e consumo desconhecido. Persistir por item e exibir no resultado. Limites por item e por execução, compartilhados entre tarefas concorrentes.
6. Testar fluxo feliz, conflitos de especificação, falhas de páginas/LLM, cache, concorrência dos limites e interface. Fazer apenas amostra real pequena, com relatório de tokens/custo.

Crédito informado pelo usuário: US$ 72. Não é saldo consultado na conta. Limite por execução não é limite global da conta: outras execuções/chaves também consomem crédito. Custo ausente não significa gratuito; timeout/cancelamento pode ter cobrança sem usage retornado.

Referências consultadas: [Featherless completions](https://featherless.ai/docs/completions), [controle de raciocínio](https://featherless.ai/docs/chat-template-kwargs), [Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract).

## Implementação e validação

Executado localmente. A busca rejeita Google Shopping, buscadores e listagens como links de compra. Se faltarem ofertas diretas, faz uma consulta orgânica adicional, sem LLM; preço e URL precisam vir da mesma oferta. Links antigos inadequados não aparecem como botão de compra: a interface pede nova pesquisa. O filtro de URLs é heurístico e não garante disponibilidade permanente da página.

A interface permite completar a descrição de qualquer item, mantém o rascunho após erro e mostra tokens de entrada/saída, chamadas, páginas lidas e custo da última pesquisa. Similar permanece estimativa até aceite explícito. A soma na tela é das últimas pesquisas visíveis, não um histórico financeiro da conta.

Padrões: até 2 páginas por rodada, 1.400 caracteres por página, saída de 400 tokens, 6 chamadas e 30.000 tokens por item; 120 chamadas e 200.000 tokens por execução. Reservas concorrentes usam uma estimativa conservadora de entrada antes da chamada. O corte em US$ 0,03/item e US$ 0,25/execução considera custos já retornados: chamadas em andamento podem ultrapassá-lo. Não é garantia de teto de cobrança nem controle global dos US$ 72. Falhas sem usage são indicadas como consumo incompleto.

Amostra real de 08/11/2026, sem gravação no cache remoto:

| Material | Entrada | Saída | Chamadas | USD informado | Fontes diretas |
|---|---:|---:|---:|---:|---:|
| Tomada Tramontina Liz branca 20A | 1.390 | 68 | 1 | 0,000175 | 2 |
| Tinta Suvinil Toque de Seda Branco Neve 18 L | 6.004 | 211 | 3 | 0,000716 | 1 |

Total observado: **7.673 tokens / US$ 0,000892**; diferença de uma unidade na sexta casa decimal decorre do arredondamento por item. O check_setup adicional consumiu 500 tokens / US$ 0,000158916. Total desta validação: **8.173 tokens / aproximadamente US$ 0,001051**. Não inclui créditos próprios de Tavily/Serper. A amostra pequena não determina o custo médio de uma obra. Relatório bruto: `reports/avaliacao-pesquisa-aprofundada.json`. Nessa execução, o agregado de páginas ficou zerado por um erro de soma, corrigido depois; os itens registram quatro páginas efetivamente lidas. O relatório foi preservado como observado.

Testes: última suíte Python ampla com 861 aprovados e uma divergência entre site/prévia; a dependência foi sincronizada e os sete testes de interface passaram depois (um ignorado por ausência de node_modules na prévia). Testes direcionados de pesquisa, links e cancelamento: 71 aprovados. Frontend: 570 testes e typecheck aprovados. PostgreSQL descartável: 275 verificações; migração 005 aplicada duas vezes sem erro. Navegador isolado com dados sintéticos: desktop 1440 px, celular 390 px, consumo visível, rascunho mantido após HTTP 500 e ausência de rolagem horizontal.

check_setup confirmou Featherless, tool calling, Langfuse e Supabase. Uma das três chaves Tavily estava sem cota; as outras duas responderam. DuckDuckGo atingiu timeout, por isso o diagnóstico geral não ficou totalmente verde. Não houve deploy nem migração no Supabase de produção. Para publicar, aplicar `sql/005_pesquisa_detalhes.sql` e publicar backend/frontend compatíveis. A validação determinística cobre atributos reconhecidos; marcas/modelos arbitrários ainda dependem da evidência e da extração.

## Pesquisa com menos filtros

A demo e a entrada normal usam a mesma pesquisa. A leitura da página é opcional e os preços podem vir de anúncios ou fontes de busca vinculados ao produto. A busca pode reformular uma consulta sem repetir cada especificação; a descrição completa do pedido continua disponível para comparar as ofertas. Títulos abreviados não eliminam a oferta e itens similares podem servir de estimativa. Contradições explícitas não confirmam o produto como igual.

A lista de fontes mostra o preço anunciado e sua embalagem. O preço convertido permanece nos cálculos do orçamento. Resultados antigos sem preço anunciado mostram a ausência do dado ao lado do link. A loja pode variar preço por horário, região ou condições da compra; pesquisar de novo consulta a página novamente.

O cliente pode adicionar especificações e pesquisar de novo. Permanecem a exigência de fonte para o preço, a distinção entre preços anunciados e convertidos e a identificação de estimativas.
