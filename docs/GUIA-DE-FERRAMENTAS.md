# Guia de ferramentas do Orçamentista Autônomo

Para explicar qualquer peça do projeto a jurados, mentores e ao time. Cada seção diz **o que é**, **o que faz aqui**, **onde está no código**, **perguntas prováveis** e **limites** (o que não fazemos ou não sabemos). Foi escrito a partir do código e dos docs do repositório em 07/11/2026.

> Convenção: ✅ = confirmado no código do repositório. ⚠️ = decisão ou plano que não está neste repositório (depende de outra fatia ou de outra branch).

---

## 0. O produto em 6 frases

1. O arquiteto sobe a lista de materiais (CSV, Excel, TXT do Revit, PDF) e confere numa tabela editável.
2. Clica em "Enviar para a IA".
3. Para cada item, o sistema pesquisa preço em lojas brasileiras, confere se é o mesmo produto, calcula quantas embalagens comprar (com perda) e grava o resultado.
4. Itens genéricos (ex.: "tinta branca") viram uma **pergunta** ao arquiteto em vez de um chute.
5. No fim, o sistema calcula frete por CEP (loja única ou dividir), se cabe no orçamento do cliente e quanto tempo e dinheiro economizou.
6. Todo preço tem fonte (link da loja). **Nunca existe preço sem fonte.**

### Mapa: quem faz o quê

```
Navegador (site, Vercel)
   │ upload → tabela editável → "Enviar para a IA"
   ▼
FastAPI (Python)  ── POST /orcamentos ──▶ pesquisar_orcamento(id)
   │
   ├─ Cache de preços (Supabase, tabela cache_precos, 7 dias)
   ├─ Busca: Tavily (principal) → DuckDuckGo (reserva)
   ├─ Extração + conferência: LLM rápido (Qwen3-32B) via Featherless
   ├─ Agente ReAct que refaz a busca: GLM-5.2 via Featherless (até 2 buscas extras)
   ├─ Cálculo (Python puro): mediana, outliers, embalagens, confiança
   └─ Grava item a item em orcamento_itens (Supabase)
            │ Realtime
            ▼
        o site atualiza sozinho
Langfuse: registra cada passo (LLM, busca, cálculo), tokens, custo, tempo
Fatia C (João): frete por CEP, viabilidade, ganho, exportar ⚠️ (branch dele)
```

---

## 1. Backend e linguagem

### 1.1 Python 3.11+ (Docker usa 3.12) ✅
- **O que é:** a linguagem do backend inteiro.
- **Por que:** as bibliotecas de IA, busca e dados que usamos têm SDK em Python, e o time já dominava.
- **P: Por que não Node/TypeScript no backend?** O agente, a pesquisa e os cálculos estão escritos em Python; o front (React/TypeScript) é separado e conversa por HTTP e Realtime.

### 1.2 FastAPI + Uvicorn ✅ (`src/main.py`)
- **O que é:** FastAPI é um framework para criar APIs HTTP em Python. Uvicorn é o servidor que o executa.
- **O que faz aqui:** expõe as rotas:
  - `GET /health`: mostra se LLM, Supabase e Langfuse estão configurados.
  - `POST /agent/run`: roda o agente genérico (base do template).
  - `POST /orcamento-itens/{id}/repesquisar`: botões "Pesquisar de novo" e "Responder" (pergunta do arquiteto).
  - `POST /orcamentos` e `POST /orcamentos/{id}/resultado`: ficam nas fatias A e C ⚠️.
  - `/docs`: página Swagger gerada automaticamente, útil para os jurados testarem.
- **P: Por que FastAPI?** Gera validação e documentação a partir dos modelos Pydantic, e suporta `async`, que usamos para pesquisar vários itens ao mesmo tempo.
- **P: Os jurados conseguem testar?** O backend está em https://orca-api-x7k2.vercel.app (docs do projeto). ⚠️ O site final depende da Fatia A.
- **Limite:** o CORS está aberto para qualquer origem (`allow_origins=["*"]`) e não há autenticação. Decisão consciente para a demo; para produção seria preciso restringir.

### 1.3 Pydantic e pydantic-settings ✅
- **O que é:** biblioteca que valida dados com tipos. `pydantic-settings` lê o `.env` e transforma em configuração tipada.
- **O que faz aqui:**
  - `src/modelos.py`: define o contrato do item (`ItemEntrada`, `Fonte`, `ResultadoItem`). O `ResultadoItem` **recusa** um item definido sem preço, um preço sem fonte, faixa com mín > máx e pendente sem pergunta. Essa é a regra "nunca preço sem fonte" aplicada no código.
  - `src/tools.py`: o schema JSON das ferramentas do agente é gerado dos modelos Pydantic, com `extra="forbid"` (rejeita campo inventado pelo LLM).
  - `src/config.py`: todas as chaves e limites vêm do `.env`.
- **P: Como vocês garantem que a IA não inventa preço?** Três travas: (1) o preço extraído pelo LLM só vale se aparecer escrito no texto do anúncio (`src/precos.py`); (2) o modelo `ResultadoItem` rejeita preço sem fonte; (3) a conta final é Python, não LLM.

### 1.4 httpx, requests, python-dotenv, tzdata ✅
- **httpx:** cliente HTTP assíncrono. Usado, por exemplo, para checar se a URL da imagem do produto realmente carrega (`src/busca.py`, timeout de 4 s).
- **requests:** cliente HTTP síncrono, listado nas dependências.
- **python-dotenv:** carrega variáveis do `.env`.
- **tzdata:** fusos horários no Windows (o agente tem uma ferramenta de hora em Recife).

### 1.5 Docker e docker-compose ✅
- **O que é:** empacota a API com suas dependências para rodar igual em qualquer máquina.
- **Aqui:** `docker compose up --build` sobe a API. Supabase e Langfuse ficam na nuvem de propósito (rede do evento é compartilhada). Perfis opcionais: `n8n` e `local-db` (Postgres local).
- **P: A produção usa Docker?** Não: o backend roda na Vercel (decisão do projeto). O Docker é para desenvolvimento e plano B.

### 1.6 Vercel ✅/⚠️
- **O que é:** plataforma de hospedagem.
- **Aqui:** hospeda o backend FastAPI e o site. Limites que moldaram o código:
  - A função serverless encerra quando a resposta é enviada. Por isso a pesquisa roda **dentro da mesma requisição** do `POST /orcamentos`.
  - Tempo máximo da função precisa ser ≥ 60 s (verificar na configuração).
  - Upload máximo de 4,5 MB (razão de o IFC ser lido no navegador, seção 9).
  - Variáveis de ambiente **sem aspas**.
- **Limite:** não há `vercel.json` neste repositório; a configuração de deploy está na conta da Vercel.

---

## 2. LLM: Featherless + modelos

### 2.1 Featherless AI ✅ (`src/agent.py`, `src/precos.py`)
- **O que é:** serviço que dá acesso a vários modelos abertos por uma API compatível com a da OpenAI.
- **Aqui:** é o único provedor de LLM. Usamos o SDK `openai` apontando para `https://api.featherless.ai/v1`.
- **P: Por que Featherless e não OpenAI/Claude?** É o gateway do hackathon (cada integrante tem crédito) e permite trocar de modelo mudando só o nome no `.env`.
- **P: Quanto custa por orçamento?** O sistema mede: cada chamada devolve `usage.cost`, somamos em `src/custo.py` e gravamos em `orcamentos.custo_usd` ⚠️ (coluna depende do Samuel). A tela mostra "Custo de IA".
- **Limites:** concorrência é limitada (medimos 6 chamadas simultâneas ao Qwen3-32B gerando 3 respostas vazias), por isso há "porteiros" de 3 chamadas simultâneas; erros 400/503 acionam um modelo reserva.

### 2.2 Os três modelos, cada um com uma função ✅ (`src/config.py`)
| Modelo | Papel | Por quê |
|---|---|---|
| `zai-org/GLM-5.2` | Agente que **refaz a busca** quando não achou lojas suficientes | Faz tool calling nativo (testado). Mais lento porque "pensa" antes de responder |
| `Qwen/Qwen3-32B` | **Extrai preço** dos anúncios e confere se é o mesmo produto | Rápido (≈5 s) e acertou 5/5 na avaliação da etapa 3 |
| `google/gemma-4-31B-it` | Reserva da extração | 5/5 na mesma avaliação; entra se o Qwen falhar |

- **P: Por que três modelos?** Cada tarefa tem custo e tempo diferentes. Extrair preço de 5 anúncios é simples e acontece em todos os itens, então usa o modelo rápido. O agente que raciocina sobre a consulta só roda nos itens difíceis.
- **P: O que é "tool calling"?** O modelo devolve, em formato estruturado, qual função quer chamar e com quais argumentos. Nosso código executa a função e devolve o resultado ao modelo.
- **P: O GLM "pensar" causa problema?** Sim: com limite de tokens baixo a resposta vem vazia. Por isso não limitamos tokens e há nova tentativa quando a resposta vem vazia.

---

## 3. O agente (ReAct)

### 3.1 ReAct + tool calling ✅ (`src/agent.py`, `src/pesquisa.py`)
- **O que é:** padrão em que o modelo alterna **Raciocínio** (decide o que fazer), **Ação** (chama uma ferramenta), **Observação** (lê o resultado) e repete até responder.
- **Aqui há dois agentes:**
  1. **Genérico** (`src/agent.py`): loop completo com limite de passos (`AGENT_MAX_STEPS=8`), escalonamento humano e persistência em `agent_runs`.
  2. **Pesquisador de preço** (`src/pesquisa.py`, prompt `prompts/pesquisador_precos.md`): ReAct enxuto com **uma ferramenta**, `buscar_preco(consulta)`. Só roda quando a primeira busca achou menos de 2 lojas com o mesmo produto.
- **Como o pesquisador decide parar:** é o **código** que decide, não o LLM. Para quando há lojas suficientes ou acabaram as 2 buscas extras. Medimos ≈10 s a menos por item difícil.
- **Limites do pesquisador:** 2 buscas extras por item, 40 s por item, 1 chamada ao GLM por vez, 2 itens com agente ao mesmo tempo, prazo total de 60 s para a fase do agente. Item que não coube fica com o resultado da fase rápida.
- **P: Isso é mesmo um agente autônomo?** Sim: decide sozinho quando refazer a busca, como reescrever a consulta e quando parar. Regras de negócio (nunca inventar preço, perguntar em vez de chutar) são aplicadas pelo código ao redor.
- **P: E se o agente errar?** Falha de ferramenta vira dado para o modelo corrigir; 3 falhas seguidas escalam para humano (`escalate_to_human`). No pesquisador, qualquer erro faz o item seguir com o resultado da primeira busca.
- **P: O agente decide sobre pessoas?** Não. Regra do repositório: decisões sobre pessoas vão sempre para `escalate_to_human`. (O produto atual é de orçamento de obra.)

### 3.2 Registro de ferramentas (`src/tools.py`) ✅
- Toda ferramenta é uma função Python com um modelo Pydantic de argumentos, registrada com `@registry.tool`. O schema enviado ao LLM sai do modelo. Erros de validação voltam ao LLM como observação.

### 3.3 Prompts em Markdown ✅ (`prompts/`)
- `system_prompt.md` (agente genérico), `extrator_precos.md` (extração), `pesquisador_precos.md` (reformular busca). Versionados no Git, com placeholders `{{CHAVE}}` preenchidos por `load_prompt()`.
- **P: Por que fora do código?** Dá para revisar e versionar o prompt sem mexer em Python.

---

## 4. Pesquisa de preço (Fatia B)

Fluxo por item, em **duas fases**:
- **Fase 1 (rápida, todos os itens em paralelo, sem agente):** cache → busca → extração → cálculo → grava. Cada item é gravado assim que fica pronto.
- **Fase 2 (só quem precisa):** agente refaz a busca, recalcula e regrava.

### 4.1 Tavily ✅ (`src/busca.py`)
- **O que é:** API de busca na web feita para uso por LLMs; devolve resultados com texto e imagens.
- **Aqui:** busca principal. Configuração: `search_depth="basic"`, `include_images=True`, e `include_domains` restrito a uma **lista fixa de 18 lojas** (Leroy Merlin, C&C, Telhanorte, Obramax, Ferreira Costa, MadeiraMadeira, Amazon, Mercado Livre, Magazine Luiza, Casas Bahia, Americanas, Dicico, Loja Suvinil, Loja Dexco, Tramontina, Sertão, Padovani, Tumelero).
- **Por que lista fixa:** evita blog, fórum e preço em dólar.
- **Detalhe técnico:** não usamos `country="brazil"` junto com `include_domains`, porque o Tavily devolve 0 resultados nessa combinação (medido).
- **Várias chaves:** `TAVILY_API_KEYS` aceita várias separadas por vírgula, em rodízio, porque cada conta grátis tem cota mensal (docs do projeto: 1.000 buscas/mês por conta).
- **P: De onde vêm os preços?** Dos anúncios nas lojas da lista fixa, via Tavily. Não temos acordo com as lojas nem acesso a APIs delas.
- **P: Os preços são em tempo real?** São do momento da busca, com cache de 7 dias para itens repetidos. Preço vencido só é usado como reserva, com a data ("preço de dd/mm").
- **Limite:** preço de anúncio pode estar desatualizado ou mudar no checkout; por isso mostramos faixa (mín–médio–máx), confiança e link para conferir.

### 4.2 DuckDuckGo (`ddgs`) ✅
- **O que é:** biblioteca que usa o DuckDuckGo como busca, sem chave.
- **Aqui:** reserva se o Tavily falhar ou acabar a cota (`region="br-pt"`, até 25 resultados).

### 4.3 Cache de preços (Supabase, `cache_precos`) ✅ (`src/cache.py`, `sql/002`)
- Guarda as **ofertas conferidas** e a imagem escolhida, não a conta final (a conta depende da quantidade de cada orçamento e é refeita na hora).
- **Chave:** descrição normalizada (sem acento, sem palavras vazias, unidades coladas, palavras em ordem alfabética). "Tinta Suvinil Toque de Seda, Branco Neve 18 L" e "tinta suvinil branco neve toque seda 18L" caem na mesma chave.
- **Validade:** 7 dias (`PESQUISA_CACHE_DIAS`). Se a tabela não existe ou a rede falha, conta como "não está no cache" e a pesquisa segue.
- **Demo:** `scripts/aquecer_cache.py` pesquisa todos os itens do arquivo da demo e deixa no cache a fração mais rápida (padrão: metade), para a demo mostrar metade instantânea e metade ao vivo.
- **P: O cache não vai mostrar preço velho?** Vale 7 dias; vencido só entra como reserva e a tela mostra a data.

### 4.4 Extração e conferência (`src/precos.py`) ✅
- O LLM rápido lê os anúncios (até 500 caracteres de trecho cada) e devolve uma linha por anúncio: `índice|preço|embalagem|SIM/PARECIDO/NAO`.
- Regras no prompt: ignorar parcela, frete e desconto só no Pix; kit usa o preço do kit.
- **Trava anti-alucinação:** o preço só é aceito se aparecer escrito no texto do anúncio. Respostas fora do formato são descartadas, não interpretadas.
- **Só entram na média** as ofertas marcadas `SIM` (mesmo produto) com preço.
- Se o modelo principal falhar (erro HTTP, timeout, resposta sem linhas válidas), tenta o reserva.

### 4.5 Cálculo (Python puro, `src/calculo.py`, `src/compra.py`) ✅
- **Sem IA:** conta não se delega a LLM; o mesmo item dá sempre o mesmo resultado.
- Passos:
  1. converte cada oferta para preço por **unidade base** (R$/m², R$/L, R$/kg, R$/un, R$/m) para comparar "R$ 97,90/m²" com "R$ 122,22 a caixa de 1,8 m²";
  2. remove **outliers** fora de 40%–250% da mediana;
  3. calcula **mín / mediana / máx**;
  4. escolhe a embalagem de referência (a de menor custo total para a quantidade pedida);
  5. calcula **quantas embalagens comprar** com **perda por tipo de material** (arredonda para cima);
  6. calcula a **confiança**: `alta` (≥3 lojas e dispersão ≤25%), `media` (≥2 lojas e ≤50%), senão `baixa`.
- **Premissas** (ex.: rendimento de tinta ≈ m²/L com 2 demãos) aparecem na tela com "≈".
- **P: Por que mediana e não média?** A mediana é menos afetada por um anúncio com preço muito fora.
- **P: Como convertem "180 m² de tinta" em latas?** Pelo rendimento por litro (premissa por tipo de produto), com perda, dividido pelo conteúdo da embalagem, arredondando para cima.

### 4.6 Itens genéricos e pergunta ao arquiteto ✅ (`src/pesquisa.py`)
- Item sem marca/linha/medida (ex.: "tinta vermelha") recebe uma **faixa estimada** (`estimativa=true`) e uma **pergunta objetiva** ("Qual marca, linha, cor e acabamento?"), em vez de chute.
- Ao responder, `repesquisar_item` pesquisa de novo ignorando o cache.
- Status do item: `buscando`, `definido`, `pendente_especificacao`, `nao_encontrado`, `erro`.
- **P: Por que não deixar a IA escolher a marca?** Escolher marca muda o preço; é decisão do arquiteto. Regra do projeto: perguntar em vez de chutar, sugerir em vez de aplicar.

### 4.7 Concorrência (`asyncio`) ✅
- Itens são pesquisados em paralelo com limites: 8 buscas simultâneas, 3 chamadas de extração ao LLM, 1 chamada do agente.
- **P: Por que limitar?** Sem limite, o provedor devolvia respostas vazias e o agente esperava vaga até estourar o tempo (medido na etapa 9).

---

## 5. Banco de dados: Supabase

### 5.1 Supabase (Postgres + Realtime) ✅ (`src/database.py`, `sql/`)
- **O que é:** Postgres gerenciado com API, autenticação e **Realtime** (o front recebe mudanças das tabelas por WebSocket).
- **Tabelas:**
  | Tabela | Para quê |
  |---|---|
  | `orcamentos` | Um por upload: status da pesquisa, tempos, logística, viabilidade, ganho, custo ⚠️ |
  | `orcamento_itens` | Um por item. **O site escuta esta tabela via Realtime**: cada `UPDATE` do backend aparece na tela |
  | `cache_precos` | Cache da pesquisa (`sql/002`) ✅ |
  | `fornecedores` | Lojas de Recife (CEP, frete base, R$/km, pedido mínimo) ⚠️ Fatia C |
  | `agent_runs` | Trilha de auditoria do agente genérico (`sql/001`) ✅ |
- **Segurança:** o backend usa a chave `service_role` (ignora RLS), por isso só pode ficar no servidor. O site usa a chave `anon`, com RLS liberando leitura das tabelas que a tela precisa. As tabelas de cache têm RLS ligado sem política para o site.
- **P: Por que Realtime em vez de o site ficar perguntando?** O backend grava cada item assim que fica pronto e a tela atualiza sozinha, item por item, sem polling.
- **P: Como evitam pesquisar duas vezes o mesmo orçamento?** `reservar()` faz um `UPDATE` condicional atômico em `orcamentos` (só passa se o status é `pendente` ou `falhou`, ou se está `pesquisando` há mais de 3 minutos por execução morta). Dois cliques não geram duas pesquisas.
- **Limite:** as tabelas `orcamentos`/`orcamento_itens` pertencem à Fatia A (Samuel, arquivo SQL único). Colunas novas que a B grava (`premissa`, `custo_usd`) precisam estar lá.

---

## 6. Observabilidade: Langfuse

### 6.1 Langfuse (SDK Python v3+, baseado em OpenTelemetry) ✅
- **O que é:** plataforma de observabilidade para aplicações com LLM: registra cada execução como um **trace** (árvore de passos) com entrada, saída, tokens, custo e tempo.
- **Aqui:** decorador `@observe` em cada etapa (busca, extração, agente, cálculo, orçamento); `propagate_attributes` agrupa por `session_id` = id do orçamento. Resultado: **1 árvore por orçamento, 1 galho por item**, com as iterações "errou → refez" visíveis.
- **Custo e tokens:** cada chamada ao LLM registra `usage_details` e `cost_details` (o custo vem do campo `usage.cost` da Featherless).
- **Região:** projeto na região **US**. Configuração via `LANGFUSE_BASE_URL=https://us.cloud.langfuse.com` (nome atual; tem prioridade sobre o antigo `LANGFUSE_HOST`).
- **Resiliência:** sem chaves reais, o tracing desliga sozinho (`LANGFUSE_TRACING_ENABLED=false`) e a API segue funcionando. O interruptor `LANGFUSE_ENABLED=false` faz o mesmo.
- **Demo Day:** abrir o trace de um item em que o agente errou e refez a busca.
- **P: Por que isso importa para o jurado?** Mostra de onde saiu cada preço e que o agente é auditável: dá para ver a consulta usada, o que a loja devolveu e quanto custou.
- **P: O Langfuse armazena dados do cliente?** Os traces incluem textos de itens e resultados de busca; usamos só dados sintéticos.

---

## 7. Front-end

### 7.1 React 19 + TypeScript + Vite ✅ (`ui-fatia-b/`)
- **O que é:** React monta a interface em componentes; TypeScript adiciona tipos; Vite é o servidor de desenvolvimento e o empacotador (`npm run dev` na porta 5174).
- **O que existe no repositório:** os componentes da Fatia B (`ItemRow`, cota de preço `PriceDimension`, `StatusBadge`) com uma **prévia** que simula o Realtime (`ui-fatia-b/src/dados/exemplo-real.json`), para validar a tela antes do banco existir.
- **O site final é da Fatia A (Samuel)** ⚠️: framework definido por ele (o padrão da Vercel é Next.js), leitura de arquivos no navegador (PapaParse para CSV, SheetJS para Excel) e o hook `useOrcamento(id)` com Realtime.
- **Design:** "linguagem de prancha técnica" (skill `designing-orcamentista-ui`): preço mostrado como **cota** (mín–médio–máx), carregamento com cota tracejada e hachura a 45° até o dado chegar, textos em português, modo demo para projetor.
- **P: Os jurados veem o raciocínio?** Cada item mostra fontes (loja + link + preço), confiança e a premissa da conta.

---

## 8. Fatia C: frete, viabilidade, ganho ⚠️ (branch do João, ainda não juntada)

- **Frete por CEP:** consulta de CEP (ViaCEP/BrasilAPI, grátis e sem chave) + tabela `fornecedores` → estratégia `loja_unica` ou `dividir`, frete total e economia estimada. Usa os preços por loja que a B entrega em `fontes[]`, casando pelo `dominio`.
- **Viabilidade:** soma `qtd_embalagens × preco_emb_*` e compara com o orçamento do cliente → "cabe / falta R$ X" + sugestões de economia.
- **Ganho:** "À mão: ~6 h. Aqui: 28 s. Custo de IA: R$ 0,30" (tempo estimado à mão × tempo real + `custo_usd`).
- **Exportar:** plano de compra em Excel/PDF agrupado por loja.
- **Como a B chama:** `src.rotas_resultado.resultado(orcamento_id)`, uma chamada que faz tudo e grava em `orcamentos`. Se o módulo não existir, o gancho é pulado e registrado no log.
- **P: A tabela de fretes é real?** São lojas de Recife pré-cadastradas com frete base e R$/km definidos pelo time (dados sintéticos de demo); o preço dos produtos vem da busca. ⚠️ Confirmar com o João a origem exata desses valores antes de afirmar no pitch.

---

## 9. Ideia em espera: importar IFC (BIM) ✅ doc em `docs/ideias/IFC-importacao.md`
- IFC é o formato aberto do BIM (ISO 16739). Arquivos reais têm 20–200 MB e a Vercel aceita 4,5 MB por envio, então a leitura seria **no navegador** com `web-ifc` (WebAssembly) e só a lista extraída (alguns KB) iria ao backend. Não começar antes de fechar a pesquisa de preço.
- **P: Vocês leem arquivo do Revit?** Lemos exportações em texto/CSV/Excel do Revit hoje (Fatia A). IFC está planejado, não implementado.

---

## 10. Dados e testes

### 10.1 Dados sintéticos ✅
- `docs/arquivos-teste/`: 183 arquivos de teste, 12 obras fictícias em Recife (endereços e CEPs reais), 15 formatos, cerca de 116 produtos de marcas reais em 3 grafias (completo, abreviado, genérico) e arquivos com defeito de propósito (corrompido, vazio, colunas trocadas, PDF escaneado, duplicados, acentos quebrados, `#REF!`).
- Criado **antes** do produto para os testes não serem feitos sob medida.
- Regra do repositório: só dados sintéticos.

### 10.2 pytest e geradores de fixtures ✅
- `pytest` roda os testes; `openpyxl`, `xlwt` e `msoffcrypto-tool` geram os arquivos de teste (XLSX, XLS legado, XLSX com senha).
- `tests/importacao/` (100 casos de importação, `contrato.py`) e `tests/fatia_b/` (etapas 1 a 9 da pesquisa).
- Marcador `real`: testes que usam serviços de verdade (Supabase, rede).
- **Aviso:** parte dos testes da Fatia B executa a pesquisa de verdade (rede e LLM) e gasta créditos.
- **Comando:** `python -m scripts.check_setup` valida Featherless (chat + tool calling), Langfuse e Supabase gastando poucos centavos.

---

## 11. Ferramentas de trabalho do time

| Ferramenta | Uso |
|---|---|
| **Git/GitHub** | Repositório privado; commits pequenos e frequentes como evidência para os organizadores |
| **Skills (`skills/*.md`)** | Guias para assistentes de código (padrão Agent Skills): ReAct, Featherless, Langfuse, UI. `scripts/sync_skills.sh` gera as cópias em `.claude/skills/` e `.agents/skills/` |
| **AGENTS.md / CLAUDE.md** | Regras do repositório lidas por Claude Code, Codex e Cursor |
| **n8n** (`n8n/agent-bridge.json`) | Fluxo Webhook → `/agent/run`. **Fora do produto** (decisão do projeto: o site fala direto com o FastAPI); fica como opção para canais como WhatsApp/e-mail |
| **Google Forms via Apps Script** (`forms/criar_pesquisa.gs`) | Cria a pesquisa de validação com arquitetos ("Automação em Arquitetura") para dados de mercado no pitch |
| **Claude Code / Codex** | Assistentes de código usados no desenvolvimento |

---

## 12. Perguntas gerais que podem aparecer

**Como funciona o agente, em uma frase?**
Ele pesquisa o preço, confere se é o mesmo produto, refaz a busca sozinho quando não acha lojas suficientes, pergunta ao arquiteto quando falta informação e entrega faixa de preço com fonte e confiança.

**Onde está a IA e onde não está?**
IA: extrair preço dos anúncios, decidir como reescrever a busca, redigir sugestões. Sem IA (Python determinístico): cálculo de mediana, outliers, embalagens, perda, confiança, frete, viabilidade.

**O que acontece se a busca falhar?**
Tavily falhou → DuckDuckGo. Sem resultado → cache vencido com a data. Sem nada → "Não encontrado" com botão "Pesquisar de novo". Erro em um item não derruba os outros.

**Como evitam preço inventado?**
Preço só existe se estiver no texto do anúncio, só entra na média se o anúncio for do mesmo produto, e o modelo de dados rejeita preço sem fonte.

**Como medem acerto?** ⚠️ Plano (Fatia D): rodar os arquivos de `docs/arquivos-teste/` e medir % de itens resolvidos sozinhos, % que precisaram refazer a busca, tempo e custo médios. Não afirmar números antes de medir.

**Qual o custo por orçamento?**
O sistema soma o custo de cada chamada ao LLM por orçamento. Citar apenas o valor medido nos testes, não uma estimativa.

**Quanto tempo leva?**
Meta da demo: ≈30 s para 15–20 itens, com metade em cache e buscas em paralelo. O ganho comparativo "à mão ~6 h" é uma estimativa por item (≈N min × itens), não uma medição.

**É seguro?**
Dados sintéticos; chave `service_role` só no backend; chaves fora do Git. Limites conhecidos: CORS aberto e sem autenticação (demo).

**O que não fazemos (honestidade na banca)?**
Não negociamos com lojas, não fechamos compra, não temos preço de contrato, não lemos IFC ainda, não comparamos com SINAPI (só no pitch como próximo passo), não guardamos preferências do escritório (só no pitch).

**Qual o próximo passo?**
Comparação com SINAPI, memória de marcas preferidas por escritório, integração com ERPs de obra, importação de IFC, pedidos de cotação prontos por loja.

---

## 13. Cola rápida: números e nomes

| Item | Valor |
|---|---|
| LLM do agente | `zai-org/GLM-5.2` |
| LLM de extração | `Qwen/Qwen3-32B` (reserva `google/gemma-4-31B-it`) |
| Busca | Tavily (principal), DuckDuckGo (reserva), lista fixa de 18 domínios |
| Cache | 7 dias |
| Buscas extras do agente | até 2 por item, 40 s por item, 60 s de prazo total |
| Mínimo de lojas | 2 (menos que isso aciona o agente) |
| Outliers | fora de 40%–250% da mediana |
| Confiança | alta: ≥3 lojas e dispersão ≤25%; média: ≥2 lojas e ≤50% |
| Concorrência | 8 buscas, 3 extrações, 1 chamada do agente |
| Langfuse | região US, 1 trace por orçamento |
| Status do item | buscando, definido, pendente_especificacao, nao_encontrado, erro |
| Status do agente | completed, escalated, max_steps_reached, error |
