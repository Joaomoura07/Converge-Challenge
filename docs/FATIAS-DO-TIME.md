# Fatias do time: Orçamentista Autônomo

> Divisão do trabalho do Converge Challenge. Atualizado em 07/11/2026. Contexto completo em `docs/CONTEXTO-DO-PROJETO.md`.

## A história que a demo precisa contar
> **"Ele pegou meu erro, lembrou do que eu esqueci, me disse o que comprar, onde comprar e se cabe no orçamento do cliente, e mostra de onde tirou cada preço."**

Tudo abaixo serve a essa frase. O produto é um **digital worker de orçamentação**:
- **pesquisa** cada item;
- **confere** se achou o produto certo;
- **refaz** a busca quando erra;
- **pergunta** ao arquiteto só o que não dá para deduzir;
- **entrega** o plano de compra pronto.

---

## O que entra no produto

### Essenciais (sem isso a demo fica incompleta)
| # | Função | O que faz | Fatia |
|---|---|---|---|
| E1 | **Revisor de erros** | Na revisão, aponta e sugere a correção com um clique: unidade incompatível ("tinta: 3 un" → "3 latas de 18 L?"), quantidade absurda (5.000 m de rodapé num apto de 68 m²), duplicados com nomes diferentes, colunas trocadas | A |
| E2 | **Itens esquecidos** | "Faltam 15 sacos de argamassa AC-III e 5 de rejunte para os 48 m² de porcelanato. Adicionar?" (porcelanato → argamassa + rejunte; pintura → selador + massa; vaso → válvula + assento…) | C |
| E3 | **Lista de compra com perda** | "180 m² de tinta" → "2 latas de 18 L"; "48 m² de porcelanato + 10%" → "33 caixas" | B |
| E4 | **Pesquisa agêntica** | Pesquisa → confere se é o mesmo produto, embalagem e preço plausível → refaz a busca sozinho (até 2×) | B |
| E5 | **Pergunta ao arquiteto** | Item genérico vira uma pergunta objetiva ("Qual acabamento e litragem da tinta vermelha?"); ao responder, o item é pesquisado de novo sozinho | B |
| E6 | **Confiança + fonte** | Todo preço tem link da loja; confiança alta/média/baixa pela quantidade de lojas e pela dispersão. **Nunca preço sem fonte** | B |
| E7 | **Frete por CEP** | Loja única × dividir entre lojas, com frete total e economia | C |
| E8 | **Viabilidade** | O arquiteto informa o orçamento do cliente → "Cabe? Falta R$ X. Onde economizar: 3 sugestões" | C |
| E9 | **Arquivo de exemplo** | Botão "Usar arquivo de exemplo" (3 obras de `docs/arquivos-teste/`). **Os jurados não têm arquivo do Revit na mão** | A |
| E10 | **Ganho na tela** | "À mão: ~6 h. Aqui: 28 s. Custo de IA: R$ 0,30" | C |
| E11 | **Exportar** | Plano de compra em Excel/PDF para levar ao cliente e à loja | C |

### Se der tempo (nessa ordem)
| # | Função | Fatia |
|---|---|---|
| T1 | **Pedidos de cotação por loja** prontos para enviar, com o texto de negociação | C |
| T2 | **Similar técnico mais barato** ("Votomassa AC-II faz o mesmo por 18% menos"), sempre como sugestão | B |
| T3 | **Progresso ao vivo** ("12 de 20 itens") e um botão "por quê?" que mostra o raciocínio do item | B |

### Só no pitch (não codar)
- Comparação com o **SINAPI** (tabela oficial de custos da Caixa por estado) como próximo passo.
- **Memória do escritório:** aprender as marcas preferidas de cada arquiteto.
- **Integração** com os ERPs de obra que os escritórios já usam.

---

## As fatias

### Fatia A: Entrada e revisão (Samuel)
**Tela**
- Nova obra: nome, **CEP**, **orçamento do cliente (R$)** e o upload (CSV/Excel/TXT do Revit/PDF com texto).
- Botão **"Usar arquivo de exemplo"** (E9).
- **Tabela editável** com os avisos do **Revisor de erros** (E1) e as sugestões de **itens esquecidos** (E2, vindas da C), cada uma com o botão "Aceitar".
- Botão **"Enviar para a IA"**.
- Esqueleto da página de resultado + o hook `useOrcamento(id)` (Realtime das duas tabelas), onde B e C encaixam seus componentes.

**Backend**
- `POST /orcamentos`: valida o contrato (`tests/importacao/contrato.py`), grava `orcamentos` e `orcamento_itens` (status `buscando`) e chama `pesquisar_orcamento(id)` da B **na mesma requisição** (limite da Vercel).
- `classificar_item()`: decide definido × pendente antes da busca. **Função única**; a B confirma, a C só lê.
- `revisar_itens(itens)`: regras do E1 em Python; o LLM só redige a sugestão.

**Dados**
- **Dono do arquivo SQL único**: `orcamentos`, `orcamento_itens`, `cache_precos`, `fornecedores`, juntando os campos que B e C pedirem.
- Rodar os 100 casos de `tests/importacao/` e os arquivos de `docs/arquivos-teste/`. Arquivo ruim deve dar mensagem amigável.

**Cuidados**
- `.txt` do Revit em PT → forçar tab no PapaParse.
- CSV do Excel vem em Windows-1252.
- Instalar o SheetJS pelo CDN oficial (o `xlsx` do npm é vulnerável).

### Fatia B: Pesquisa agêntica de preço (Enzo)
**Backend**
- `pesquisar_orcamento(id)`: `asyncio` + semáforos (3 LLM, incluindo o agente / 8 busca). Para cada item:
  1. **cache** (`cache_precos`, 7 dias);
  2. **busca:** Tavily com lista fixa de lojas, até 5 resultados e imagens; DuckDuckGo se o Tavily falhar;
  3. **extrai e confere** com um modelo rápido (`Qwen/Qwen3-32B`): preço, loja, embalagem e "é o mesmo produto?";
  4. **refaz** com o agente ReAct (GLM-5.2) se não conferir, até 2×;
  5. **calcula:** mediana sem outliers → mín/médio/máx por embalagem e por m² (quando a unidade permitir);
  6. **lista de compra:** nº de embalagens com perda (E3);
  7. **confiança e fontes** (E6);
  8. **grava** o item (o Realtime atualiza a tela).
- Item genérico → faixa **estimada** + **pergunta ao arquiteto** (E5). Quando ele responde → `repesquisar_item(item_id)`.
- Falha total → cache vencido ("preço de dd/mm") ou "Não encontrado" + botão "Pesquisar de novo".
- Fim → chama `calcular_logistica(id)` da C.
- Langfuse: 1 árvore por orçamento, 1 galho por item. As iterações (errou → refez) ficam visíveis para o pitch.

**Tela**
- `ItemRow`: imagem, produto, "180 m² → 2 latas de 18 L", a **cota de preço** (mín–médio–máx), a confiança, os links das lojas e a pergunta quando estiver pendente.
- Carregamento em linguagem de prancha: **cota tracejada + hachura 45°** até o dado chegar (ver `skills/04-ui-design.md`).

**Demo e configuração**
- `scripts/aquecer_cache.py`: pré-aquece metade dos itens do arquivo da demo.
- Checar: anon key do Supabase no site, tempo máximo da função na Vercel ≥ 60 s, leitura (RLS) das tabelas.

**Cuidados**
- O GLM-5.2 "pensa" antes de responder: não usar limite de tokens baixo.
- Modelo reserva: `Qwen/Qwen3-32B`.

### Fatia C: Itens esquecidos, frete e resultado (João)
**Backend**
- `sugerir_complementos(itens)` (E2): regras por categoria (porcelanato → argamassa + rejunte + nivelador; pintura → selador + massa + fita/lixa; vaso → válvula + assento; drywall → perfis + massa + fita + parafuso) com a quantidade calculada. A Fatia A mostra na revisão.
- `calcular_logistica(id)` (E7): CEP da obra (ViaCEP/BrasilAPI) + tabela `fornecedores` → `{estrategia: loja_unica|dividir, lojas, frete_total, economia_estimada}`. Usa os **preços por loja** que a B entrega em `fontes`.
- `calcular_viabilidade(id)` (E8): total mín/médio/máx × orçamento do cliente → "cabe / falta R$ X" + 3 sugestões de economia (trocar por similar, dividir frete, revisar itens pendentes).
- `exportar(id)` (E11): plano de compra em Excel/PDF agrupado por loja.
- Ganho (E10): tempo à mão estimado (≈ N min por item) × tempo real + custo de IA (`cost_usd` que o agente já calcula).
- (T1) Pedidos de cotação por loja com o texto de negociação.

**Tela**
- Resultado final: total e faixa, **cabe ou não no orçamento**, pendentes, frete e economia, ganho de tempo e o botão **Exportar**.

**Dados**
- Cadastrar os fornecedores no Supabase: **as mesmas redes que a busca encontra** (Leroy Merlin, C&C, Telhanorte… com as lojas de Recife), com `dominio`, CEP, frete base, R$/km e pedido mínimo.

### Fatia D: Negócio e apresentação (a definir até as 12h)
Vale **metade da nota** (viabilidade como startup + pitch).
- **Números de mercado:** quantos arquitetos e escritórios existem (fonte: CAU/BR), quanto tempo leva um orçamento à mão (perguntar aos mentores e a arquitetos conhecidos), quanto cobrar (por orçamento ou assinatura por escritório).
- **Why now:** IA que pesquisa e confere sozinha ficou barata (custo real por orçamento medido pelo próprio sistema).
- Slides, roteiro e **vídeo** (domingo de manhã), **submissão até 12h30 de domingo**.
- **Prêmio AWS:** domínio `.com.br` + landing simples + e-mail no domínio (sábado à noite).
- **Métricas para o pitch** (com a B, sábado à noite): rodar os arquivos de `docs/arquivos-teste/` e medir % de itens resolvidos sozinhos, % que precisaram refazer a busca, tempo e custo médio por orçamento.

---

## Contratos entre fatias (fechar às 10h)
| De → Para | Contrato |
|---|---|
| A → B | `pesquisar_orcamento(orcamento_id)` chamada **na mesma requisição**; itens começam com status `buscando` |
| A ↔ C | `POST /revisao/sugestoes` → `{erros: [...] (A), complementos: [...] (C)}`, mostrados na tabela de revisão |
| B → C | Por item: `fontes: [{loja, dominio, url, preco_embalagem}]`, `embalagem`, `qtd_embalagens`, `preco_emb_min/med/max`, `confianca`, `estimativa` |
| B → C (gatilho) | No fim, a B chama `calcular_logistica(id)` e `calcular_viabilidade(id)` → gravam em `orcamentos` → o Realtime atualiza o resultado |
| Todos | Status do item: `buscando` · `definido` · `pendente_especificacao` · `nao_encontrado` · `erro` |

## Regras do agente (para todo mundo)
- **Nunca inventar preço:** sem fonte, sem preço.
- **Perguntar em vez de chutar:** se falta marca, acabamento ou medida, pergunta ao arquiteto.
- **Sugerir, nunca aplicar sozinho:** correções, complementos e similares mais baratos precisam de clique do arquiteto.
- **Tudo rastreável no Langfuse.**

## Marcos
| Quando | Marco |
|---|---|
| Sáb 10h00 | Contratos fechados; cada fatia testa sozinha (A com `tests/importacao`, B pela linha de comando, C com JSON falso) |
| Sáb 12h00 | Dono da Fatia D definido |
| **Sáb 14h00** | **Integração:** upload real → preço na tela ao vivo |
| **Sáb 17h00** | **Demo gravável:** E1–E7 funcionando |
| Sáb noite | E8–E11 · domínio/AWS · slides v1 · métricas |
| Dom 10h30 | Congela funcionalidades → vídeo → **submissão até 12h30** |
| Dom 16h00 | Demo Day |

## Roteiro da demo (≈ 75 s dentro dos 3 min)
1. "Usar arquivo de exemplo" → a tabela aparece com **2 erros apontados** (aceita a correção) e **itens esquecidos** (aceita).
2. "Enviar para a IA" → os itens chegam ao vivo; um genérico vira **pergunta** → responde → o item se refaz.
3. Abre o **Langfuse** num item em que o agente **errou e refez** a busca.
4. Resultado: **cabe no orçamento?**, **loja única × dividir**, **ganho de tempo** → Exportar.
