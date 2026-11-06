---
name: tracing-with-langfuse
description: Instrumentação com Langfuse (SDK Python v5, baseado em OpenTelemetry) para traces auditáveis do agente, com nomes de spans, tokens e custo da Featherless, sessões, tags, scores/evals e o roteiro para mostrar traces ao vivo no Demo Day. Use ao adicionar uma tool ou etapa nova, ao depurar por que um trace não aparece, ao medir custo/latência ou ao preparar a demo para os jurados.
---

# Langfuse: tracing e observabilidade

Implementação de referência: `@observe` em `src/agent.py` e `src/tools.py`; `flush()` no lifespan de `src/main.py`.

## 1. Regra de ouro

**Toda execução do agente gera exatamente um trace**, com esta árvore:

```
agent.<nome>                (trace: trace_name, session_id, tags)
└── agent.run               (as_type="agent": input = tarefa, output = status + resposta)
    ├── llm.featherless     (as_type="generation": modelo, tokens, custo USD)
    ├── tool.execute        (as_type="tool": nome, args, Observation)
    ├── llm.featherless
    └── ...
```

Esse rastro é o que prova "autonomia com auditoria" para a banca.

## 2. Configuração

- Variáveis: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. O SDK lê direto do ambiente.
- Sem chaves reais (vazias ou placeholder), ou com `LANGFUSE_ENABLED=false`, `get_settings()` desliga o SDK (`LANGFUSE_TRACING_ENABLED=false`) e o app funciona normalmente, só sem traces.
- **Telemetria nunca derruba a resposta.** Toda chamada ao Langfuse fora do `@observe` (ex. `get_trace_url`, que consulta a API) fica em `try/except`, como em `Agent._attach_trace()`. Não comente `@observe` para "consertar" erro: corrija as chaves ou use o interruptor.
- Confira a conexão: `python -m scripts.check_setup` (usa `get_client().auth_check()`).
- O host deve bater com a região do projeto (EU `cloud.langfuse.com` / US `us.cloud.langfuse.com`). Região errada = 401.

## 3. API do SDK v5 (use estas, não exemplos antigos da internet)

```python
from langfuse import get_client, observe, propagate_attributes

@observe(as_type="tool", name="tool.buscar_candidato")   # span com tipo e nome
def buscar_candidato(...): ...

with propagate_attributes(trace_name="agent.triagem", session_id=caso_id,
                          user_id="recrutador_demo", tags=["demo"], metadata={"frente": "recrutamento"}):
    agent.run(...)                                          # atributos valem para o trace inteiro

lf = get_client()
lf.update_current_generation(model=..., usage_details={"input": n, "output": m},
                             cost_details={"total": usd})
lf.update_current_span(output=..., level="WARNING")        # marca execuções problemáticas
lf.score_current_trace(name="tarefa_concluida", value=1, data_type="BOOLEAN")
lf.get_trace_url(trace_id=lf.get_current_trace_id())
lf.flush()                                                  # obrigatório em scripts curtos
```

- `update_current_trace()` e o padrão `langfuse.trace(...)` **não existem** no v5. Use `propagate_attributes`.
- `as_type` aceita `span`, `agent`, `tool`, `chain`, `retriever`, `evaluator`, `guardrail`, `generation`, `embedding`. Com o tipo certo, a UI desenha a árvore direito.
- Não combine o wrapper `langfuse.openai` com a generation manual de `_complete_once`, senão cada chamada é contada duas vezes.

## 4. Convenções de nome e o que registrar

| Item | Nome | Obrigatório registrar |
|---|---|---|
| Trace | `agent.<nome_do_agente>` | `session_id` (caso/conversa), `tags` (`demo`, `eval`, frente) |
| Chamada ao LLM | `llm.featherless` | `model`, `usage_details` (input/output), `cost_details.total` |
| Tool | `tool.<nome_da_tool>` | args e Observation (automático via `@observe`) |
| Execução ruim | — | `level="WARNING"`/`"ERROR"` + `status_message` |

**Custo:** os modelos da Featherless não estão na tabela de preços do Langfuse. Por isso o custo é enviado **explicitamente** a partir de `usage.cost`. Sem isso, o dashboard mostraria US$ 0.

## 5. Medição (evals)

- Depois de cada execução de teste, registre scores: `tarefa_concluida` (BOOLEAN), `escalou_corretamente` (BOOLEAN), `custo_usd` (NUMERIC).
- Mantenha 5–10 casos fixos (caminho feliz + exceções) e rode-os com a tag `eval` sempre que mudar prompt ou tool. Compare no Langfuse por tag.
- Métricas para o pitch: taxa de conclusão, taxa de escalonamento, latência p50/p95 e custo médio por execução.

## 6. Privacidade

- Use somente dados sintéticos (regra do evento). Mesmo assim, não coloque segredos nem chaves em `input`/`metadata`.
- Para dados sensíveis, passe `capture_input=False`/`capture_output=False` no `@observe` e registre só um resumo com `update_current_span`.

## 7. Roteiro do Demo Day

1. Antes: rode 3–5 execuções de demo com a tag `demo` e o mesmo `session_id`, para ter histórico.
2. Deixe uma aba do Langfuse aberta em **Tracing → filtro `tags = demo`**.
3. Ao vivo: execute pela API/UI. A resposta traz `trace_url`, então abra direto o trace da execução que acabou de rodar.
4. Mostre a árvore (Thought → tool → Observation), a **latência** de cada passo e o **custo total** da execução.
5. Para jurados testarem sem login: `get_client().set_current_trace_as_public()` dentro da execução, ou compartilhe o trace pela UI.

## 8. Troubleshooting

| Sintoma | Causa provável |
|---|---|
| Nenhum trace aparece | Chaves ausentes ou região errada (veja o aviso no log), ou o script terminou sem `flush()` |
| `Failed to export spans … 401` / `Invalid credentials` | Chave placeholder, chave de outro projeto ou região errada. Rode `python -m scripts.check_setup` |
| Trace aparece "solto", sem filhos | Função chamada fora do contexto `@observe` (thread nova sem contexto OTel) |
| Custo zerado | `usage.cost` ausente (plano por assinatura) → cadastre o preço do modelo em *Settings → Models* |
| Generation duplicada | Wrapper `langfuse.openai` e generation manual ativos ao mesmo tempo |

## Referências

- Docs do SDK Python: https://langfuse.com/docs/observability/sdk/python/overview
- Tipos de observação: https://langfuse.com/docs/observability/features/observation-types
- Custos e tokens: https://langfuse.com/docs/observability/features/token-and-cost-tracking
