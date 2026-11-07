# Submissão: textos da Fatia B (pesquisa de preço) para o formulário

Prontos para colar. Os números são **medidos** (fonte: `docs/revisao/fatia-b.md`); não arredondar para cima.

## Como o agente funciona (pesquisa de preço)

Para cada material da lista, o Orçamentista faz sozinho o trabalho que o arquiteto faria loja por loja:

1. **Busca** o produto na web em duas frentes ao mesmo tempo: uma lista de grandes lojas brasileiras de construção e uma
   busca aberta em lojas da **região da obra** (cidade e estado vêm do CEP).
2. **Lê os anúncios** com um modelo de linguagem rápido, que extrai preço, embalagem e diz se é **o mesmo produto**
   pedido, um parecido ou outro. **Trava anti-alucinação:** um preço só é aceito se estiver escrito no anúncio.
3. **Refaz a busca quando precisa.** Se achou menos de 2 lojas com o produto exato, um **agente ReAct** (GLM-5.2 com
   tool calling) lê o que deu errado, reformula a consulta e pesquisa de novo, até 2 vezes. Quem decide parar é o código.
4. **Calcula** em Python, sem IA: preço por unidade (R$/m², R$/L), descarta preços fora da curva, uma oferta por loja,
   mínimo, mediana e máximo, confiança, e **quantas embalagens comprar** com a perda de cada material
   ("180 m² → 2 latas de 18 L").
5. **Pergunta em vez de chutar:** item genérico ("tinta vermelha") recebe uma faixa estimada e uma pergunta ao
   arquiteto ("Qual marca, linha, cor e acabamento?"). Ele responde e o item é pesquisado de novo.
6. **Ao vivo:** cada item é gravado assim que fica pronto e aparece na tela na hora (Supabase Realtime). Todo preço vem
   com o link da loja. Cada passo fica registrado no Langfuse (o que buscou, o que leu, quanto custou).

**Robustez:** três chaves de LLM em rodízio, modelo reserva disparado em paralelo quando o principal demora, cache de
preços de 7 dias (o mesmo produto sai em menos de 1 s, com a mesma foto) e reserva de busca (DuckDuckGo) se o Tavily cair.

## Números medidos

| Medida | Valor | Onde |
|---|---|---|
| Orçamento real pelo site | 16 itens em 49 s: 11 definidos, 4 pedindo especificação, 1 não encontrado | Supabase, 07/11 |
| Custo de IA | US$ 0,0026 nesse orçamento (≈ R$ 0,015) | coluna `custo_usd` |
| Cozinha Graças, 24 itens, sem cache | 79% com preço e fonte; 2,1 lojas por item; completo em ~98 s; US$ 0,0186 | `scripts/metricas_pitch.py` |
| Com cache (demo) | 1º item na tela em ~1,3 s | idem |

## Ferramentas, modelos e APIs (Fatia B)

| Uso | Ferramenta |
|---|---|
| Leitura dos anúncios | Featherless: `Qwen/Qwen3-32B` (reserva: `mistralai/Mistral-Small-3.2-24B-Instruct-2506`) |
| Agente que refaz a busca | Featherless: `zai-org/GLM-5.2` (tool calling nativo, padrão ReAct) |
| Busca na web e imagens | Tavily (principal) e DuckDuckGo via `ddgs` (reserva) |
| Região da obra | ViaCEP |
| Banco, cache e tempo real | Supabase (Postgres + Realtime) |
| Rastreamento e custo | Langfuse |
| Backend | Python, FastAPI, hospedado na Vercel |
| Tela do item | React/Next.js (componente `ItemRow` com a "cota de preço") |

## Limites (para não prometer demais)
- Algumas lojas grandes (ex.: Leroy Merlin) não mostram o preço na página que a busca lê; o item pode sair com menos lojas.
- Cerca de 1 em cada 5 itens sem cache ainda sai sem preço confirmado; ele fica marcado com "Pesquisar de novo".
- Frete: calculado no checkout de cada loja (cálculo próprio em pausa nesta versão).
