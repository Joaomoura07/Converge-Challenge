# Converge Challenge — AI Agents

> Hackathon **Converge Challenge powered by Tako** · Porto Digital, Recife · 7–8/11/2026

Base de infraestrutura para um agente autônomo (ou sistema multiagente) em Python. A lógica do produto entra a partir das **10h de sábado, 7/11**, como pede o regulamento.

## Arquitetura

```
 Cliente / Front ──HTTP──▶ FastAPI (src/main.py)
                               │
                               ▼
                      Agent loop (src/agent.py) ◀── prompts/*.md
                      planeja → chama tool → observa → itera
                       │                 │
          OpenAI SDK ──┘                 └──▶ ToolRegistry (src/tools.py)
               │                                   │
               ▼                                   ▼
   Featherless API (LLM gateway)        APIs / mocks (ATS, HRIS, e-mail…)
   zai-org/GLM-5.2

   Langfuse ◀── trace de cada execução (LLM + tools, tokens, custo, latência)
   Supabase ◀── src/database.py: trilha de auditoria (agent_runs) + dados do app
```

| Pasta / arquivo | Responsabilidade |
|---|---|
| `prompts/` | Prompts versionados em Markdown, com placeholders `{{CHAVE}}` |
| `src/config.py` | Settings tipados lidos do `.env` + `load_prompt()` |
| `src/agent.py` | Loop de tool calling, limite de passos, tracing, métricas de uso |
| `src/tools.py` | Registro de ferramentas com schema gerado via Pydantic; erros viram dados para o agente |
| `src/database.py` | Cliente Supabase e persistência das execuções |
| `src/main.py` | Rotas HTTP (`/health`, `/agent/run`) |
| `sql/` | Migrations SQL (rodar no SQL Editor do Supabase) |
| `scripts/check_setup.py` | Testa Featherless (chat + tool calling), Langfuse e Supabase |
| `skills/` | Skills do time para Claude Code, Codex e ChatGPT ([como usar](skills/README.md)) |
| `AGENTS.md` / `CLAUDE.md` | Regras do repo para assistentes de código |

### Comportamento do agente

O loop ReAct usa tool calling nativo e termina com um destes `status`: `completed`, `escalated` (chamou `escalate_to_human` ou teve 3 falhas de tool seguidas), `max_steps_reached` ou `error`. Em 400/503, ele tenta o `FEATHERLESS_MODEL_FALLBACK`. Cada resposta traz `cost_usd`, tokens, latência e `trace_url` do Langfuse.

## Setup rápido

Requer Python 3.11+.

```bash
git clone https://github.com/enzoemanuelgl/Converge-Challenge.git
cd Converge-Challenge
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # preencha suas chaves
python -m scripts.check_setup    # valida Featherless, tool calling, Langfuse e Supabase
uvicorn src.main:app --reload
```

- API: http://localhost:8000 · Docs interativas: http://localhost:8000/docs
- Banco: rode `sql/001_agent_runs.sql` no SQL Editor do Supabase.
- Docker (opcional): `docker compose up --build`

Teste rápido:

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Que horas são em Recife?"}'
```

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `FEATHERLESS_API_KEY` | Chave da Featherless (cada integrante usa a sua) |
| `FEATHERLESS_BASE_URL` | `https://api.featherless.ai/v1` |
| `FEATHERLESS_MODEL` | Modelo principal (padrão `zai-org/GLM-5.2`) |
| `FEATHERLESS_MODEL_FAST` | Modelo barato para texto simples (padrão `google/gemma-4-31B-it`) |
| `FEATHERLESS_MODEL_FALLBACK` | Reserva em 400/503, com tool calling nativo (padrão `Qwen/Qwen3-32B`) |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | `service_role` key (somente backend) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Chaves do projeto Langfuse |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` ou `https://us.cloud.langfuse.com` |
| `AGENT_MAX_STEPS`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT_SECONDS`, `LLM_TEMPERATURE` | Ajustes do loop |

Lista completa em [`.env.example`](.env.example). **Nunca** faça commit do `.env`.

## Adicionando uma ferramenta

Detalhes em [`skills/01-react-agent-pattern.md`](skills/01-react-agent-pattern.md).

```python
from pydantic import Field
from src.tools import ToolArgs, registry

class BuscarCandidatoArgs(ToolArgs):
    candidato_id: str = Field(description="ID do candidato no ATS")

@registry.tool(description="Busca os dados de um candidato no ATS.")
def buscar_candidato(args: BuscarCandidatoArgs) -> dict:
    ...
```

## Ferramentas, modelos e APIs utilizados

Featherless (`zai-org/GLM-5.2`), Langfuse, Supabase, FastAPI, OpenAI Python SDK. Atualizar antes da submissão.

## Time

<!-- nomes + GitHub -->
