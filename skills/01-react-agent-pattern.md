---
name: building-react-agents
description: Padrão ReAct robusto (Thought → Action → Observation → Final Answer) para os agentes deste repositório, com tools tipadas em Pydantic, autocorreção limitada a 3 falhas e escalonamento humano. Use ao criar ou alterar um agente, uma tool, o loop em src/agent.py, o system prompt, ou ao decidir quando o agente deve parar e chamar um humano.
---

# Padrão ReAct Robusto (Reasoning + Acting + Safety)

Implementação de referência: `src/agent.py` (loop) e `src/tools.py` (tools). Siga-as; não crie um loop paralelo.

## 1. O ciclo

| Etapa | Onde vive no código | Regra |
|---|---|---|
| **Thought** | `message.content` que acompanha os `tool_calls` → `AgentStep.thought` | Curto. Diz o que falta e qual tool resolve. |
| **Action** | `tool_call` **nativo** (function calling), args em JSON | Uma intenção por chamada. Nome e args exatamente como no schema. |
| **Observation** | `ToolRegistry.execute()` → `{"ok": true, "result": ...}` ou `{"ok": false, "error": "..."}` | Sempre volta ao modelo, inclusive erro. Nunca levanta exceção. |
| **Final Answer** | Mensagem **sem** `tool_calls` | Só quando todas as dependências estão resolvidas, ou via `escalate_to_human`. |

**Por que tool calling nativo em vez de parsear texto `Action:`?** Ele elimina erros de regex/parse, dá JSON estruturado e permite várias ações por turno. O formato texto só serve como fallback (seção 5).

## 2. Tools: tipagem estrita

```python
from pydantic import Field
from src.tools import ToolArgs, registry

class BuscarCandidatoArgs(ToolArgs):            # ToolArgs = extra="forbid"
    candidato_id: str = Field(description="ID no ATS, ex.: 'cand_123'", pattern=r"^cand_\w+$")

@registry.tool(description="Busca dados de UM candidato no ATS. Use antes de qualquer ação sobre ele.")
def buscar_candidato(args: BuscarCandidatoArgs) -> dict:
    ...
```

- Herde de `ToolArgs`: campos inventados pelo LLM viram erro de validação, em vez de serem ignorados em silêncio.
- Use `Literal[...]`/`Enum`, `pattern`, `ge`/`le` e `description` em todo campo. O schema **é** a documentação que o modelo lê.
- A `description` da tool diz **o que faz, quando usar e quando não usar**. Trate-a como a docstring mais importante do projeto (o que a Anthropic chama de "agent-computer interface").
- Falha de validação volta ao modelo como `Argumentos inválidos: <erro Pydantic>` e ele corrige na iteração seguinte. Já está implementado.
- Retorne dicts pequenos e relevantes. Não despeje payloads de API inteiros (custa tokens e confunde o modelo).
- Tools que **escrevem** (enviar e-mail, cadastrar, alterar folha) devem ser idempotentes (aceitar `idempotency_key`) ou ter `dry_run: bool = True`. O agente pode repetir uma ação depois de um erro.

## 3. Erros e autocorreção (self-healing)

| Tipo de erro | Quem trata | Como |
|---|---|---|
| Transitório (timeout, 429, 5xx) **dentro da tool** | A própria tool | Retry com backoff *dentro* da tool antes de devolver erro |
| Transitório **no LLM** | SDK OpenAI + modelo reserva | `LLM_MAX_RETRIES` + `FEATHERLESS_MODEL_FALLBACK` (skill `integrating-featherless`) |
| Validação / 4xx de negócio | O agente | Erro na Observation → ele corrige os argumentos |
| **3 falhas consecutivas de tool** | O loop | Para e devolve `status="escalated"` (`MAX_CONSECUTIVE_FAILURES`) |
| Passos esgotados | O loop | `status="max_steps_reached"` (`AGENT_MAX_STEPS`) |

Mensagem de erro boa diz **o que** falhou e **como corrigir** (`"timezone inválido: use IANA, ex. America/Recife"`). Mensagem ruim é `"Error"`.

## 4. Guarda de escopo e human-in-the-loop

- **Nunca inventar** identidades, CPFs, valores financeiros, datas legais ou regras de negócio. Se uma tool pode fornecer o dado, chame-a. Se nenhuma pode, escale.
- **Dado crítico faltando ou instrução ambígua** → chame `escalate_to_human(reason, summary, question, recommendation)`. O loop encerra com `status="escalated"` e o contexto pronto para decisão.
- **Decisões sobre pessoas** (contratar, demitir, promover, salário, avaliação) → o agente **prepara**, o humano **decide**. Isso é restrição do Desafio Tako.
- Use somente dados sintéticos. Não registre dados pessoais reais em prompts, logs ou traces.

## 5. Fallback para modelos sem tool calling nativo

A doc da Featherless lista tool calling nativo para **Qwen 3** e **Kimi-K2**. Teste o seu modelo com `python -m scripts.check_setup --model <id>`. Se ele responder sem `tool_calls`:

1. **Preferido:** troque `FEATHERLESS_MODEL` (ou só o reserva) para um modelo com suporte nativo, ex. `Qwen/Qwen3-32B`.
2. **Alternativa:** ReAct em JSON com `response_format={"type": "json_object"}`, pedindo ao modelo **um** destes objetos por turno, validado com Pydantic:

```json
{"thought": "...", "action": "nome_da_tool", "action_input": {"...": "..."}}
{"thought": "...", "final_answer": "..."}
```

## 6. Checklist ao criar/alterar um agente

- [ ] Toda tool nova tem args `ToolArgs`, `description` com "quando usar" e retorno enxuto
- [ ] Tools de escrita são idempotentes ou têm `dry_run`
- [ ] O system prompt (`prompts/`) cita quando escalar e o formato da resposta final
- [ ] Rodou o caminho feliz **e** pelo menos uma exceção (dado faltando, tool falhando)
- [ ] O trace no Langfuse mostra Thought, Actions e custo (skill `tracing-with-langfuse`)
- [ ] Existe um caso de teste (eval) para o comportamento novo. 5–10 casos fixos já separam "funciona" de "teve sorte"

## Anti-padrões

- Loop sem limite de passos, ou retry infinito da mesma ação com os mesmos argumentos
- Uma tool "faz-tudo" com `action: str` livre: prefira tools pequenas e específicas
- Engolir erro de tool e seguir como se tivesse funcionado
- Colocar regra de negócio só no prompt, quando ela pode ser validada em código (Pydantic/tool)
- Multiagente antes de um agente único funcionar bem. Comece simples

## Referências

- Anthropic, *Building effective agents* (simplicidade, transparência, design de tools): https://www.anthropic.com/engineering/building-effective-agents
- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* (2022): https://arxiv.org/abs/2210.03629
- Featherless, Tool Calling: https://featherless.ai/docs/tool-calling
