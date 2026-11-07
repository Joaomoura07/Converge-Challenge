@AGENTS.md

As skills deste repositório estão em `.claude/skills/` (descobertas automaticamente) e apontam para `skills/*.md`.

## Acionamento obrigatório das skills aplicáveis

Antes de executar um prompt, identifique a etapa e acione as skills correspondentes abaixo pela ferramenta de skills do Claude Code, quando disponível. Se a ferramenta não listar a skill, leia o `SKILL.md` em `.claude/skills/<nome>/` e o arquivo fonte indicado por ele. A leitura das instruções aplicáveis precede a edição. Uma menção ao nome, sozinha, não conta como uso.

- Agente, tools, loop, prompt ou escalonamento — `building-react-agents`.
- Chamadas ao LLM, modelos, limites ou erros da Featherless — `integrating-featherless`.
- Nova etapa instrumentada, traces, métricas ou integração Langfuse — `tracing-with-langfuse`.
- Interface, formulários, aceite e Realtime — `building-orca-ui`, fonte `skills/07-orca-ui-fatia-a.md`.
- SQL, contratos A/B/C, persistência e testes de concorrência — `managing-orcamento-data`, fonte `skills/05-orcamento-data.md`.
- CSV, Excel, TXT do Revit, PDF textual e normalização — `importing-materials`, fonte `skills/06-material-import.md`.

Os prompts do plano indicam a skill principal. Acrescente as demais somente quando a tarefa alcançar sua área. Reutilize instruções já carregadas no contexto e releia quando o arquivo mudar ou a regra precisar ser recuperada. Ao iniciar, informe quais skills foram carregadas; ao terminar, registre quais regras relevantes aplicou e quais verificações executou. Mantenha a memória enxuta. As verificações obrigatórias do repositório continuam sendo critério de conclusão.

## Memória do projeto

@CONTEXTO-DO-PROJETO.md

Antes de trabalhar na Fatia A, leia `FATIAS-DO-TIME.md`, `PLANO-FATIA-A.md` e confira a etapa atual em `CONTEXTO-DO-PROJETO.md`. A divisão enviada por Samuel em 07/11/2026 é a referência de escopo e responsabilidades. Neste checkout, o contexto está na raiz, embora o documento do time mencione `docs/CONTEXTO-DO-PROJETO.md`. O plano detalha ferramentas, contratos, dependências, tratamento de falhas, testes e prompts. Execute uma etapa por vez, conforme o pedido de Samuel.

Samuel é dono do SQL único das quatro tabelas, de `classificar_item()`, de `revisar_itens()`, de `POST /revisao/sugestoes` e do hook `useOrcamento(id)`. `POST /orcamentos` grava itens com status `buscando` e aguarda `pesquisar_orcamento(id)` de Enzo na mesma requisição. As correções e os complementos exigem aceite do arquiteto.

Antes de alterar SQL, contratos, persistência ou integração com B/C, consulte `CONTRATOS-B-C.md`. Ele registra as respostas de Enzo e João com nomes exatos de colunas e divergências que precisam de acordo, incluindo reserva da pesquisa dentro da B e entrega dos resultados calculados pela C.

Ao concluir cada etapa, atualize o estado da Fatia A em `CONTEXTO-DO-PROJETO.md` com o que foi feito, o que foi testado, os bloqueios e o próximo passo. Separe decisões confirmadas de propostas e resultados reais de simulações.
