# AGENTS.md: instruções para assistentes de código

Lido automaticamente pelo OpenAI Codex, Cursor e outros agentes. O Claude Code lê via `CLAUDE.md`.

## Projeto
Hackathon Converge Challenge (7–8/11/2026): API FastAPI com um agente autônomo (ReAct + tool calling) sobre a Featherless, com tracing no Langfuse e persistência no Supabase. Veja `README.md`.

## Skills: consulte ANTES de mexer na área correspondente
| Skill | Arquivo | Quando |
|---|---|---|
| `building-react-agents` | `skills/01-react-agent-pattern.md` | Agente, loop, tools, prompt, escalonamento humano |
| `integrating-featherless` | `skills/02-featherless-integration.md` | Chamadas ao LLM, modelos, erros, custo |
| `tracing-with-langfuse` | `skills/03-langfuse-tracing.md` | Tracing, métricas, evals, Demo Day |

## Regras do repositório
- Estrutura: `prompts/` (prompts .md), `src/agent.py` (loop), `src/tools.py` (tools), `src/database.py` (Supabase), `src/main.py` (rotas), `src/config.py` (settings).
- Config só via `src/config.py` + `.env`. Nunca faça commit de chaves nem do `.env`.
- Toda tool nova: args herdam `ToolArgs`, registrada com `@registry.tool`, retorno enxuto.
- Decisões sobre pessoas (contratar, demitir, salário, avaliação) nunca são tomadas pelo agente: use `escalate_to_human`.
- Use somente dados sintéticos. Integrações externas (ATS/HRIS/folha) podem ser mocks, desde que o agente realmente as opere.
- Antes de concluir uma mudança: `python -m scripts.check_setup` (ambiente) e rode o caminho feliz + uma exceção.
- Commits pequenos e frequentes: os organizadores podem pedir o histórico como evidência.
- Ao criar ou renomear uma skill em `skills/`, rode `bash scripts/sync_skills.sh`.
