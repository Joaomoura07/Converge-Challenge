---
name: integrating-featherless
description: Integração com a Featherless AI (API compatível com OpenAI) como gateway de LLM deste repositório, cobrindo configuração por .env, escolha de modelo por tarefa, tool calling, limites de concorrência, tratamento de erros 400/401/403/429/500/503, modelo reserva e controle de custo dos créditos. Use ao chamar um LLM, trocar de modelo, depurar erro da Featherless ou estimar custo por execução.
---

# Featherless AI: integração e fallback

Implementação de referência: `build_llm_client()` e `Agent._complete()` em `src/agent.py`; configuração em `src/config.py`.

## 1. Configuração

- Cliente: SDK `openai` com `base_url=https://api.featherless.ai/v1`. Não use `requests` cru para chamar o LLM.
- Chaves: **só** via `.env` → `FEATHERLESS_API_KEYS` (várias, separadas por vírgula; `FEATHERLESS_API_KEY` antiga continua aceita) → `get_settings().featherless_keys` / `featherless_key` (a 1ª). Nunca faça hardcode, nunca mande ao front-end, nunca faça commit. Não espalhe `os.getenv` pelo código: centralize em `src/config.py`.
- Cada integrante tem a **própria** chave e US$ 25. Saldo zerado = requisições param.
- Antes de codar, confira tudo com:

```bash
python -m scripts.check_setup                         # chat + tool calling + Langfuse + Supabase
python -m scripts.check_setup --model Qwen/Qwen3-32B  # testar outro modelo
```

## 2. Modelo por tarefa

| Uso | Variável | Modelo sugerido | Observação |
|---|---|---|---|
| Raciocínio, planejamento, JSON complexo, código | `FEATHERLESS_MODEL` | `zai-org/GLM-5.2` | Recomendado pelo evento. Tool calling nativo **confirmado** via `check_setup` em 05/11/2026. Modelo de raciocínio: não use `max_tokens` baixo (a resposta pode vir vazia) |
| Reserva automática (400/503) **e** tool calling garantido | `FEATHERLESS_MODEL_FALLBACK` | `Qwen/Qwen3-32B` | Família com tool calling nativo documentado |
| Classificar, resumir, formatar texto | `FEATHERLESS_MODEL_FAST` | `google/gemma-4-31B-it` | Mais barato. Não confie em tool calling sem testar |

Regra prática: use o modelo grande só onde ele muda o resultado. Uma subtarefa de classificação ou extração simples pode usar `Agent(model=get_settings().featherless_model_fast)`.

## 3. Concorrência

A Featherless limita **unidades concorrentes (CU)**, não requisições por minuto. Cada requisição reserva o custo do modelo enquanto está em andamento:

| Tamanho do modelo | Custo |
|---|---|
| < 16B | 1 CU |
| < 35B | 2 CU |
| ≥ 70B | 4 CU |

O custo exato fica na página de cada modelo. Passou do orçamento do plano → **HTTP 429**. Na prática:
- Não dispare dezenas de chamadas paralelas com modelo grande. Use um semáforo pequeno (2–4) se paralelizar.
- Cada integrante tem a própria chave, e portanto o próprio orçamento de CU. Durante testes de carga, distribua as chaves.

## 4. Erros HTTP

| Código | Significado | Ação |
|---|---|---|
| **400** | Modelo frio/carregando, ou parâmetro inválido (ex. `max_tokens` acima do limite) | Não insista: o código cai no **reserva**. Se persistir, revise os parâmetros. Modelos frios podem levar de 5 min a 1 h para aquecer |
| **401** | Chave não reconhecida | Confira o `.env` / gere outra chave |
| **403** | Modelo restrito (gated) | Página do modelo → *Unlock Model* → aceitar licença |
| **429** | Orçamento de concorrência estourado | Backoff (automático via SDK) e menos paralelismo |
| **500** | Falha do lado deles, ou parâmetro não suportado | Remova parâmetros exóticos. Retry automático |
| **503** | Sem capacidade no momento para o modelo | Retry; depois de 3 tentativas, troque de modelo (o **reserva** faz isso) |

**Backoff:** não escreva `sleep(2/4/8)` à mão. O SDK já faz backoff exponencial com jitter (0,5 s → 8 s) em 408/409/429/5xx, controlado por `LLM_MAX_RETRIES` (padrão 3). Depois disso, `Agent._complete()` tenta `FEATHERLESS_MODEL_FALLBACK` uma vez em 400/503. Se o reserva também falhar, a execução termina com `status="error"`, que fica visível no trace.

## 5. Parâmetros

- Documentados: `temperature`, `top_p`, `top_k`, `min_p`, `max_tokens`, `stop`, `stream`, penalidades, `tools`.
- `seed` **não é confiável** (vários servidores). Para reprodutibilidade, use `temperature` baixa (0–0,2).
- `response_format` só aparece no workaround de tool calling simulado. Teste antes de depender dele.
- Mantenha os parâmetros mínimos: parâmetro não suportado pode virar 500.

## 6. Custo

- Toda resposta traz `usage.prompt_tokens`, `usage.completion_tokens` e, no plano por requisição, **`usage.cost` em USD**.
- O loop soma isso em `AgentResult.cost_usd` e envia a cada generation do Langfuse (`cost_details`).
- No pitch, mostre **custo por execução × custo do processo manual** que ela substitui. Essa conta é pedida explicitamente no Desafio Tako.
- Para economizar: prompts de sistema curtos, tools com retornos enxutos, histórico sem payloads gigantes e modelo rápido nas subtarefas simples.

## Referências

- Tool Calling: https://featherless.ai/docs/tool-calling
- Concorrência: https://featherless.ai/docs/concurrency-limits
- Códigos de erro: https://featherless.ai/docs/api-reference-error-codes
- Chat completions (parâmetros e `usage`): https://featherless.ai/docs/completions
- Catálogo de modelos: https://featherless.ai/models
