# Orçamentista Autônomo

> Hackathon **Converge Challenge powered by Tako** · Porto Digital, Recife · 7–8/11/2026

O arquiteto sobe a lista de materiais do projeto e recebe, em poucos minutos, um estudo de viabilidade: preço
mínimo, médio e máximo de cada item **com as lojas de onde veio**, quantas embalagens comprar, o que ainda precisa
de especificação, onde comprar e se cabe no orçamento do cliente.

- **Repositório principal:** https://github.com/Joaomoura07/Converge-Challenge
- **Site:** https://converge-challenge-3k6i.vercel.app
- **API:** https://orca-api-x7k2.vercel.app (`/health`, `/docs`)
- **Demonstração:** [roteiro dos exemplos para os jurados](frontend/public/exemplos/demo/ROTEIRO.md). Comece pelo `teste_1`: de três a cinco materiais especificados, sem preços pré-preenchidos.

## O problema

Montar orçamento e estudo de viabilidade é trabalho manual: a lista sai do Revit, do SketchUp ou de uma planilha, e o
arquiteto pesquisa preço loja por loja, converte metro quadrado em latas e caixas e soma tudo. Uma lista de 50 itens
leva horas e cada preço fica sem rastro de onde veio.

## Como funciona

1. **Entrada:** nome, CEP e orçamento do cliente; lista importada (CSV, Excel — `.xlsx`, `.xls` e `.xlsm` —,
   TXT do Revit ou PDF com texto), planta em DXF, modelo BIM em IFC ou modelo SketchUp (SKP).
   Também aceita digitação manual e arquivos de exemplo. Todas as entradas alimentam a mesma lista editável para revisão.
2. **Revisão antes de gastar IA:** regras apontam erros (unidade incompatível, quantidade fora da faixa, duplicados,
   colunas trocadas) e sugerem itens que costumam faltar (argamassa e rejunte para porcelanato, selador para pintura).
   **Nada muda sem o clique do arquiteto.**
3. **Pesquisa agêntica, item por item, ao vivo na tela** (Supabase Realtime):
   - cache de preços (7 dias);
   - busca nas lojas (Tavily, DuckDuckGo de reserva) e em lojas da cidade da obra;
   - um modelo rápido lê cada anúncio, extrai preço e embalagem e confere se é o **mesmo produto**;
   - conferências sem IA descartam o que não presta: preço que não está escrito no anúncio, código do produto lido
     como preço, embalagem que não bate com o título, ferramenta no lugar do material, fonte que não é loja;
   - quando faltam lojas, um **agente ReAct** (GLM-5.2, tool calling) lê o que deu errado, reformula a busca e tenta
     de novo (até 2 vezes);
   - o cálculo (Python, sem IA) tira outliers, monta a faixa de preço, converte o quantitativo em embalagens com
     perda e dá a confiança.
4. **Item genérico** ("tinta branca") recebe faixa **estimada** e uma pergunta objetiva ao arquiteto. A resposta
   dispara uma nova pesquisa daquele item.
5. **Resultado:** plano de compra por loja, viabilidade (cabe ou quanto falta, com sugestões de economia), ganho de
   tempo e custo de IA, e exportação em Excel.

Regra de ouro: **nenhum preço sem fonte.** Cada pesquisa gera um trace no Langfuse com cada busca, cada chamada ao
LLM, tokens, custo e tempo.

## Arquitetura

```
 Site (Next.js, Vercel) ── POST /orcamentos ──▶ API FastAPI (Vercel)
        ▲                                         │ grava itens "buscando"
        │ Realtime                                ▼
   Supabase ◀── grava cada item pronto ── pesquisar_orcamento (mesma requisição)
   (orcamentos,                               ├─ cache_precos
    orcamento_itens,                          ├─ busca: Tavily / DuckDuckGo / lojas da região
    cache_precos)                             ├─ extração: Qwen3-32B (reserva Mistral Small 3.2)
                                              ├─ agente ReAct: GLM-5.2 (reserva Qwen3-32B)
                                              ├─ cálculo: embalagens, perda, faixa, confiança
                                              └─ fim: logística, viabilidade, ganho (Fatia C)
   Langfuse ◀── 1 trace por orçamento (sessão = id do orçamento)
```

| Pasta / arquivo | O que tem |
|---|---|
| `src/rotas_orcamentos.py` | `POST /orcamentos`: valida, classifica, grava e chama a pesquisa |
| `src/revisao.py`, `src/rotas_revisao.py` | Revisor E1 e `POST /revisao/sugestoes/completo` |
| `src/complementos.py` | Itens que costumam faltar (E2) |
| `src/pesquisa.py`, `src/busca.py`, `src/precos.py`, `src/calculo.py`, `src/compra.py`, `src/cache.py` | Pesquisa de preço (Fatia B) |
| `src/orcamento.py` | Pesquisa do orçamento no banco, "Pesquisar de novo" e "Responder" |
| `src/alternativas.py` | "Pesquisar de novo" buscando maior qualidade, menor preço ou semelhante |
| `src/logistica.py`, `src/viabilidade.py`, `src/ganho.py`, `src/exportar.py`, `src/rotas_resultado.py` | Resultado (Fatia C) |
| `src/agent.py`, `src/tools.py` | Loop ReAct e registro de ferramentas |
| `prompts/` | Prompts versionados |
| `sql/002_orcamentos.sql` | SQL único das tabelas, funções, RLS e Realtime |
| `frontend/` | Site (Next.js + TypeScript) |
| `tests/`, `frontend/src/**/*.test.ts` | Testes do backend (pytest) e do site (vitest) |

## Rodar localmente

Requer Python 3.11+ e Node 20+.

```bash
pip install -r requirements.txt
cp .env.example .env              # preencha as chaves
python -m scripts.check_setup     # valida Featherless, Langfuse, Supabase, Tavily
uvicorn src.main:app --reload     # API em http://localhost:8000
```

```bash
cd frontend && npm ci && npm run dev
```

Banco: rode `sql/002_orcamentos.sql` no SQL Editor do Supabase (pode rodar de novo: é idempotente) e confira com
`sql/verificar_supabase.sql`.

Testes: `python -m pytest tests` (backend) e `npm test` em `frontend/` (site).

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `FEATHERLESS_API_KEYS` | Chaves da Featherless separadas por vírgula (a pesquisa reparte a carga entre elas) |
| `FEATHERLESS_MODEL` | Modelo do agente (padrão `zai-org/GLM-5.2`) |
| `TAVILY_API_KEYS` | Chaves do Tavily separadas por vírgula (chave sem cota é pulada) |
| `SUPABASE_URL`, `SUPABASE_KEY` | Projeto Supabase; no backend, a chave `service_role` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Tracing (`https://us.cloud.langfuse.com`) |
| `PESQUISA_BUSCA_ABERTA` | `true` (padrão) busca também lojas da cidade da obra |
| `FRETE_ATIVO` | `false` (padrão): frete em pausa, o plano agrupa por loja sem custo de frete |
| `AGENT_RUN_ATIVO` | `false` (padrão): desliga `POST /agent/run`, o agente genérico do template |
| `NEXT_PUBLIC_API_URL` | No site: endereço da API **com** `https://` |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | No site: leitura e Realtime |

Lista completa em [`.env.example`](.env.example). **Nunca** faça commit do `.env`.

## Ferramentas, modelos e APIs

- **LLM:** Featherless, com `zai-org/GLM-5.2` (agente), `Qwen/Qwen3-32B` (extração),
  `mistralai/Mistral-Small-3.2-24B-Instruct-2506` (reserva da extração) e `google/gemma-4-31B-it` (alternativas)
- **Busca:** Tavily e DuckDuckGo (`ddgs`); CEP pelo ViaCEP
- **Dados e tempo real:** Supabase (Postgres, RLS, Realtime)
- **Observabilidade:** Langfuse
- **Backend:** FastAPI, Pydantic, OpenAI Python SDK; **site:** Next.js, React, TypeScript, PapaParse, SheetJS, PDF.js
- **Hospedagem:** Vercel

## Limites conhecidos

- Frete por CEP está em pausa (`FRETE_ATIVO`): o resultado diz "frete a confirmar".
- Item fora das lojas pesquisadas pode sair sem preço confirmado; nesses casos a tela mostra o motivo e oferece
  "Pesquisar de novo".
- PDF escaneado não é lido (sem OCR): a tela orienta usar CSV, Excel ou cadastro manual.
- Todos os dados de obras e clientes são fictícios.

## Time

- **Samuel Vasconcelos:** entrada, revisão e SQL (Fatia A)
- **Enzo:** pesquisa agêntica de preço (Fatia B)
- **João Pedro Moura Matos:** complementos, logística, viabilidade, exportação e site (Fatia C)
