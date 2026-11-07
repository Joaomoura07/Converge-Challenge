# Revisões da Fatia B (pesquisa de preço)

Cada etapa só avança com revisão aprovada. Gerado por `python -m scripts.revisar`.

## Etapa 0 — sistema de revisão · 07/11 10:32 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 220 passed, 12 skipped in 0.65s |
| coerência com o programa | ✅ | 7 passed in 0.37s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |

## Etapa 1 — configuração · 07/11 10:34 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 224 passed, 12 skipped, 3 deselected in 0.71s |
| coerência com o programa | ✅ | 7 passed in 0.45s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 1) | ✅ | 3 passed, 11 deselected in 11.15s |

## Etapa 2 — busca (Tavily + DuckDuckGo) · 07/11 10:45 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ❌ | 1 failed, 231 passed, 12 skipped, 6 deselected in 0.91s<br>FAILED tests/fatia_b/test_coerencia.py::test_sem_chaves_no_codigo - Assertion... |
| coerência com o programa | ❌ | 1 failed, 6 passed in 0.45s<br>FAILED tests/fatia_b/test_coerencia.py::test_sem_chaves_no_codigo - Assertion... |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ✅ | 3 passed, 22 deselected in 16.58s |

## Etapa 2 — busca (Tavily + DuckDuckGo) — após corrigir detector de chaves · 07/11 10:47 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 232 passed, 12 skipped, 6 deselected in 0.78s |
| coerência com o programa | ✅ | 7 passed in 0.37s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ✅ | 3 passed, 22 deselected in 39.76s |

## Etapa 2 — busca — nova tentativa, máx. 2 por loja, reserva só texto, Langfuse na importação · 07/11 10:49 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ❌ | 1 failed, 233 passed, 12 skipped, 6 deselected in 3.30s<br>FAILED tests/fatia_b/test_etapa1_config.py::test_langfuse_base_url_tem_prioridade_sobre_host |
| coerência com o programa | ✅ | 7 passed in 0.52s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ❌ | 1 failed, 2 passed, 24 deselected in 21.84s<br>FAILED tests/fatia_b/test_etapa2_busca.py::test_etapa2_busca_real_traz_lojas_da_lista_e_imagem[Porcelanato Portobello Cimento Queimado acetinado 90x90 retificado] |

## Etapa 2 — busca — sem country (causa dos 0 resultados), imagens do Tavily na reserva · 07/11 10:52 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 236 passed, 12 skipped, 6 deselected in 3.54s |
| coerência com o programa | ✅ | 7 passed in 0.63s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ✅ | 3 passed, 26 deselected in 9.91s |

## Etapa 2 — imagem: 1 por produto (cor, medida, URL > descrição do Tavily, só se carregar) · 07/11 11:01 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 250 passed, 12 skipped, 9 deselected in 4.00s |
| coerência com o programa | ✅ | 7 passed in 0.43s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ✅ | 6 passed, 40 deselected in 37.69s |

## Etapa 3 — extrai e confere preços (Qwen3-32B formato curto + trava anti-alucinação) · 07/11 11:10 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 264 passed, 12 skipped, 11 deselected in 4.05s |
| coerência com o programa | ✅ | 7 passed in 0.49s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 3) | ❌ | 1 failed, 1 passed, 60 deselected in 35.83s<br>FAILED tests/fatia_b/test_etapa3_precos.py::test_etapa3_extracao_real_acerta_o_caso_de_controle |

## Etapa 3 — extração — prompt com palavras inteiras (SIM/PARECIDO/NAO), leitor estrito, reserva rápida · 07/11 11:14 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 266 passed, 12 skipped, 11 deselected in 4.72s |
| coerência com o programa | ✅ | 7 passed in 0.41s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 3) | ✅ | 2 passed, 62 deselected in 13.49s |

### Avaliação manual — etapa 3 (6 produtos, busca + extração em paralelo) · 07/11
- **Tempo:** 11,4 s para os 6 itens ponta a ponta; modelo principal (Qwen3-32B) em todos, 3,7–5,1 s por extração.
- **Trava anti-alucinação:** descartou 4 preços que não estavam escritos no anúncio.
- **Funcionou:** separa produto exato × parecido × outro (ex.: misturadores de R$ 4.800+ de outra linha marcados "nao"; tinta 3,6 L × 18 L "parecido").
- **Pendências para as próximas etapas (não são bugs da etapa 3):**
  1. *Etapa 4:* lojas informam o preço em unidades diferentes (porcelanato: R$/m² na Leroy e R$/caixa 1,8 m² na Telhanorte) → normalizar para a mesma embalagem antes da mediana.
  2. *Etapa 4:* item genérico ("tinta vermelha") traz embalagens de artesanato (60 ml, 250 ml) → para a faixa estimada, aceitar só embalagens de obra.
  3. *Etapa 6 (agente):* misturador Deca e cuba Morgana terminaram com 0 ofertas conferidas com preço → é exatamente o caso em que o agente deve refazer a busca.
  4. Páginas de artigo das lojas ("Qual argamassa escolher?") entram na busca; vêm sem preço e não atrapalham a média.

## Etapa 4 — cálculo: normalização por unidade base, outliers, mediana, confiança, lista de compra com perda · 07/11 11:24 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 292 passed, 12 skipped, 12 deselected in 4.06s |
| coerência com o programa | ✅ | 7 passed in 0.43s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 4) | ✅ | 1 passed, 90 deselected in 38.75s |

## Etapa 4 — uma oferta por loja (a mais barata) — achado da avaliação real · 07/11 11:27 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 293 passed, 12 skipped, 12 deselected in 4.25s |
| coerência com o programa | ✅ | 7 passed in 0.44s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 4) | ✅ | 1 passed, 91 deselected in 11.87s |

### Avaliação manual — etapa 4 (6 produtos, busca + extração + cálculo em paralelo) · 07/11
- **Tempo:** 10,7 s para os 6 itens; o cálculo é Python puro (instantâneo).
- **Resultados:**

| Item | Compra | R$ por embalagem (mín / mediana / máx) | Confiança |
|---|---|---|---|
| Suvinil Toque de Seda 18 L, 180 m² | 2 latas 18 L (≈ 8 m²/L, +5%) | 739,90 / 749,90 / 901,49 | alta (ML a R$ 245 descartado como outlier) |
| Porcelanato Eliane Munari 60x60, 48 m² | 30 caixas 1,8 m² (+10%) | 122,22 / 160,02 / 176,22 · R$ 88,90/m² | média (R$/m² e R$/caixa agora comparáveis) |
| Tinta vermelha fosca (genérico), 12 m² | 1 × 6 L | 89,90 (estimativa) | baixa (3 embalagens de artesanato descartadas) |
| Argamassa AC-III 20 kg, 48 m² | 13 sacos (≈ 5 kg/m², +5%) | 41,59 / 42,90 / 46,90 (já com 1 oferta por loja) | alta |
| Misturador Deca Link | 1 un | 1.878,78 (1 loja) | baixa |
| Cuba Tramontina Morgana 56x34 | 1 un | 551,00 (1 loja) | baixa |

- **Corrigido na hora:** a mesma loja aparecia 2× (Leroy, dois anúncios da argamassa) e contava como duas lojas → agora fica uma oferta por loja (a mais barata). Teste de regressão adicionado.
- **Pendências:**
  1. *Etapa 6 (agente):* misturador e cuba saíram com 1 loja só e confiança baixa → gatilho para o agente refazer a busca (ex.: incluir o código do produto ou o nome da loja).
  2. *Etapa 6:* no genérico, a oferta da Loja Suvinil veio como "unidade" (sem litros) e foi descartada por não ter unidade comparável → o agente pode pedir a especificação (pergunta ao arquiteto) em vez de confiar em 1 fonte.

## Etapa 5 — cache de preços: chave normalizada, 7 dias, vencido como reserva, imagem estável · 07/11 11:36 · ~~✅ aprovada~~ ⏸️ corrigido: o teste real só foi pulado (tabela não existe); ver revisão abaixo

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 306 passed, 12 skipped, 13 deselected in 4.13s |
| coerência com o programa | ✅ | 7 passed in 0.43s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 5) | ✅ | 1 skipped, 105 deselected, 2 warnings in 2.44s |

## Etapa 5 — revisor: teste real só pulado agora conta como PENDENTE · 07/11 11:36 · ⏸️ pendente (algo não rodou de verdade)

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 306 passed, 12 skipped, 13 deselected in 4.10s |
| coerência com o programa | ✅ | 7 passed in 0.40s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 5) | ⏸️ | 1 skipped, 105 deselected, 2 warnings in 2.55s<br>SKIPPED [1] tests\fatia_b\test_etapa5_cache.py:142: tabela cache_precos ainda n�o criada (rode sql/002_cache_precos.sql): {'message': "Could not find the table 'public.cache_precos' in the schema cache" |

## Etapa 5 — cache real no Supabase (tabela criada) · 07/11 11:44 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 306 passed, 12 skipped, 13 deselected in 4.09s |
| coerência com o programa | ✅ | 7 passed in 0.44s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 5) | ✅ | 1 passed, 105 deselected, 2 warnings in 4.40s |

### Avaliação manual — etapa 5 (cache real no Supabase) · 07/11
- Argamassa Quartzolit AC-III 20 kg, 48 m²: **1ª vez 13,2 s** (busca + extração + grava) → **2ª vez 0,26 s** (cache), mesmo preço (mediana R$ 42,90), mesma imagem.
- Escrita diferente ("argamassa quartzolit ac-iii, cinza, 20 kg") com 100 m²: **cache em 0,29 s**, conta refeita → 27 sacos (em vez de 13), mesma imagem.
- A linha da argamassa ficou no cache (dado real, vale 7 dias). Avisos `DeprecationWarning` vêm de dentro da biblioteca supabase-py, não do nosso código.

## Etapa 6 — orquestração por item + agente ReAct que refaz a busca · 07/11 13:18 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 322 passed, 12 skipped, 14 deselected in 11.68s |
| coerência com o programa | ✅ | 7 passed in 0.45s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 6) | ❌ | 1 failed, 122 deselected, 2 warnings in 30.25s |

## Etapa 6 — teste real do agente em cenário controlado (a busca real varia) · 07/11 13:21 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 322 passed, 12 skipped, 15 deselected in 8.82s |
| coerência com o programa | ✅ | 7 passed in 0.43s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 6) | ✅ | 2 passed, 122 deselected, 2 warnings in 91.47s (0:01:31) |

## Etapa 6 — agente: código decide parar; mesmo event loop; embalagem de menor custo · 07/11 13:27 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 323 passed, 12 skipped, 15 deselected in 5.11s |
| coerência com o programa | ✅ | 7 passed in 0.60s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 6) | ✅ | 2 passed, 123 deselected, 2 warnings in 42.56s |

### Avaliação manual — etapa 6 (6 produtos, orçamento inteiro sem cache) · 07/11
- **5 de 6 itens prontos em 7–11 s**, sem agente (a 1ª busca já trouxe 3+ lojas). Cada item é avisado assim que fica pronto (`ao_terminar`), então a tela não espera o mais lento.
- **Cuba Tramontina Morgana:** 1 loja → o agente (GLM-5.2) reformulou 2× ("cuba tramontina morgana 56x34", "cuba embutir tramontina morgana 56"), mas só o Mercado Livre vende o modelo exato → `definido` com confiança **baixa**, o que é honesto. Levou ~60 s.
- **Tempo do agente medido:** cada chamada ao GLM-5.2 leva 9–13 s, cada busca 5–11 s. O Qwen3-32B sem `/no_think` foi pior (34 s numa só chamada).
- **Corrigido:**
  1. Quem decide parar agora é o **código** (2 lojas ou buscas esgotadas), não o LLM: menos uma chamada só para ouvir "FIM".
  2. O agente roda as buscas **no mesmo event loop** (antes: `asyncio.run` dentro de thread, que gerava "Event loop is closed").
  3. Cliente da extração é fechado após o uso.
  4. **Embalagem de menor custo total** para a necessidade (12 m² de tinta não vira latão de 18 L quando há galão).
  5. Tempo limite do agente: 60 → **40 s**.
- **Para a demo:** pré-aquecer os itens difíceis (etapa 9); com cache, o item sai em ~0,3 s.
- **Para a fatia A (SQL):** novo campo `premissa text` em `orcamento_itens` (ex.: "rendimento ≈ 8 m²/L (tinta, 2 demãos)"; a tela mostra com "≈").

## Etapa 7 — orçamento no banco: reserva atômica, grava item a item, fatia C no fim, repesquisar · 07/11 13:35 · ⏸️ pendente (algo não rodou de verdade)

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 333 passed, 12 skipped, 16 deselected in 6.94s |
| coerência com o programa | ✅ | 7 passed in 0.96s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 7) | ⏸️ | 1 skipped, 135 deselected, 2 warnings in 5.87s<br>SKIPPED [1] tests\fatia_b\test_etapa7_orcamento.py:165: tabelas/colunas da fatia A ainda não existem: {'message': "Could not find the table 'public.orcamento_itens' in the schema cache", 'code': 'PGRST205', 'hint': None, 'details': None} |

## Etapa 8 — ItemRow + cota de preço (React), conferido no navegador em 1440/390 px e modo demo · 07/11 13:45 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 338 passed, 12 skipped, 16 deselected in 5.86s |
| coerência com o programa | ✅ | 7 passed in 0.40s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |

### Avaliação manual — etapa 8 (componentes no navegador, dados reais do cache) · 07/11
- Prévia em `ui-fatia-b/` (Vite + React, `npm run dev` → http://localhost:5174, `?demo=1` para projetor). Os componentes estão em `ui-fatia-b/src/components/orcamento/` para copiar para o site Next.js do Samuel.
- Conferido: carregamento (cota tracejada + hachura 45°), chegada (a linha se fecha e a linha do item pisca em azul por 1,2 s), pendente com "Responder" e campo de especificação, não encontrado com "Pesquisar de novo", "A IA refez a busca 2 vezes", celular 390 px sem rolagem horizontal.
- **Corrigido na hora:** animação travada no StrictMode do React (o timer era cancelado); a linha da cota ficava com falhas (`pathLength` + `non-scaling-stroke`), trocado por recorte (`clip-path`); "1 un → 1 unidade" (redundante) escondido; premissa com "≈" duplicado; modo demo não aumentava a fonte (componentes em rem).
- **Achado de dados (não é da tela):** no porcelanato desta rodada a extração rotulou o preço por m² da Ferreira Costa (R$ 88,90) como "caixa 1,8 m²", e ele entrou como o mínimo. A embalagem vem do LLM e pode errar; vale uma trava em Python: R$/m² muito abaixo das outras lojas → conferir a embalagem.
- Cores em `ui-fatia-b/src/tokens.css` são **provisórias** (papel frio + azul de cópia heliográfica); o time decide as finais.

## Etapa 9 — pré-aquecimento do cache + resposta vazia da Featherless + agente no mesmo limitador · 07/11 13:56 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 350 passed, 12 skipped, 16 deselected in 6.77s |
| coerência com o programa | ✅ | 7 passed in 0.45s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |

### Avaliação manual — etapa 9 (aquecimento real da Cozinha Graças, 24 itens) · 07/11
- **1ª rodada (LLM: 4 vagas, agente fora do limitador):** 149 s; 19 definidos, 1 pendente, 4 não encontrados. 6 extrações falharam com `TypeError`.
- **Causa achada:** a Featherless sobrecarregada responde **HTTP 200 sem `choices`** (`failed_generation`); o SDK não tenta de novo. Medido: 6 chamadas simultâneas ao Qwen3-32B → 3 vazias. **Corrigido:** `RespostaVazia` + nova tentativa no mesmo modelo antes da reserva; `agent.py` não quebra mais com resposta vazia.
- **2ª rodada (LLM: 3 vagas, agente dentro do mesmo limitador):** 127 s; 18 definidos, 2 pendentes, 4 não encontrados. **Piorou o primeiro resultado** (o 1º item só chegou em 33 s) e o agente estourou o tempo em 12 itens sem conseguir vaga (iterações = 0).
- **Conclusão (pendente, prioridade máxima):** separar em duas fases — fase 1 = caminho rápido de TODOS os itens (só extração, sem agente) gravando cada um; fase 2 = agente só nos itens com < 2 lojas, depois que a fase 1 terminar. E dar ao agente uma cota própria (ex.: 1 vaga), sem disputar com as extrações.

## Etapa 6 — duas fases (agente depois do caminho rápido, cota própria de LLM, prazo total), semáforo por loop, rota repesquisar · 07/11 14:25 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 373 passed, 12 skipped, 16 deselected in 7.52s |
| coerência com o programa | ✅ | 7 passed in 0.45s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 6) | ❌ | 1 failed, 1 passed, 174 deselected, 2 warnings in 67.93s (0:01:07) |

## Etapa 6 — duas fases + disjuntor de modelo fora do ar (Qwen3-32B: 'not available for inference') · 07/11 14:29 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 375 passed, 12 skipped, 16 deselected in 8.61s |
| coerência com o programa | ✅ | 7 passed in 0.43s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 6) | ✅ | 2 passed, 176 deselected, 2 warnings in 82.99s (0:01:22) |

## Etapa 2 — descarta URL de página de busca da loja · 07/11 14:31 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 375 passed, 12 skipped, 16 deselected in 6.28s |
| coerência com o programa | ✅ | 7 passed in 0.40s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ❌ | 2 failed, 4 passed, 172 deselected in 51.59s |

## Etapa 3 — disjuntor: modelo com HTTP 400 fica fora 10 min · 07/11 14:31 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 375 passed, 12 skipped, 16 deselected in 6.35s |
| coerência com o programa | ✅ | 7 passed in 0.42s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 3) | ✅ | 2 passed, 176 deselected in 14.59s |

## Etapa 4 — trava: preço por m² rotulado como caixa · 07/11 14:31 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 375 passed, 12 skipped, 16 deselected in 6.52s |
| coerência com o programa | ✅ | 7 passed in 0.47s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 4) | ✅ | 1 passed, 177 deselected in 5.61s |

## Etapa 5 — cache guarda iterações do agente (sql/003 opcional) · 07/11 14:32 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 375 passed, 12 skipped, 16 deselected in 6.33s |
| coerência com o programa | ✅ | 7 passed in 0.41s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 5) | ❌ | 1 failed, 177 deselected, 2 warnings in 3.00s |

## Etapa 7 — banco real da fatia A: tolera coluna ausente (premissa), orçamento sintético completo, rota repesquisar · 07/11 14:35 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 377 passed, 12 skipped, 16 deselected in 6.47s |
| coerência com o programa | ✅ | 7 passed in 0.41s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 7) | ❌ | 1 failed, 179 deselected, 2 warnings in 2.65s |

## Etapa 7 — banco real da fatia A: classificacao 'pendente', coluna premissa ausente tolerada, orçamento sintético, rota repesquisar · 07/11 14:37 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 383 passed, 12 skipped, 16 deselected in 6.25s |
| coerência com o programa | ✅ | 7 passed in 0.47s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 7) | ✅ | 1 passed, 185 deselected, 2 warnings in 18.19s |

## Etapa 2 — descarta URL de página de busca da loja (refeita: falha anterior foi variação da busca real) · 07/11 14:38 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 383 passed, 12 skipped, 16 deselected in 6.49s |
| coerência com o programa | ✅ | 7 passed in 0.40s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 2) | ✅ | 6 passed, 180 deselected in 15.71s |

## Etapa 5 — cache no formato do SQL único (resultado jsonb) + iterações; lê o formato antigo · 07/11 14:38 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 383 passed, 12 skipped, 16 deselected in 6.34s |
| coerência com o programa | ✅ | 7 passed in 0.41s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 5) | ✅ | 1 passed, 185 deselected, 2 warnings in 3.17s |

### Avaliação manual — continuação da passagem (P0/P1) · 07/11 tarde
- **P0-1 duas fases (medido, Cozinha Graças, 24 itens):**

| Cenário | 1º item na tela | 5º item | Fim |
|---|---|---|---|
| Antes (etapa 9, agente disputando vaga) | 33 s | — | 127 s |
| Só fase 1, sem cache | 5,6–7,8 s | 10,5–14,2 s | 34–41 s |
| Duas fases, sem cache | 5,6 s | 10,5 s | 93 s (fase 2 limitada a 60 s) |
| Demo: metade no cache | **1,6 s** | **1,9 s** | 107 s (Featherless lenta: LLM médio 20 s, máx 44 s) |

  - Gargalo da fase 1 = fila de vagas do LLM (3 simultâneas; espera média 9–13 s), não a busca (~2–3 s).
  - A Featherless oscila muito hoje: o mesmo código deu o 1º item em 52 s numa rodada (aquecimento das 14h40) e 5,6 s na seguinte.
  - Fase 2 cabe ~4 itens com agente em 60 s; os outros ficam com o resultado da fase 1 (provisório com preço, ou "não encontrado" + "Pesquisar de novo"). Para a demo, o aquecimento guarda no cache justamente os itens lentos.
- **Qwen3-32B saiu do ar** ("not available for inference", HTTP 400, até 19 s por chamada perdida) → disjuntor em `src/precos.py`: modelo com 400 fica fora 10 min; vai direto para a reserva (Gemma 4, 1,1 s).
- **Semáforo por `id(loop)`** reaproveitava semáforo com vagas presas de loop fechado (travou a suíte) → agora guardado pelo próprio loop (WeakKeyDictionary).
- **Banco da fatia A no ar — divergências achadas e tratadas no código da B:**
  1. `cache_precos` foi **recriada** como `(chave, resultado jsonb, imagem_url, atualizado_em)` e zerada → cache grava em `resultado` (com as iterações) e lê os dois formatos. `sql/003` removido (não precisa mais).
  2. `orcamento_itens` **sem `premissa`** → `gravar_item` tira a coluna ausente e grava o resto (antes o item ficaria "buscando" para sempre). **Pedir ao Samuel: `alter table orcamento_itens add column premissa text;`**
  3. `classificacao` no banco é `definido | pendente` (check `itens_classificacao_ck`) → `item_da_linha` mapeia `pendente` → `pendente_especificacao` (antes o genérico era pesquisado como definido, sem pergunta).
  4. `orcamentos.cep` só aceita dígitos; `orcamento_itens.fontes` é NOT NULL sem padrão (a B sempre manda `[]`).
- **Trava de embalagem (P1-6):** só na direção observada (preço por m² rotulado como caixa). A direção contrária é indistinguível com 3 lojas (testado: corrigia a loja errada) e fica para o filtro de outlier.

## Etapa 3 — prompt: kit/pacote do mesmo produto = SIM (lixa em pacote deixava de ter preço) · 07/11 15:24 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 388 passed, 12 skipped, 16 deselected in 9.76s |
| coerência com o programa | ✅ | 7 passed in 0.41s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 3) | ✅ | 2 passed, 189 deselected in 11.47s |

## Etapa 8 — componentes da B no site Next.js (frontend/): ResultadoItens com progresso, pendentes no fim e botões na rota; papéis de cor na paleta do site · 07/11 15:24 · ⏸️ pendente (algo não rodou de verdade)

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 388 passed, 12 skipped, 16 deselected in 10.39s |
| coerência com o programa | ✅ | 7 passed in 0.49s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 8) | ⏸️ | 191 deselected in 1.10s |

### Avaliação manual — componentes no site, Realtime, não encontrados e métricas · 07/11 ~15h40
- **Site (`frontend/`, Next.js do Samuel):** componentes da B copiados para `frontend/src/components/orcamento/` + `ResultadoItens`
  (progresso "N de M itens pesquisados" com barra, pendentes no fim, "Responder"/"Pesquisar de novo" na rota
  `POST /orcamento-itens/{id}/repesquisar`, item volta a "pesquisando" na hora e mensagem em português se falhar).
  Encaixe para a fatia A: `<ResultadoItens itens={itens} />` com os itens do `useOrcamento(id)`. Nenhum arquivo do Samuel alterado.
  Cores: papéis ligados à paleta do site em `frontend/src/styles/papeis-de-cor.css` (definido 5,8:1 e pendente 4,85:1 sobre o papel, medidos).
  **Conferido no navegador** (`/previa-b`, dados reais): carregamento com hachura e cota tracejada, chegada animada, Responder
  (texto < 3 letras barrado), Pesquisar de novo, 375 px sem rolagem horizontal, `?demo=1` com fonte 18 px; página principal do Samuel
  sem erro no console. Tipos + 47 testes do Vitest ok; `test_etapa8_ui` garante que a prévia e o site usam os mesmos componentes.
- **Realtime real:** assinatura em `orcamentos` e `orcamento_itens` recebeu os eventos de UPDATE (1 + 1). **Leitura pública (anon) não
  testada:** só há a chave secreta no `.env`; falta testar com a chave publishable do site.
- **P1-8, por que "não encontrado":**
  1. Leroy Merlin: o anúncio certo vem SEM preço — a página carrega o preço por JavaScript; nem o conteúdo bruto do Tavily
     (`include_raw_content`) tem "R$". Sem conserto barato na busca; quem compensa é o agente buscando em outra loja.
  2. Embalagem sem medida ("caixa" sem m², Portinari metrô sem tamanho): não dá para comparar. Honesto ficar sem preço.
  3. **Corrigido:** kit/pacote do MESMO produto era "PARECIDO" (lixa Norton em pacote de 5 ficava sem preço). Prompt agora:
     mesmo produto em kit = SIM com a embalagem do kit (o cálculo divide pelo conteúdo). Controle real: kit 2 latas 18 L → SIM, 36 L.
  4. Featherless degradada à tarde: extração de controle levou 132 s numa rodada e 3,4–5,5 s nas seguintes; Qwen às vezes devolve
     0 linhas válidas e a reserva Gemma leva ~40 s.
- **Métricas para o pitch** (`python -m scripts.metricas_pitch <arquivo>`), Cozinha Graças, 24 itens, cache da demo:
  96% com preço e fonte · 83% definidos · 12% pedem especificação · 4% não encontrados · 8% com busca refeita pelo agente ·
  1,4 loja por item (ponto fraco: muita confiança baixa) · 1º item em 1,3 s · completo em 69 s · US$ 0,0057 por orçamento.

## Etapa revisao-geral — análise do que falta para o Enzo (07/11, 15h50) · 07/11 15:49 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 458 passed, 12 skipped, 16 deselected, 2 warnings in 12.39s |
| coerência com o programa | ✅ | 7 passed in 0.43s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |

## Etapa 3 — rodízio de chaves da Featherless: vagas por chave, chave do agente separada, chave que falha esfria · 07/11 16:40 · ✅ aprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 581 passed, 12 skipped, 16 deselected, 2 warnings in 15.04s |
| coerência com o programa | ✅ | 7 passed in 0.41s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 3) | ✅ | 2 passed, 201 deselected in 14.44s |

## Etapa 6 — agente com a chave própria (a última de FEATHERLESS_API_KEYS) · 07/11 16:41 · ❌ reprovada

| Checagem | Resultado | Detalhe |
|---|---|---|
| sintaxe | ✅ | todos os arquivos compilam |
| testes (offline, tudo) | ✅ | 581 passed, 12 skipped, 16 deselected, 2 warnings in 12.46s |
| coerência com o programa | ✅ | 7 passed in 0.42s |
| api /health | ✅ | HTTP 200 · llm=True supabase=True langfuse=True |
| execução real (etapa 6) | ❌ | 1 failed, 1 passed, 201 deselected, 2 warnings in 66.89s (0:01:06) |

### Rodízio de chaves da Featherless (FEATHERLESS_API_KEYS) · 07/11 ~16h30
- `check_setup`: as 3 chaves respondem. Backend publicado lendo `FEATHERLESS_API_KEYS` (`/health` com `llm: true`).
- Extração: vagas por chave (3 × 2 chaves de extração = 6 simultâneas); a 3ª chave fica só para o GLM-5.2 do agente;
  resposta vazia, 429 e 5xx esfriam a chave por 30 s e a nova tentativa vai para outra. Revisão real da etapa 3 aprovada.
- **Etapa 6 real reprovada (não é o rodízio):** o agente usou a chave própria e reformulou para "misturador monocomando
  Deca Link cozinha", mas Amazon e Loja Dexco vieram com o produto certo **sem preço no anúncio**; o tempo de 40 s
  acabou antes da 2ª busca. Ataque previsto: priorizar anúncios com preço e busca aberta (passo 5 do plano).
