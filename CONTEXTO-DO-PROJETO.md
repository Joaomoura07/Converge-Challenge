# Orçamentista Autônomo — contexto do projeto

> Resumo para o time do **Converge Challenge powered by Tako**. Plano da Fatia A atualizado em 07/11/2026.

## 0. Fatia A — entrada e revisão, divisão atualizada

A referência de escopo é [FATIAS-DO-TIME.md](FATIAS-DO-TIME.md), cópia do arquivo enviado por Samuel em 07/11/2026. Neste checkout, o contexto está na raiz. O plano detalhado está em [PLANO-FATIA-A.md](PLANO-FATIA-A.md).

### Responsáveis

- **Samuel / A** entrega Nova obra com nome, CEP e orçamento do cliente, upload CSV/Excel/TXT do Revit/PDF com texto, cadastro manual, três exemplos, tabela com aceite de correções e complementos, envio e esqueleto de resultado com `useOrcamento(id)`.
- **Samuel / A** também é dono do SQL único de `orcamentos`, `orcamento_itens`, `cache_precos` e `fornecedores`, de `classificar_item()`, `revisar_itens(itens)`, `POST /revisao/sugestoes` e `POST /orcamentos`.
- **Enzo / B** implementa `pesquisar_orcamento(id)`, pesquisa, conferência, preços com fontes e confiança, embalagens com perda, perguntas, `repesquisar_item(item_id)` e `ItemRow`. Ao final chama logística e viabilidade da C.
- **João / C** implementa `sugerir_complementos(itens)`, logística, viabilidade, ganho de tempo, exportação e componentes finais. Cadastra as lojas na tabela `fornecedores` criada pela A.
- **D** cuida de negócio e apresentação. Responsável a definir segundo o documento do time.

### Contratos confirmados pela nova divisão

- A grava os itens em `buscando` e chama `pesquisar_orcamento(orcamento_id)` da B **na mesma requisição**, aguardando seu retorno.
- A revisão chama `POST /revisao/sugestoes`, que reúne `{erros: [...], complementos: [...]}`. A calcula erros e C calcula complementos.
- A classificação é função única da A. B confirma e C lê. Preservar classificação de negócio separadamente do estado de processamento.
- Estados oficiais do item são `buscando`, `definido`, `pendente_especificacao`, `nao_encontrado` e `erro`. Fechar separadamente os estados gerais de orçamento.
- O hook acompanha as duas tabelas por Realtime. Fechar na etapa 01 como a tela conhece o ID antes da resposta do POST. UUID gerado pelo cliente é proposta a validar no contrato.
- Correções, complementos e similares exigem clique do arquiteto. Cada preço apresentado pela B deve ter fonte.

### Etapas atualizadas

Os prompts completos e os critérios de teste estão no plano.

| Etapa | Entrega |
|---|---|
| 01 | Diagnóstico e contratos |
| 02 | SQL único e persistência |
| 03 | Nova obra e cadastro manual |
| 04 | CSV e três arquivos de exemplo |
| 05 | Classificação única e revisor E1 |
| 06 | Sugestões A/C e aceite na tabela |
| 07 | Página de resultado e useOrcamento |
| 08 | POST /orcamentos e integração na mesma requisição |
| 09 | Excel |
| 10 | TXT do Revit |
| 11 | PDF com texto |
| 12 | Encaixe dos componentes B/C |
| 13 | Bateria e regressões |
| 14 | Demo e entrega |

### Estado em 07/11/2026

- **Skills implementadas para a Fatia A** — `building-orca-ui` em `skills/04-ui-design.md`, `managing-orcamento-data` em `skills/05-orcamento-data.md` e `importing-materials` em `skills/06-material-import.md`. Registradas em `.claude/skills` e `.agents/skills` pelo script do repositório. CLAUDE.md exige carregar a skill aplicável antes de editar e os 14 prompts indicam seus nomes. As três skills anteriores de agente, Featherless e Langfuse continuam disponíveis. Validação estrutural concluída; uso efetivo na sessão do Claude será conferido no próximo retorno.

- **SQL APLICADO no Supabase real (07/11/2026), informado por Samuel.** Samuel rodou `sql/002_orcamentos.sql` e `sql/verificar_supabase.sql` no SQL Editor e relatou que "deu tudo certo" (não vi a saída; o número exato do resumo não foi registrado). A 1ª tentativa falhou com `ERROR 42703: column "resultado" does not exist`: já existia uma `cache_precos` de outro formato no projeto. Correção: o SQL agora renomeia uma `cache_precos` fora do contrato para `cache_precos_antiga_<data>` e cria a tabela limpa (teste novo, bateria em 273 OK / 0 falhas em duas execuções). Próximo: avisar Enzo e João (usar `service_role` no backend), seed de `fornecedores`. Ainda NÃO testado no real: Realtime entregando eventos, chamadas `supabase.rpc` de B/C. O texto abaixo, escrito antes da aplicação, descreve o preparo.
- **SQL pronto para aplicar no Supabase (07/11/2026).** Skill usada: `managing-orcamento-data` (`skills/05-orcamento-data.md`). Arquivos: `sql/002_orcamentos.sql` (acrescentado `orcamentos.ganho jsonb` nullable, mais `ADD COLUMN IF NOT EXISTS` para `logistica`, `viabilidade` e `ganho` em bancos que tenham versão anterior do arquivo; removido `create extension pgcrypto`, desnecessário no Postgres 13+/Supabase), `scripts/testar_sql_orcamentos.sh` (nova seção 10b e checagens de papéis para as escritas de João), `sql/verificar_supabase.sql` (somente leitura: tabelas+RLS, colunas, funções e permissões, políticas, publicação Realtime; uma tabela `secao|item|situacao|detalhe` e linha de resumo) e `docs/APLICAR-SUPABASE.md` (passo a passo). Confirmado por leitura: todas as colunas listadas por Enzo e João existem com os nomes exatos (`fornecedores`: id, nome, dominio, cep, lat, lon, frete_base, rs_por_km, pedido_minimo; `orcamentos` e `orcamento_itens` conforme o pedido, `origem_linhas` é `integer[]`).
  - **Testes reais (Postgres 16 descartável em Docker, papéis simulados anon/authenticated/service_role): 270 verificações OK, 0 falhas, em duas execuções seguidas** (1ª rodada teve 1 falha do próprio teste, valor esperado errado, corrigido). Cobrem: criação limpa 2x e reaplicação; migração do rascunho (dados preservados, esquema e regras idênticos a banco novo); João grava `logistica`/`viabilidade`/`ganho` com `service_role`, `anon` lê e não grava; gravar esses jsonb não altera `tentativa_pesquisa`, `status_pesquisa` nem heartbeat, a tentativa da B segue válida e a finalização da B não apaga os resultados da C; reaplicar sobre banco sem `ganho` recria a coluna; RLS, Realtime nas duas tabelas, corrida controlada da troca de tentativa e teste de mutação. `verificar_supabase.sql` rodado em transação read-only: 87 ok / 0 FALTA no banco simulado; num banco sem `ganho` e sem `orcamento_itens` no Realtime acusou as 2 FALTAs.
  - **NÃO testado (antes da aplicação; ver o registro de aplicação acima):** SQL no Supabase real (nenhuma conexão feita por mim); Realtime entregando eventos de verdade; papéis reais (só simulados); avisos do SQL Editor sobre `drop`; as chamadas `supabase.rpc` e a API Python de B/C; Vercel. A primeira aplicação real é a prova.
  - **CONFIRMADO** (pelos requisitos enviados por Enzo/João e por Samuel): nomes e tipos de colunas listados acima; estados do item; fontes obrigatórias em qualquer preço; `ganho`, `logistica` e `viabilidade` em `orcamentos` (pedido por João em `PARA-SAMUEL.md`, que reverte a ideia anterior de "sem colunas"). **PROPOSTA da A, ainda sem aceite de B/C:** protocolo `reservar_pesquisa`/`gravar_resultado_item`/`finalizar_pesquisa`/`renovar_pesquisa` com número de tentativa e prazo de 180 s desde a última atividade; `pesquisa_iniciada_em`/`pesquisa_concluida_em` no lugar dos `iniciado_em`/`concluido_em` que João citou; `lat`/`lon` como `numeric(9,6)` (João pediu double precision; o cliente recebe número igual); complementos em colunas explícitas e `estimativa_consumo` separada de `estimativa`; `classificacao` definido/pendente; validade do cache = `atualizado_em` + 7 dias; `similar` com fonte própria. **Em aberto:** quem faz o seed de `fornecedores` (João oferece `sql/003_seed_fornecedores.sql`); prazo de 180 s × duração máxima real na Vercel; quem preenche `custo_usd`/`tempo_ms`/`trace_url`.

- **Atualização vigente após respostas de B/C** — Enzo é o autor da primeira mensagem e João da segunda, conforme Samuel. Requisitos exatos e divergências salvos em `CONTRATOS-B-C.md`. Etapa 02 reaberta para compatibilizar SQL, funções e testes. A reserva é responsabilidade da B; protocolo de retomada e gravação ainda precisa de acordo. João calcula resultados na hora, exigindo fechar como a tela os obtém. Os registros de conclusão abaixo representam as versões anteriores do SQL.

- **Etapa 03 feita (07/11/2026) — Nova obra e cadastro manual em `frontend/`. Não commitada.** Skill usada: `building-orca-ui` (instruções de `skills/04-ui-design.md`); lidas a seção 0 deste arquivo e as seções 3 e 4 do plano. **Figma NÃO foi aberto** (a busca devolveu HTTP 403, exige login): o visual segue a direção descrita na skill e no pedido (papel claro, títulos serifados, azul cobalto, divisórias finas, cota tracejada, hachura 45° nas áreas reservadas) e **ainda precisa ser comparado com os quadros do Figma por quem tem acesso**.
  - **Decisões confirmadas (Samuel):** Next.js + TypeScript em `frontend/` (App Router); `orcamento_id` gerado na tela antes do envio (`crypto.randomUUID`); direção visual "caderno de materiais digital".
  - **Arquivos criados (só em `frontend/`; `sql/` e `src/` intactos):** `package.json` (versões fixas: next 15.5.29, react/react-dom 19.1.10, typescript 5.9.3, vitest 5.1.0) e `package-lock.json`, `tsconfig.json`, `next.config.mjs`, `vitest.config.mts`, `.env.example` (sem chaves; só variáveis públicas, ainda não usadas), `.gitignore` (node_modules, .next, .env*), `src/lib/validacao.ts` (CEP, reais, quantidade, unidade, nome, descrição, `gerarUuid` com fallback), `src/lib/lista.ts` (reducer da lista única: adicionar/editar/remover/tocar/revelar_erros/alternar_modo/importar; erros derivados e indexados por ID), `src/components/{Caderno,NovaObra,TabelaMateriais}.tsx`, `src/app/{layout,page}.tsx`, `globals.css`, `icon.svg`, testes `src/lib/{validacao,lista}.test.ts`.
  - **Comportamento implementado:** tela Nova obra (nome, CEP texto de 8 dígitos com zero inicial, orçamento em reais aceitando "20.000,50", "20000,5", "R$ 20.000"; recusa vazio, zero, negativo e texto; validação no envio, com foco no primeiro campo inválido); `orcamento_id` nasce ao iniciar a obra e é mantido ao editar a obra; tabela editável com ID estável por linha (UUID, nunca o índice), adicionar/remover, quantidade com vírgula → número com ponto, unidades m/m2/m3/un/kg/l/cm/mm (aceita "m²"), categoria opcional; abas de modo (manual, CSV, Excel, Revit, PDF) trocam só o painel, a lista é única e preservada; áreas reservadas vazias: avisos E1, complementos E2, "Usar arquivo de exemplo" (desabilitado) e "Enviar para a IA" (desabilitado com lista vazia ou erro estrutural, com motivo em texto e atalho "Ir para o primeiro erro"); estados vazio, edição e erro; responsivo (grade no desktop, cartões no celular). Não há importação, sugestões nem envio.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **40 testes OK** (validação e lista, incluindo exclusão de linha com erro sem alterar os erros das outras e preservação ao alternar modo); `npm run build` OK. **No Chrome real (playwright-core, fora do projeto, servidor `next start`)**: caminho feliz; orçamento vazio/0/negativo/texto/"1,2,3" recusados com mensagem e foco; CEP curto recusado e CEP com zero inicial mantido; quantidade vazia/0/negativa/texto com erro no campo e envio bloqueado; exclusão de linha sem erro e de linha com erro, com os erros das demais linhas intactos; UUID mantido ao editar a obra; celular de 390 px sem rolagem horizontal; sem erros de console. Rodou 3 vezes seguidas, tudo OK. O script de navegador não está no repositório (ficou no scratchpad).
  - **Defeito achado e corrigido na verificação:** erro exibido ao sair do campo deslocava o layout entre pressionar e soltar o mouse e o clique no botão se perdia. Agora a Nova obra valida só no envio e cada linha da tabela reserva uma linha de espaço para as mensagens.
  - **NÃO testado / não feito:** comparação com o Figma; leitor de tela e navegação só por teclado (rótulos, `aria-invalid`, `aria-describedby` e foco foram implementados, mas não conferidos com leitor); Safari, Firefox e celular físico; rascunho não persiste ao recarregar a página (recarregar perde a obra, a lista e o UUID); confirmação "acrescentar ou substituir" da skill fica para os importadores (o reducer já tem `importar` com os dois modos); deploy na Vercel; o script `python -m scripts.check_setup` segue sem rodar (Python do Windows).
  - **PROPOSTAS da A (não confirmadas):** quantidade "1.234" (ponto com três dígitos, sem vírgula) é recusada como ambígua e orçamento "20.000" é lido como vinte mil; quantidade com no máximo 3 casas e orçamento com 2; nome da obra até 120 caracteres e descrição até 300; unidade vazia é erro (não há padrão); linha com todos os campos vazios também bloqueia o envio.
  - **Bloqueios:** nenhum para a etapa 04. Pendências abertas herdadas: como a tela obtém frete/viabilidade/ganho/Excel da C; Supabase real ainda sem as tabelas.
- **Etapa 02 reaberta e refeita para o contrato de B/C (07/11/2026) — SQL pronto para conferência, NÃO aplicado no Supabase.** Skill usada: `managing-orcamento-data` (carregada via Skill; instruções de `skills/05-orcamento-data.md`). Arquivos: `sql/002_orcamentos.sql` (reescrito), `scripts/testar_sql_orcamentos.sh` (reescrito), `scripts/fixtures/002_rascunho_anterior.sql` (cópia do rascunho antigo, só para testar a migração). **Evidência de aplicação anterior:** consulta de leitura ao Supabase real devolveu `PGRST205` nas 4 tabelas, ou seja, o rascunho nunca foi aplicado lá; a migração cobre bancos locais que o tenham recebido.
  - **Regras aplicadas (da skill):** nomes/tipos/defaults de `CONTRATOS-B-C.md` (`produto_normalizado`, `imagem_url`, `unidade_preco`, `motivo`, `iteracoes`, `preco_emb_*` numeric(12,2), `preco_un_*` numeric(12,4), `preco_data` timestamptz, `atualizado_em` por trigger, `status_pesquisa` pendente/pesquisando/concluida/falhou, `pesquisa_erro`, cache com `imagem_url`/`atualizado_em`, fornecedores com `rs_por_km`, `lat`, `lon`, obrigatórios NOT NULL); qualquer um dos seis preços exige `fontes` válidas (loja, dominio normalizado, url http(s), preco_embalagem, embalagem texto opcional), inclusive com `estimativa=true`, também no `similar` e no cache; `classificacao` separada de `status`; `orcamento_cliente` em reais e CEP texto preservados; protocolo único `reservar_pesquisa` → `gravar_resultado_item` → `finalizar_pesquisa` (+ `renovar_pesquisa`), com número de tentativa e bloqueio `FOR NO KEY UPDATE` da linha do orçamento antes de conferir a tentativa e gravar (ordem de bloqueio: orcamentos → itens); `pesquisa_heartbeat_em` renova o prazo (180 s só libera execução parada, a segurança é o número da tentativa).
  - **Testes executados (Postgres 16 descartável, Docker): 251 verificações OK em duas execuções seguidas.** Criação limpa 2x; colunas do contrato; criação, reenvio, conflito, falha parcial; 12 criações simultâneas e 8 com conteúdo diferente; seis preços isolados sem fonte, com estimativa e com fonte inválida; escrita exata de B (todos os campos) e de C (exemplo de porcelanato do João, fornecedores com os nomes dele); protocolo: 12 reservas simultâneas, execução lenta, retomada, reabrir; **troca de tentativa durante a gravação com intercalamento controlado** (reserva segura a linha em transação aberta e a gravação/finalização da tentativa velha espera e é recusada) e **teste de mutação** (sem o `FOR NO KEY UPDATE` a gravação velha passa, e o teste pega); permissões com papéis simulados do Supabase; migração do rascunho (dados e tipos preservados, esquema e regras idênticos aos de um banco novo, falha segura com fornecedor sem CEP). O teste de migração achou um defeito real (`finalizar_pesquisa` com parâmetro renomeado) já corrigido.
  - **NÃO testado:** SQL no Supabase real; Realtime entregando eventos; papéis reais (só simulados); a API Python e as chamadas `supabase.rpc` de B/C (código deles); Vercel.
  - **PROPOSTAS da A a revisar por B/C (não confirmadas):** (B) `reservar_pesquisa(id, expira_s=180, reabrir=false)` devolve `{reservado, tentativa, status_pesquisa}` e B usa as funções em vez de UPDATE direto; prazo contado desde a última atividade, não de `pesquisa_iniciada_em`; `reabrir=true` para `repesquisar_item`; B não escreve `classificacao` (é da A); `iteracoes` gravado como valor; validade do cache = `atualizado_em` + 7 dias; resultado do cache usa as mesmas chaves de preço e `fontes` do item; `resposta` do arquiteto fica em coluna do item (escrita pela A); domínio das fontes normalizado dentro de `gravar_resultado_item`. (C) `pesquisa_concluida_em` como "concluído em"; complementos em colunas explícitas (`sugerido`, `sugestao_regra`, `sugestao_motivo`, `origem_linhas int[]` com os números de `linha`, `aceito`) e `estimativa_consumo` separada de `estimativa`; `linha` obrigatória (A numera listas digitadas); `"similar"` jsonb exige `descricao` e, com preço, fonte própria (nome entre aspas no SQL por ser palavra reservada); `logistica`/`viabilidade` mantidas como jsonb opcionais, pois João calcula na hora; domínio de `fornecedores` normalizado por trigger. (Ambos) `classificacao` passa a `definido`/`pendente` (antes `definido`/`generico`).
  - **Decisões em aberto para a revisão posterior:** como a tela obtém frete, viabilidade, ganho e Excel calculados por João na hora (função/rota e sinal de "pronto"); duração máxima efetiva da função na Vercel × prazo de 180 s; se `custo_usd`/`trace_url`/`tempo_ms` ficam em `orcamentos` (B grava ao finalizar); leitura pública `anon` com `using (true)` segue só para a demo sintética.
- **Etapa 01 concluída (leitura e planejamento, sem código).** Verificado no checkout: só existem `src/` (main, agent, tools, database, config), `sql/001_agent_runs.sql`, `prompts/`, `skills/01–03`, `scripts/`. NÃO existem `frontend/`, `tests/`, `docs/arquivos-teste/`, `contrato.py`, `skills/04-ui-design.md` nem as 4 tabelas. `src/main.py` só tem `/health` e `/agent/run`. Python do Windows não roda (alias da Microsoft Store). **Propostas (não confirmadas):** UUID gerado pelo cliente como `orcamento_id` e chave de reenvio; hash do conteúdo para detectar conflito (409); coluna `classificacao` separada de `status`; estados gerais `recebido|pesquisando|concluido|erro`; sugestão com `id`, `revisao_id`, `linhas`, `acao`, `campos`. Pendências com Enzo/João: ver resposta da etapa 01. Próxima tarefa: etapa 02 (SQL único).
- **Etapa 02 concluída (SQL único), 07/11/2026.** Decisões confirmadas por Samuel: Next.js + TypeScript em `frontend/`; UUID gerado pela tela como `orcamento_id` (mesmo UUID em reenvio; mesmo conteúdo recupera, conteúdo diferente dá conflito). Criados: `sql/002_orcamentos.sql` (4 tabelas, `criar_orcamento()` transacional, `iniciar_pesquisa()` com trava, RLS, Realtime) e `scripts/testar_sql_orcamentos.sh`. **Testado de verdade** em Postgres 16 descartável (Docker): 47 verificações OK, duas execuções seguidas — criação idempotente, gravação, falha parcial desfeita, reenvio, conflito, 12 chamadas simultâneas (1 cria, 11 recuperam; 8 com conteúdo diferente: 1 cria, 7 conflitos), trava da pesquisa (só 1 vence), restrições, cascata, RLS e Realtime com papéis simulados do Supabase. **Revisão da etapa 02 (mesmo dia):** (1) regra de fontes corrigida: qualquer `preco_emb_min/med/max` exige `fontes` válidas (`fontes_validas()`: loja, dominio, url http(s), preco_embalagem >= 0), inclusive com `estimativa=true`; a B grava tudo num UPDATE via `gravar_resultado_item()`. (2) retomada corrigida: `iniciar_pesquisa()` devolve o número da tentativa (ou NULL), prazo de 180 s sem atividade só serve para retomar execução morta; `gravar_resultado_item`, `renovar_pesquisa` e `finalizar_pesquisa` recusam (retornam false) tentativa velha, então execução lenta não sobrescreve a nova. Testes: 93 verificações OK em duas execuções seguidas (cada campo de preço isolado, estimativa sem fonte, fontes inválidas, execução lenta, corrida de 8 gravações velhas contra 1 nova, 12 pedidos simultâneos antes e depois do prazo). **NÃO testado:** o SQL no Supabase real (não foi aplicado; falta rodar no SQL Editor), a API Python (inexistente; Python do Windows não roda), o Realtime recebendo eventos de verdade. **Propostas ainda não confirmadas por Enzo/João:** estados gerais `recebido|pesquisando|concluido|erro`; `embalagem` como texto; `logistica`/`viabilidade` como jsonb em `orcamentos`; funções da B `gravar_resultado_item`/`finalizar_pesquisa` com número da tentativa (B precisa chamá-las em vez de UPDATE direto); regra "todo preço exige fonte" mesmo em estimativa; `unidade` livre no banco (API valida a lista). Limitação: leitura pública `using (true)` — qualquer um com a chave anon lista todos os orçamentos; ok só para demo sintética.
- Concluído neste chat — cópia da divisão do time e atualização do contexto, do plano por ferramenta e dos 14 prompts.
- Verificação local — implementação da Fatia A pendente. `tests/importacao/contrato.py`, amostras e `skills/04-ui-design.md` ainda precisam estar disponíveis neste checkout.
- Última verificação de ambiente — `python -m scripts.check_setup` falhou ao iniciar `WindowsApps/python.exe`. Resolver o interpretador para os testes da aplicação.
- Em aberto — framework/local do frontend, formatos Excel, campos finais do SQL e do contrato, nomes dos três exemplos, identificação antecipada do orçamento e tempo efetivo do fluxo na Vercel.
- Prazo de Samuel até a noite de 07/11. Marcos do time — integração às 14h, E1–E7 demonstráveis às 17h, E8–E11 à noite, congelamento domingo às 10h30 e submissão até 12h30.
- Próximo passo (atualizado após a etapa 03) — Samuel confere a tela e o Figma; depois etapa 04 (CSV e três arquivos de exemplo), que alimenta a mesma lista de `frontend/src/lib/lista.ts`. Em paralelo, o SQL abaixo segue aguardando B/C.
- Próximo passo (SQL) — Samuel encaminha `sql/002_orcamentos.sql` a Enzo e João para conferir com o código deles (lista de propostas acima). Só depois de B/C aceitarem (ou ajustarem), aplicar no Supabase pelo SQL Editor e então seguir para a etapa 03 (Nova obra e cadastro manual, em `frontend/`).

---

## 1. O evento

| | |
|---|---|
| **O quê** | Hackathon presencial de AI Agents, com Demo Day e premiação |
| **Quando** | Sábado 7/11 e domingo 8/11/2026. **Presença obrigatória nos dois dias** |
| **Onde** | **Porto Digital** — Av. Cais do Apolo, 222, 8º andar, Bairro do Recife |
| **Canal oficial** | Grupo de WhatsApp do evento (todo aviso sai por lá) |

### Horários que importam
| Dia | Hora | O quê |
|---|---|---|
| Sáb | 08h30 | Credenciamento e café |
| Sáb | 09h30 | Abertura e regras (prestar atenção em qualquer mudança) |
| Sáb | **10h00** | **Começa a construção.** Código do produto só a partir daqui |
| Sáb | 17h00 | Fim do dia 1 |
| Dom | **13h00** | **Prazo final de submissão** (meta: submeter até 12h30) |
| Dom | 16h00 | Demo Day: **3 minutos por time**, cronometrado |
| Dom | 17h30 | Premiação |

### Como a banca avalia (4 critérios, peso igual)
1. **Protótipo e aderência:** funciona na demo, faz trabalho real, e **os jurados vão testar o link**
2. **Viabilidade como startup:** mercado, quem paga, como cresce
3. **Pitch:** clareza do problema, da solução e do mercado
4. **Criatividade e originalidade**

Metade da nota é negócio. A Canastra (fundo de investimento) e a Tako estão na banca.

### O que a submissão exige
- Descrição: problema, para quem, solução e **como o agente funciona**
- Vídeo de demonstração
- **Link navegável e testável**
- Material de apresentação
- Lista de ferramentas, modelos e APIs usados

### Prêmio AWS (atenção)
Para resgatar os créditos é preciso ter **site em domínio próprio**, **e-mail no mesmo domínio** (Gmail não vale) e conta AWS. Dá para resolver no sábado à noite: registrar um `.com.br`, subir uma landing simples e criar o e-mail.

---

## 2. O produto: Orçamentista Autônomo

### O problema
Arquitetos perdem horas montando orçamento e estudo de viabilidade na mão. Eles pegam a lista de materiais do projeto (exportada do Revit ou do SketchUp), pesquisam preço loja por loja e calculam frete. É trabalho repetitivo, lento e cheio de erro.

### A solução
Um sistema em que o arquiteto **sobe a lista de materiais e recebe um estudo de viabilidade pronto**, com preços médios, imagens dos produtos e a melhor estratégia de compra para o CEP da obra.

### Fluxo do usuário
```
1. Informa nome, CEP e orçamento do cliente e importa arquivo, usa exemplo ou digita os materiais
2. Na tabela editável, confere os erros E1 e aceita correções e complementos E2
3. Clica em "Enviar para a IA"
4. Os itens vão aparecendo na tela AO VIVO, um a um, com preço e imagem
5. Recebe preços com fontes, perguntas, plano de compra, frete, viabilidade e exportação
```

### O que o sistema entrega
- **Preço médio, mínimo e máximo** de cada item, pesquisado na internet em tempo real
- **Imagem** do produto
- **Separação** entre itens bem definidos (ex.: "Suvinil Toque de Seda Branco Neve 18L") e itens **Pendentes de Especificação** (ex.: "tinta branca", sem marca nem modelo)
- **Decisão de logística:** pelo CEP da obra, se compensa comprar tudo numa loja só ou dividir entre lojas pagando mais de um frete
- Material para o arquiteto **negociar desconto** com as lojas físicas

---

## 3. Arquitetura

```
 [Site na Vercel]
   upload → tabela editável → "Enviar para a IA"
        │
        ▼  POST /orcamentos
 [Backend FastAPI na Vercel]
   Agente de IA (loop ReAct)
     ├─ LLM: Featherless (GLM-5.2)       → entende e normaliza cada item
     ├─ Busca: Tavily (principal)        → preço + imagem
     │         DuckDuckGo (reserva)      → se o Tavily falhar ou acabar
     ├─ Cache de preços (Supabase)       → item já pesquisado sai na hora
     └─ Logística (Python determinístico) → CEP da obra × lojas → loja única ou dividir
        │
        ▼  grava item por item
 [Supabase]  ── Realtime ──▶  o site atualiza sozinho
 [Langfuse]  ← trace de cada execução (o que o agente fez, custo, tempo)
```

### Decisões já tomadas
| Tema | Decisão |
|---|---|
| Hospedagem | **Tudo na Vercel:** backend (já no ar) + site. Nada depende do notebook |
| n8n | **Fora.** O site fala direto com o FastAPI |
| Busca | Tavily + DuckDuckGo de reserva + cache |
| Lojas e frete | **Híbrido:** o preço vem da busca; lojas de Recife pré-cadastradas no Supabase (CEP, frete base, R$/km, pedido mínimo) garantem o cálculo de frete mesmo se a busca falhar |
| Proteção da URL | Nenhuma por enquanto (é demo) |
| Demo | Roteiro atualizado de aproximadamente 75 s dentro do pitch de 3 min, com exemplos, revisão, pesquisa, pergunta, Langfuse e resultado |

### Stack
| Peça | Ferramenta | Status |
|---|---|---|
| LLM | Featherless (`zai-org/GLM-5.2`; reserva `Qwen/Qwen3-32B`) | ✅ testado, faz tool calling |
| Busca | Tavily | ✅ chave testada (traz preço e imagem) |
| Busca reserva | DuckDuckGo (biblioteca `ddgs`, sem chave) | entra no sábado |
| CEP | ViaCEP / BrasilAPI (grátis, sem chave) | entra no sábado |
| Banco + tempo real | Supabase | ✅ conectado |
| Rastro / auditoria | Langfuse (região **US**) | ✅ conectado |
| Backend | FastAPI (Python) | ✅ no ar na Vercel |
| Site | Vercel (framework a definir com o Samuel) | conta criada, site vazio |

**Backend no ar:** https://converge-challenge.vercel.app
- `/health` → mostra o que está conectado (LLM, Supabase e Langfuse: tudo `true`)
- `/docs` → Swagger para testar a API

---

## 4. Contrato de dados — validar A, B e C

### Entrada: `POST /orcamentos`
O site manda os itens **já revisados pelo arquiteto**:
```json
{
  "obra": { "nome": "Reforma Apto Boa Viagem", "cep": "51020-000", "orcamento_cliente": 20000.00 },
  "origem": { "arquivo": "lista.xlsx", "formato": "xlsx", "software": "revit" },
  "itens": [
    { "linha": 5, "categoria": "Pintura", "descricao": "Tinta acrílica Suvinil Toque de Seda Branco Neve",
      "quantidade": 180, "unidade": "m2", "nivel": "Térreo", "extras": {} }
  ]
}
```
A API grava os itens em `buscando`, chama `pesquisar_orcamento(id)` da B e aguarda a execução na mesma requisição. A resposta inclui `orcamento_id` e o estado acordado após o retorno. `orcamento_cliente` é nome de campo proposto para o valor em reais exigido na nova divisão; confirmar em `tests/importacao/contrato.py`. O acompanhamento durante a requisição depende da identificação antecipada do ID e do hook Realtime.

**Regras do formato:**
- `quantidade` é sempre número com ponto decimal (`12.5`), nunca texto.
- Unidades escritas sempre do mesmo jeito: `m`, `m2`, `m3`, `un`, `kg`, `l`, `cm`, `mm`.
- Colunas desconhecidas vão para `extras`, para nada se perder.
- O plano prevê um modelo em Python em `tests/importacao/contrato.py`. A pasta ainda será criada e commitada.

### Tabelas no Supabase

Samuel consolida o SQL único das quatro tabelas, incorporando os campos pedidos por Enzo e João. O esquema abaixo resume responsabilidades e ainda depende do contrato executável.
| Tabela | Para quê | Campos principais |
|---|---|---|
| `orcamentos` | Um por envio, acompanhado por Realtime | id, estado geral a fechar, nome, cep, orçamento do cliente, totais, logística, viabilidade, tempo e custo |
| `orcamento_itens` | Um por item, acompanhado por Realtime | orcamento_id, descrição original, classificação inicial, produto normalizado, marca, status (`buscando`/`definido`/`pendente_especificacao`/`nao_encontrado`/`erro`), pergunta, quantidade, unidade, embalagem, qtd_embalagens, preco_emb_min/med/max, confianca, estimativa, fontes (loja, dominio, url, preco_embalagem), imagem |
| `fornecedores` | Esquema pela A e cadastro pela C | nome, dominio, site, CEP, coordenadas, frete base, frete por km, pedido mínimo |
| `cache_precos` | Não pesquisar o mesmo produto duas vezes | chave do produto, resultado, validade |

### Saída de logística
```json
{ "estrategia": "loja_unica | dividir", "lojas": ["..."], "frete_total": 180.0, "economia_estimada": 95.0 }
```

### Perguntas em aberto para o Samuel
1. Qual framework e em qual pasta ou repositório vai ficar o site?
2. Quais variantes de Excel e layouts de PDF com texto estão nas amostras?
3. Falta algum campo no contrato para a tela?
4. Quais três obras serão usadas no botão de exemplo e qual delas demonstra dois erros e complementos na demo?

---

## 5. O que já está pronto

### Repositório (GitHub, privado)
```
src/            → backend FastAPI + agente (agent.py, tools.py, database.py, config.py, main.py)
prompts/        → prompt do agente
skills/         → guias para Claude Code / Codex / ChatGPT (ReAct, Featherless, Langfuse)
docs/briefing/  → 3 PDFs: oportunidades, dossiê técnico, plano de ação
scripts/check_setup.py → testa todas as conexões num comando
```

### Arquivos de teste planejados

As pastas `tests/importacao/` (100 casos previstos) e `docs/arquivos-teste/` (acervo previsto de 183 arquivos) ainda serão criadas e commitadas. As características abaixo descrevem o acervo planejado.
- **12 obras fictícias** em Recife e região (apartamento, casa, cozinha, banheiro, loja, escritório, clínica, restaurante, piscina, fachada, studio, casa de praia), com **endereços e CEPs reais**
- **15 formatos**:
  - Revit `.txt`, orçamento `.xlsx`, lista `.csv`, lista de WhatsApp `.txt`
  - SketchUp `.csv`/`.html`, memorial `.docx`, pedido de cotação e prancha em `.pdf`
  - foto de lista escrita à mão `.jpg`/`.png`
  - `.xls`, `.ods`, `.json`, `.xml`, `.tsv`, `.md`
- **Cerca de 116 produtos de marcas reais** (Suvinil, Coral, Portobello, Deca, Docol, Tigre, Quartzolit, Knauf, Blum, Gerdau…) escritos de 3 jeitos: completo, abreviado e **genérico** (que deve virar *Pendente de Especificação*)
- **Arquivos com problema de propósito:** corrompido, vazio, colunas trocadas, PDF escaneado, duplicados, acentos quebrados, fórmulas com `#REF!` etc.
- Índice previsto em `docs/arquivos-teste/LEIAME.md`.

### Armadilhas já descobertas (vale ler antes de codar)
- **O PapaParse pode confundir a vírgula decimal com o separador.** Use tabulação para o TXT tabulado do Revit e confira a amostra do time.
- **CSV salvo pelo Excel pode usar Windows-1252.** Teste também UTF-8 para preservar os acentos nas duas codificações.
- **O GLM-5.2 "pensa" antes de responder.** Com limite de tokens baixo, a resposta vem vazia.
- **Variáveis na Vercel nunca levam aspas.**
- **O pacote `xlsx` do npm está desatualizado e tem falhas de segurança.** Instalar o SheetJS pelo CDN oficial.

---

## 6. Contas e chaves

| Serviço | Status |
|---|---|
| Featherless | ✅ (cada um tem a própria chave, US$ 25 de crédito) |
| Supabase | ✅ |
| Langfuse | ✅ (região US) |
| Tavily | ✅ 1 chave. **Cada integrante deve criar a sua** em app.tavily.com (grátis, 1.000 buscas/mês por conta) |
| Vercel | ✅ todas as chaves configuradas |

- O arquivo `.env` com as chaves é enviado **no privado**. **Nunca** vai para o GitHub nem para o grupo do evento.
- Várias chaves do Tavily vão juntas, separadas por vírgula: `TAVILY_API_KEYS=tvly-aaa,tvly-bbb`.
- Lembrete: **cancelar o plano da Featherless** antes da primeira cobrança, se não for continuar usando.

---

## 7. Plano para o fim de semana

### Sábado
| Hora | O quê | Marco |
|---|---|---|
| 10h | Fechar contratos entre A/B/C e o SQL único da A | Cada fatia testa sua entrada |
| 10h–12h | Leitura dos arquivos + tabela editável no site · ligar Tavily/DuckDuckGo · tabelas no Supabase | |
| 12h–14h | Agente buscando preço de ponta a ponta + Realtime atualizando a tela | **14h: caminho feliz rodando** |
| 14h–16h | "Pendente de Especificação" + logística por CEP | |
| 16h–17h | Integrar revisão, exemplos, compra, pesquisa e frete | **17h — E1–E7 demonstráveis** |
| Noite | E8–E11 · domínio + e-mail (AWS) · slides · métricas · publicação | **link público estável** |

**Regra de corte:** se às 14h o caminho feliz não estiver rodando, corta escopo, não sono.

### Domingo
| Hora | O quê |
|---|---|
| até 10h30 | Corrigir só o que quebra a demo |
| 10h30 | **Congela as funcionalidades** |
| 10h30–11h30 | Gravar o vídeo (também é o plano B se a demo ao vivo falhar) |
| até 12h30 | **Submeter** (o prazo é 13h) |
| 13h–16h | Ensaiar o pitch pelo menos 5 vezes, com cronômetro |

### Roteiro do pitch (3 min)
| Tempo | Conteúdo |
|---|---|
| 0:00–0:25 | A dor com número (horas perdidas por orçamento) |
| 0:25–0:45 | A solução em uma frase |
| 0:45–2:00 | **Demo de aproximadamente 75 s** — exemplo, dois erros, aceite de correções e complementos, pesquisa, pergunta, Langfuse, viabilidade e exportação. |
| 2:00–2:35 | Negócio: quem paga, preço, mercado, por que agora |
| 2:35–3:00 | Ganho × custo por orçamento, e próximo passo |

---

## 8. Regras de ouro
- **Código do produto só a partir de sábado, 10h.** Commits pequenos e frequentes durante o evento.
- Nada de chaves no GitHub.
- Usar só dados fictícios.
- Se der dúvida sobre alguma regra, perguntar no grupo oficial do WhatsApp.
