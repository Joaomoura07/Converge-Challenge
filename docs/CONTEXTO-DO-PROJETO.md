# Orçamentista Autônomo — contexto do projeto

> Resumo para o time do **Converge Challenge powered by Tako**. Atualizado em 06/11/2026, à noite.

---

## 1. O evento

| | |
|---|---|
| **O quê** | Hackathon presencial de AI Agents, com Demo Day e premiação |
| **Quando** | Sábado 7/11 e domingo 8/11/2026. **Presença obrigatória nos dois dias** |
| **Onde** | **Porto Digital** — Av. Cais do Apolo, 222, 8º andar, Bairro do Recife |
| **Canal oficial** | Grupo de WhatsApp do evento (todo aviso sai por lá) |

### Horários que importam
| Dia | Hora | O quê |
|---|---|---|
| Sáb | 08h30 | Credenciamento e café |
| Sáb | 09h30 | Abertura e regras (prestar atenção em qualquer mudança) |
| Sáb | **10h00** | **Começa a construção.** Código do produto só a partir daqui |
| Sáb | 17h00 | Fim do dia 1 |
| Dom | **13h00** | **Prazo final de submissão** (meta: submeter até 12h30) |
| Dom | 16h00 | Demo Day: **3 minutos por time**, cronometrado |
| Dom | 17h30 | Premiação |

### Como a banca avalia (4 critérios, peso igual)
1. **Protótipo e aderência:** funciona na demo, faz trabalho real, e **os jurados vão testar o link**
2. **Viabilidade como startup:** mercado, quem paga, como cresce
3. **Pitch:** clareza do problema, da solução e do mercado
4. **Criatividade e originalidade**

Metade da nota é negócio. A Canastra (fundo de investimento) e a Tako estão na banca.

### O que a submissão exige
- Descrição: problema, para quem, solução e **como o agente funciona**
- Vídeo de demonstração
- **Link navegável e testável**
- Material de apresentação
- Lista de ferramentas, modelos e APIs usados

### Prêmio AWS (atenção)
Para resgatar os créditos é preciso ter **site em domínio próprio**, **e-mail no mesmo domínio** (Gmail não vale) e conta AWS. Dá para resolver no sábado à noite: registrar um `.com.br`, subir uma landing simples e criar o e-mail.

---

## 2. O produto: Orçamentista Autônomo

### O problema
Arquitetos perdem horas montando orçamento e estudo de viabilidade na mão. Eles pegam a lista de materiais do projeto (exportada do Revit ou do SketchUp), pesquisam preço loja por loja e calculam frete. É trabalho repetitivo, lento e cheio de erro.

### A solução
Um sistema em que o arquiteto **sobe a lista de materiais e recebe um estudo de viabilidade pronto**, com preços médios, imagens dos produtos e a melhor estratégia de compra para o CEP da obra.

### Fluxo do usuário
```
1. Sobe o arquivo (CSV / Excel / PDF exportado do Revit, SketchUp etc.)
2. O site mostra os itens numa TABELA EDITÁVEL: o arquiteto confere e corrige
3. Clica em "Enviar para a IA"
4. Os itens vão aparecendo na tela AO VIVO, um a um, com preço e imagem
5. Recebe: itens definidos × "Pendente de Especificação" + decisão de frete
```

### O que o sistema entrega
- **Preço médio, mínimo e máximo** de cada item, pesquisado na internet em tempo real
- **Imagem** do produto
- **Separação** entre itens bem definidos (ex.: "Suvinil Toque de Seda Branco Neve 18L") e itens **Pendentes de Especificação** (ex.: "tinta branca", sem marca nem modelo)
- **Decisão de logística:** pelo CEP da obra, se compensa comprar tudo numa loja só ou dividir entre lojas pagando mais de um frete
- Material para o arquiteto **negociar desconto** com as lojas físicas

---

## 3. Arquitetura

```
 [Site na Vercel]
   upload → tabela editável → "Enviar para a IA"
        │
        ▼  POST /orcamentos
 [Backend FastAPI na Vercel]
   Agente de IA (loop ReAct)
     ├─ LLM: Featherless (GLM-5.2)       → entende e normaliza cada item
     ├─ Busca: Tavily (principal)        → preço + imagem
     │         DuckDuckGo (reserva)      → se o Tavily falhar ou acabar
     ├─ Cache de preços (Supabase)       → item já pesquisado sai na hora
     └─ Logística (Python determinístico) → CEP da obra × lojas → loja única ou dividir
        │
        ▼  grava item por item
 [Supabase]  ── Realtime ──▶  o site atualiza sozinho
 [Langfuse]  ← trace de cada execução (o que o agente fez, custo, tempo)
```

### Decisões já tomadas
| Tema | Decisão |
|---|---|
| Hospedagem | **Tudo na Vercel:** backend (já no ar) + site. Nada depende do notebook |
| n8n | **Fora.** O site fala direto com o FastAPI |
| Busca | Tavily + DuckDuckGo de reserva + cache |
| Lojas e frete | **Híbrido:** o preço vem da busca; lojas de Recife pré-cadastradas no Supabase (CEP, frete base, R$/km, pedido mínimo) garantem o cálculo de frete mesmo se a busca falhar |
| Proteção da URL | Nenhuma por enquanto (é demo) |
| Demo | **≈30 s:** arquivo com 15–20 itens, metade já em cache, buscas em paralelo, itens aparecendo um a um |

### Stack
| Peça | Ferramenta | Status |
|---|---|---|
| LLM | Featherless (`zai-org/GLM-5.2`; reserva `Qwen/Qwen3-32B`) | ✅ testado, faz tool calling |
| Busca | Tavily | ✅ chave testada (traz preço e imagem) |
| Busca reserva | DuckDuckGo (biblioteca `ddgs`, sem chave) | entra no sábado |
| CEP | ViaCEP / BrasilAPI (grátis, sem chave) | entra no sábado |
| Banco + tempo real | Supabase | ✅ conectado |
| Rastro / auditoria | Langfuse (região **US**) | ✅ conectado |
| Backend | FastAPI (Python) | ✅ no ar na Vercel |
| Site | Vercel (framework a definir com o Samuel) | conta criada, site vazio |

**Backend no ar:** https://converge-challenge.vercel.app
- `/health` → mostra o que está conectado (LLM, Supabase e Langfuse: tudo `true`)
- `/docs` → Swagger para testar a API

---

## 4. Contrato de dados (proposta: validar Enzo + Samuel)

### Entrada: `POST /orcamentos`
O site manda os itens **já revisados pelo arquiteto**:
```json
{
  "obra": { "nome": "Reforma Apto Boa Viagem", "cep": "51020-000" },
  "origem": { "arquivo": "lista.xlsx", "formato": "xlsx", "software": "revit" },
  "itens": [
    { "linha": 5, "categoria": "Pintura", "descricao": "Tinta acrílica Suvinil Toque de Seda Branco Neve",
      "quantidade": 180, "unidade": "m2", "nivel": "Térreo", "extras": {} }
  ]
}
```
Resposta imediata: `{ "orcamento_id": "..." }`. O processamento segue em segundo plano.

**Regras do formato:**
- `quantidade` é sempre número com ponto decimal (`12.5`), nunca texto.
- Unidades escritas sempre do mesmo jeito: `m`, `m2`, `m3`, `un`, `kg`, `l`, `cm`, `mm`.
- Colunas desconhecidas vão para `extras`, para nada se perder.
- O modelo em Python já existe: `tests/importacao/contrato.py`.

### Tabelas no Supabase
| Tabela | Para quê | Campos principais |
|---|---|---|
| `orcamentos` | Um por upload | id, status (`processando`/`concluido`/`erro`), cep, totais, decisão de logística |
| `orcamento_itens` | Um por item (o site **escuta essa tabela via Realtime**) | orcamento_id, descrição original, produto normalizado, marca, **status** (`definido`/`pendente_especificacao`/`erro`), motivo da pendência, quantidade, unidade, embalagem, qtd. de embalagens, preço médio/mín/máx, fontes (loja + link + preço), imagem, loja sugerida |
| `fornecedores` | Lojas de Recife pré-cadastradas | nome, site, CEP, coordenadas, frete base, frete por km, pedido mínimo |
| `cache_precos` | Não pesquisar o mesmo produto duas vezes | chave do produto, resultado, validade |

### Saída de logística
```json
{ "estrategia": "loja_unica | dividir", "lojas": ["..."], "frete_total": 180.0, "economia_estimada": 95.0 }
```

### Perguntas em aberto para o Samuel
1. Qual framework no site? (Next.js é o padrão da Vercel)
2. Quem faz a leitura do arquivo no navegador (PapaParse para CSV, SheetJS para Excel)?
3. Falta algum campo no contrato para a tela?
4. Qual arquivo de teste vira o arquivo da demo? (sugestão: obra 03 Cozinha ou 11 Studio, curtos e com marcas)

---

## 5. O que já está pronto

### Repositório (GitHub, privado)
```
src/            → backend FastAPI + agente (agent.py, tools.py, database.py, config.py, main.py)
prompts/        → prompt do agente
skills/         → guias para Claude Code / Codex / ChatGPT (ReAct, Featherless, Langfuse)
tests/importacao/ → 100 casos de teste de importação + contrato.py
docs/briefing/  → 3 PDFs: oportunidades, dossiê técnico, plano de ação
docs/arquivos-teste/ → 183 arquivos de teste realistas (ver abaixo)
scripts/check_setup.py → testa todas as conexões num comando
```

### Arquivos de teste: `docs/arquivos-teste/` (183 arquivos)
Acervo para jogar no sistema **no final** e conferir se o resultado faz sentido. Foi criado **antes** do produto de propósito, para os testes não serem feitos sob medida para dar certo.
- **12 obras fictícias** em Recife e região (apartamento, casa, cozinha, banheiro, loja, escritório, clínica, restaurante, piscina, fachada, studio, casa de praia), com **endereços e CEPs reais**
- **15 formatos**:
  - Revit `.txt`, orçamento `.xlsx`, lista `.csv`, lista de WhatsApp `.txt`
  - SketchUp `.csv`/`.html`, memorial `.docx`, pedido de cotação e prancha em `.pdf`
  - foto de lista escrita à mão `.jpg`/`.png`
  - `.xls`, `.ods`, `.json`, `.xml`, `.tsv`, `.md`
- **Cerca de 116 produtos de marcas reais** (Suvinil, Coral, Portobello, Deca, Docol, Tigre, Quartzolit, Knauf, Blum, Gerdau…) escritos de 3 jeitos: completo, abreviado e **genérico** (que deve virar *Pendente de Especificação*)
- **Arquivos com problema de propósito:** corrompido, vazio, colunas trocadas, PDF escaneado, duplicados, acentos quebrados, fórmulas com `#REF!` etc.
- O índice completo está em `docs/arquivos-teste/LEIAME.md`

### Armadilhas já descobertas (vale ler antes de codar)
- **A detecção automática de separador do PapaParse erra nos `.txt` do Revit em português.** O `12,50 m²` faz ele achar que o separador é vírgula. Em `.txt`, forçar tab.
- **CSV salvo pelo Excel em português** vem em Windows-1252: os acentos quebram se for lido como UTF-8.
- **O GLM-5.2 "pensa" antes de responder.** Com limite de tokens baixo, a resposta vem vazia.
- **Variáveis na Vercel nunca levam aspas.**
- **O pacote `xlsx` do npm está desatualizado e tem falhas de segurança.** Instalar o SheetJS pelo CDN oficial.

---

## 6. Contas e chaves

| Serviço | Status |
|---|---|
| Featherless | ✅ (cada um tem a própria chave, US$ 25 de crédito) |
| Supabase | ✅ |
| Langfuse | ✅ (região US) |
| Tavily | ✅ 1 chave. **Cada integrante deve criar a sua** em app.tavily.com (grátis, 1.000 buscas/mês por conta) |
| Vercel | ✅ todas as chaves configuradas |

- O arquivo `.env` com as chaves é enviado **no privado**. **Nunca** vai para o GitHub nem para o grupo do evento.
- Várias chaves do Tavily vão juntas, separadas por vírgula: `TAVILY_API_KEYS=tvly-aaa,tvly-bbb`.
- Lembrete: **cancelar o plano da Featherless** antes da primeira cobrança, se não for continuar usando.

---

## 7. Plano para o fim de semana

### Sábado
| Hora | O quê | Marco |
|---|---|---|
| 10h | Primeiro commit; dividir quem mexe em quais arquivos | |
| 10h–12h | Leitura dos arquivos + tabela editável no site · ligar Tavily/DuckDuckGo · tabelas no Supabase | |
| 12h–14h | Agente buscando preço de ponta a ponta + Realtime atualizando a tela | **14h: caminho feliz rodando** |
| 14h–16h | "Pendente de Especificação" + logística por CEP | |
| 16h–17h | Mentoria com perguntas concretas | **17h: demo gravável** |
| Noite | Deploy final · domínio + landing + e-mail (AWS) · slides · rodar os arquivos de teste | **link público estável** |

**Regra de corte:** se às 14h o caminho feliz não estiver rodando, corta escopo, não sono.

### Domingo
| Hora | O quê |
|---|---|
| até 10h30 | Corrigir só o que quebra a demo |
| 10h30 | **Congela as funcionalidades** |
| 10h30–11h30 | Gravar o vídeo (também é o plano B se a demo ao vivo falhar) |
| até 12h30 | **Submeter** (o prazo é 13h) |
| 13h–16h | Ensaiar o pitch pelo menos 5 vezes, com cronômetro |

### Roteiro do pitch (3 min)
| Tempo | Conteúdo |
|---|---|
| 0:00–0:25 | A dor com número (horas perdidas por orçamento) |
| 0:25–0:45 | A solução em uma frase |
| 0:45–2:00 | **Demo ao vivo** (≈30 s rodando). Enquanto roda: "testamos com 183 arquivos reais de 15 formatos…" |
| 2:00–2:35 | Negócio: quem paga, preço, mercado, por que agora |
| 2:35–3:00 | Ganho × custo por orçamento, e próximo passo |

---

## 8. Regras de ouro
- **Código do produto só a partir de sábado, 10h.** Commits pequenos e frequentes durante o evento.
- Nada de chaves no GitHub.
- Usar só dados fictícios.
- Se der dúvida sobre alguma regra, perguntar no grupo oficial do WhatsApp.
