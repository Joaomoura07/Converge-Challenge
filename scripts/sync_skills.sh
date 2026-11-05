#!/usr/bin/env bash
# Gera as "pontes" de skills a partir de skills/*.md (fonte única da verdade):
#   .claude/skills/<name>/SKILL.md  -> Claude Code
#   .agents/skills/<name>/SKILL.md  -> OpenAI Codex / ChatGPT / agentes do padrão agentskills.io
# Rode após criar/renomear uma skill:  bash scripts/sync_skills.sh
set -euo pipefail
cd "$(dirname "$0")/.."
for src in skills/[0-9]*.md; do
  name=$(sed -n 's/^name: *//p' "$src" | head -1)
  desc=$(sed -n 's/^description: *//p' "$src" | head -1)
  for root in .claude/skills .agents/skills; do
    mkdir -p "$root/$name"
    cat > "$root/$name/SKILL.md" <<MD
---
name: $name
description: $desc
---

<!-- Gerado por scripts/sync_skills.sh. Edite $src, não este arquivo. -->

Leia e siga integralmente \`$src\` (na raiz do repositório) antes de agir.
Ele é a fonte única desta skill; este arquivo existe só para a ferramenta descobri-la.
MD
  done
  echo "ok  $name  <-  $src"
done
