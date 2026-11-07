# Passagem da Fatia B (pesquisa de preço): o que está feito e o que falta

Escrito em 07/11, sábado à tarde, para quem vai continuar a Fatia B com o próprio Claude Code.
**Cole este arquivo inteiro no Claude como primeira mensagem** e peça para ele ler também `AGENTS.md`,
`docs/FATIAS-DO-TIME.md` e `docs/revisao/fatia-b.md` antes de mexer em qualquer coisa.

---

## 1. Contexto em 1 minuto
- Hackathon **Converge Challenge** (Porto Digital, Recife). Submissão **domingo 8/11 às 13h**; Demo Day às 16h (pitch de 3 min).
- Produto: **Orçamentista Autônomo**. O arquiteto sobe a lista de materiais → revisa numa tabela → "Enviar para a IA" →
  um agente pesquisa preço e imagem de cada item em lojas reais, mostra ao vivo (Supabase Realtime) e separa
  `definido` × `pendente_especificacao` (pergunta ao arquiteto quando o item é genérico).
- Fatias: **A** (Samuel) upload/revisão/SQL · **B** (Enzo → você) pesquisa de preço · **C** (João) itens esquecidos, frete, viabilidade, exportar · **D** negócio/pitch.
- Stack: FastAPI na Vercel (`main` faz deploy automático, **cuidado ao dar push na main**) · Featherless (LLM) ·
  Tavily (busca; DuckDuckGo de reserva) · Supabase · Langfuse (região US).
- Chaves: só no `.env` (o Enzo passa por WhatsApp). **Nunca commitar `.env` nem chave no código**
  (`tests/fatia_b/test_coerencia.py` procura chaves vazadas). Não editar `.env.example`.

## 2. Como trabalhar (o que o Enzo seguiu e funcionou)
```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
python -m scripts.check_setup                 # confere chaves: Featherless, Tavily (3 chaves), DuckDuckGo, Supabase, Langfuse
python -m pytest                              # ~350 testes offline, ~6 s (os que chamam serviço real ficam de fora)
python -m scripts.revisar --etapa N --real --nota "o que mudou"   # revisão de cada etapa (grava em docs/revisao/fatia-b.md)
```
- **Cada mudança passa pelo `scripts/revisar.py`**: sintaxe, testes offline, coerência com o contrato do time,
  `/health` e os testes reais da etapa (`-m real -k etapaN`). Teste real só "pulado" conta como **PENDENTE**, não aprovado.
- Depois da revisão automática, rodar o caso real à mão e anotar o achado em `docs/revisao/fatia-b.md`.
- Commits pequenos e frequentes (os organizadores podem pedir o histórico).

## 3. O fluxo de um item (o que já existe)
```
item ─▶ ① cache (cache_precos, 7 dias) ── achou ─▶ resultado em ~0,3 s
            │ não
            ▼
        ② busca (Tavily, 18 lojas BR fixas; DuckDuckGo de reserva) + 1 imagem verificada
            ▼
        ③ extração (Qwen3-32B /no_think, reserva Gemma 4): preço, embalagem, "é o mesmo produto?"
           trava anti-alucinação: preço que não está escrito no anúncio é descartado
            ▼
        ④ agente ReAct (GLM-5.2) SÓ se < 2 lojas com o mesmo produto: reformula a busca, até 2×;
           quem decide parar é o código (2 lojas ou buscas esgotadas), não o LLM
            ▼
        ⑤ cálculo (Python puro): preço por unidade base (R$/m², R$/L…), tira outliers (40–250% da mediana),
           1 oferta por loja, mín/mediana/máx, confiança, nº de embalagens com perda, embalagem de menor custo
            ▼
        ResultadoItem → grava em orcamento_itens (Realtime atualiza a tela) + cache
```
Item genérico → faixa **estimada** + pergunta por tipo de material (sem LLM). Só "parecidos" → vira pendente com estimativa.
Falha total → cache vencido ("preço de dd/mm") ou `nao_encontrado` com as consultas tentadas.

## 4. Arquivos (todos da Fatia B)
| Arquivo | O que faz | Etapa / revisão |
|---|---|---|
| `src/modelos.py` | Contrato B ↔ A/C (`ItemEntrada`, `Fonte`, `ResultadoItem` com regras: nunca preço sem fonte etc.) | — |
| `src/config.py` | Parâmetros `pesquisa_*` (3 LLM simultâneos, 8 buscas, 5 lojas, cache 7 dias, agente 40 s) | 1 ✅ |
| `src/busca.py` | Tavily + rodízio de 3 chaves + DuckDuckGo + escolha e verificação da imagem | 2 ✅ |
| `src/precos.py` + `prompts/extrator_precos.md` | Extração, trava anti-alucinação, reserva, `RespostaVazia` | 3 ✅ |
| `src/compra.py` | Entende embalagens ("caixa 2,16 m²", "kit 2 latas 18 L"), rendimento, consumo, perda | 4 ✅ |
| `src/calculo.py` | Normalização, outliers, mediana, confiança, embalagem de menor custo | 4 ✅ |
| `src/cache.py` + `sql/002_cache_precos.sql` | Cache no Supabase (tabela **já criada**), imagem estável por produto | 5 ✅ |
| `src/pesquisa.py` + `prompts/pesquisador_precos.md` | Orquestra o item + agente ReAct + pergunta ao arquiteto | 6 ✅ |
| `src/orcamento.py` | `pesquisar_orcamento(id)` (reserva atômica, grava item a item, chama a C) e `repesquisar_item` | 7 ✅ (banco real, 07/11 14:37) |
| `ui-fatia-b/` | Componentes React: `ItemRow`, `PriceDimension` (cota de preço), `StatusBadge` + prévia Vite | 8 ✅ |
| `scripts/aquecer_cache.py` | Pré-aquece o cache da demo e deixa metade "ao vivo" | 9 ✅ (com achado grave, ver P0-1) |
| `scripts/revisar.py`, `pytest.ini`, `tests/fatia_b/` | Revisão por etapa e testes (offline + `real`) | — |
| `docs/revisao/fatia-b.md` | **Diário de tudo que foi medido e corrigido** (leia antes de mudar algo) | — |

## 5. O que falta, em ordem de prioridade

> **Atualização 07/11 ~14h45 (continuação):** feitos P0-1 (duas fases: 1º item em 5,6 s; com metade em cache, 1,6 s),
> P0-2 (etapa 7 aprovada no banco real), P0-3 (rota `POST /orcamento-itens/{item_id}/repesquisar`, corpo opcional
> `{"nova_descricao": "..."}`), P1-6, P1-7 e P1-9, mais disjuntor de modelo fora do ar e adaptação ao SQL da fatia A
> (cache em `resultado` jsonb, `classificacao = pendente`). Números e achados em `docs/revisao/fatia-b.md`.
> **Ainda abertos:** P0-4 (conferir limite da função no painel da Vercel), P0-5 (componentes no site do Samuel),
> P1-8, P2. **Pedir ao Samuel:** `alter table orcamento_itens add column premissa text;`

### P0 — sem isso a demo não fica boa
1. **Desempenho com muitos itens (o mais importante).** Medido no aquecimento da Cozinha Graças (24 itens):
   - Featherless sobrecarregada devolve **HTTP 200 sem `choices`** (já tratado com nova tentativa).
   - Com o agente dividindo as mesmas 3 vagas de LLM com as extrações, o 1º item só chegou em **33 s**,
     o total foi **127 s** e o agente estourou os 40 s em **12 itens sem conseguir vaga**.
   - **Fazer:** em `src/pesquisa.py` (`pesquisar_itens`), separar em **duas fases**:
     fase 1 = caminho rápido de todos os itens (sem agente), gravando cada um assim que fica pronto;
     fase 2 = agente só nos itens com < 2 lojas, depois que a fase 1 acabar, com **cota própria** (ex.: 1 vaga de LLM).
     Meta: primeiros itens na tela em < 10 s; 20 itens com metade em cache ≤ 30 s.
   - Medir com `python -m scripts.aquecer_cache docs/arquivos-teste/03-cozinha-gracas/orcamento_cozinha-gracas.json`.
2. **Etapa 7 com o banco real.** O teste `test_etapa7_orcamento_real_no_supabase` está PENDENTE porque as tabelas
   `orcamentos` e `orcamento_itens` do Samuel ainda não existem. Quando ele rodar o SQL:
   `python -m scripts.revisar --etapa 7 --real`. O que o SQL dele precisa ter está no docstring de `src/orcamento.py`;
   **coluna nova a avisar: `premissa text`**. Ele **não** deve recriar `cache_precos` (já existe, com outro formato).
3. **Ligar no endpoint do Samuel.** O `POST /orcamentos` dele chama `await pesquisar_orcamento(orcamento_id)`
   **na mesma requisição** (a Vercel mata o que roda depois da resposta). Falta uma rota para o botão
   "Pesquisar de novo"/"Responder" chamar `repesquisar_item(item_id, nova_descricao)` (combinar com o Samuel quem cria em `src/main.py`).
4. **Tempo máximo da função na Vercel.** Um orçamento de 24 itens levou > 2 min. Conferir o limite do plano
   (*Settings → Functions*) e, para a demo, usar o cache pré-aquecido.
5. **Componentes no site do Samuel (Next.js).** Copiar `ui-fatia-b/src/components/orcamento/` para o site, importar
   `orcamento.css` no `app/layout.tsx`, ligar no Realtime de `orcamento_itens`. As cores em `ui-fatia-b/src/tokens.css`
   são provisórias: o time define (regras em `skills/04-ui-design.md`). Prévia: `npm --prefix ui-fatia-b install && npm --prefix ui-fatia-b run dev` → http://localhost:5174 (`?demo=1` = projetor).

### P1 — qualidade do resultado
6. **Embalagem errada vinda do LLM.** No porcelanato, a extração marcou o preço por m² da Ferreira Costa (R$ 88,90) como
   "caixa 1,8 m²" e ele virou o mínimo. Criar trava em `src/calculo.py`: oferta cujo preço por unidade base fica muito
   abaixo das outras lojas → conferir se a embalagem não é a unidade avulsa.
7. **Fonte que é página de busca.** Às vezes a URL da fonte é uma busca da loja (ex.: `magazineluiza.com.br/busca/...`),
   não o produto. Avaliar descartar URLs de busca em `src/busca.py` (`_filtra`).
8. **Itens não encontrados da cozinha** ("Fita LED Ledvance", "Tomada Liz 10A", "Corrediça Blum Tandembox", "Lixa Norton A275"):
   ver no Langfuse por que falharam; na demo eles são pesquisados ao vivo de novo (o cache não guarda falha).
9. O cache não guarda `iteracoes`: item aquecido não mostra "A IA refez a busca" na tela. Se quiser isso no pitch,
   deixar 1 item difícil para rodar ao vivo ou guardar as iterações junto das ofertas.

### P2 — pitch e depois
10. **Escolher o arquivo da demo** e aquecer na véspera (`--manter 0.5`; `--manter 1` se a rede do evento estiver ruim).
11. **Métricas para o pitch** (com a fatia D): % de itens resolvidos sozinhos, % que o agente refez, tempo e custo
    por orçamento (o custo vem da Featherless em `usage.cost` e aparece no Langfuse).
12. **Ideia guardada, não fazer agora:** importar o modelo IFC (BIM) no navegador — ver `docs/ideias/IFC-importacao.md`.
    Sobre o "Jev" (sugestão de um monitor): é um modelo que escolhe entre opções sem gerar texto; não extrai preço.
    Decisão: não adicionar agora; o "decidir sem LLM" já está em código (cálculo, confiança, parada do agente).

## 6. Números medidos (para não repetir experimento)
- Busca + extração de 1 item: ~5–12 s. Do cache: ~0,3 s. 6 itens em paralelo sem cache: 7–11 s cada (sem disputa).
- GLM-5.2 (agente): 9–13 s por chamada. Qwen3-32B sem `/no_think`: 34 s (pior); com `/no_think`: ~5 s.
- Featherless: Qwen3-32B = 2 unidades de concorrência, GLM-5.2 = 4. Sobrecarga = 200 sem `choices`.
- Tavily: não usar `country` junto com `include_domains` (volta 0 resultados). 3 chaves em `TAVILY_API_KEYS` (separadas por vírgula, sem aspas).

## 7. Regras que valem para o Claude de quem continuar
- Ler `AGENTS.md` e a skill da área antes de mexer (`skills/01..04`). Tela/estilo → `skills/04-ui-design.md`.
- Toda tool nova herda `ToolArgs`; decisões sobre pessoas nunca pelo agente; só dados sintéticos.
- Nunca inventar preço: sem fonte, sem preço (o `ResultadoItem` recusa).
- Rodar `scripts/revisar.py` a cada etapa e registrar o achado real em `docs/revisao/fatia-b.md`.
- Não dar push na `main` sem combinar com o time (deploy automático na Vercel).
