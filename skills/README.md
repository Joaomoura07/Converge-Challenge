# Skills do time

Três skills no padrão aberto [Agent Skills](https://agentskills.io) (frontmatter `name` + `description`). O mesmo arquivo funciona no Claude e nos produtos da OpenAI.

| # | Skill | Para quê |
|---|---|---|
| 01 | [`building-react-agents`](01-react-agent-pattern.md) | Loop ReAct, tools Pydantic, autocorreção (3 falhas), human-in-the-loop |
| 02 | [`integrating-featherless`](02-featherless-integration.md) | Cliente, modelos por tarefa, concorrência, erros, modelo reserva, custo |
| 03 | [`tracing-with-langfuse`](03-langfuse-tracing.md) | SDK v5, árvore de spans, custo, evals, roteiro do Demo Day |
| 04 | [`designing-orcamentista-ui`](04-ui-design.md) | Linguagem de prancha técnica, papéis de cor (valores definidos pelo time), telas, "cota de preço", carregamento tracejado, textos, acessibilidade, modo demo |

**Fonte única:** edite só os arquivos desta pasta. As "pontes" em `.claude/skills/` e `.agents/skills/` são geradas por `bash scripts/sync_skills.sh`.

## Como usar em cada ferramenta

### Claude Code (terminal, VS Code, desktop)
Automático: o Claude Code descobre `.claude/skills/*/SKILL.md` e lê o `CLAUDE.md`. Ele aciona a skill sozinho pela descrição, ou você pede: *"use a skill building-react-agents para criar uma tool de agendamento"*.

### OpenAI Codex (CLI / IDE / app)
Automático: o Codex procura `.agents/skills/*/SKILL.md` da pasta atual até a raiz do repo e lê o `AGENTS.md`. Para invocar: digite `$` e escolha a skill, ou mencione o nome no pedido.

### Cursor / Windsurf / Copilot
Leem o `AGENTS.md`, que lista as skills e quando usá-las. Se a ferramenta não abrir o arquivo sozinha, anexe com `@skills/01-react-agent-pattern.md`.

### ChatGPT ou Claude no navegador (sem acesso ao repo)
1. Crie um **Projeto** (ChatGPT *Projects* / Claude *Projects*) chamado "Converge".
2. Envie os 3 arquivos `skills/0*.md` + `AGENTS.md` como arquivos do projeto.
3. Nas instruções do projeto, cole: *"Siga as skills anexadas. Antes de responder sobre agente/tools, Featherless ou Langfuse, consulte o arquivo correspondente e respeite as regras do AGENTS.md."*

## Criando uma skill nova
1. Crie `skills/04-<tema>.md` com frontmatter:
   - `name`: minúsculas, números e hífens, no máximo 64 caracteres, de preferência no gerúndio (`handling-documents`)
   - `description`: em terceira pessoa, no máximo 1024 caracteres, dizendo **o que faz** e **quando usar** (com as palavras que o time vai digitar)
2. Corpo com menos de 500 linhas: regras imperativas, exemplos de código do próprio repo e anti-padrões.
3. Rode `bash scripts/sync_skills.sh` e faça commit.
