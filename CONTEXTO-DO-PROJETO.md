# Orçamentista Autônomo — contexto do projeto

> Resumo para o time do **Converge Challenge powered by Tako**. Plano da Fatia A atualizado em 07/11/2026.

## 0. Fatia A — entrada e revisão, divisão atualizada

A referência de escopo é [FATIAS-DO-TIME.md](FATIAS-DO-TIME.md), cópia do arquivo enviado por Samuel em 07/11/2026. Neste checkout, o contexto está na raiz. O plano detalhado está em [PLANO-FATIA-A.md](PLANO-FATIA-A.md).

### Responsáveis

- **Samuel / A** entrega Nova obra com nome, CEP e orçamento do cliente, upload CSV/Excel/TXT do Revit/PDF com texto, cadastro manual, três exemplos, tabela com aceite de correções e complementos, envio e esqueleto de resultado com `useOrcamento(id)`.
- **Samuel / A** também é dono do SQL único de `orcamentos`, `orcamento_itens`, `cache_precos` e `fornecedores`, de `classificar_item()`, `revisar_itens(itens)`, `POST /revisao/sugestoes` e `POST /orcamentos`.
- **Enzo / B** implementa `pesquisar_orcamento(id)`, pesquisa, conferência, preços com fontes e confiança, embalagens com perda, perguntas, `repesquisar_item(item_id)` e `ItemRow`. Ao final chama logística e viabilidade da C.
- **João / C** implementa `sugerir_complementos(itens)`, logística, viabilidade, ganho de tempo, exportação e componentes finais. Cadastra as lojas na tabela `fornecedores` criada pela A.
- **D** cuida de negócio e apresentação. Responsável a definir segundo o documento do time.

### Contratos confirmados pela nova divisão

- A grava os itens em `buscando` e chama `pesquisar_orcamento(orcamento_id)` da B **na mesma requisição**, aguardando seu retorno.
- A revisão chama `POST /revisao/sugestoes`, que reúne `{erros: [...], complementos: [...]}`. A calcula erros e C calcula complementos.
- A classificação é função única da A. B confirma e C lê. Preservar classificação de negócio separadamente do estado de processamento.
- Estados oficiais do item são `buscando`, `definido`, `pendente_especificacao`, `nao_encontrado` e `erro`. Fechar separadamente os estados gerais de orçamento.
- O hook acompanha as duas tabelas por Realtime. Fechar na etapa 01 como a tela conhece o ID antes da resposta do POST. UUID gerado pelo cliente é proposta a validar no contrato.
- Correções, complementos e similares exigem clique do arquiteto. Cada preço apresentado pela B deve ter fonte.

### Etapas atualizadas

Os prompts completos e os critérios de teste estão no plano.

| Etapa | Entrega |
|---|---|
| 01 | Diagnóstico e contratos |
| 02 | SQL único e persistência |
| 03 | Nova obra e cadastro manual |
| 04 | CSV e três arquivos de exemplo |
| 05 | Classificação única e revisor E1 |
| 06 | Sugestões A/C e aceite na tabela |
| 07 | Página de resultado e useOrcamento |
| 08 | POST /orcamentos e integração na mesma requisição |
| 09 | Excel |
| 10 | TXT do Revit |
| 11 | PDF com texto |
| 12 | Encaixe dos componentes B/C |
| 13 | Bateria e regressões |
| 14 | Demo e entrega |

### Estado em 07/11/2026

- **Etapa 08 feita no servidor (07/11/2026) — POST /orcamentos. Commit de 07/11/2026. Tela NÃO ligada.** Skills: `managing-orcamento-data` (regras já carregadas na sessão), lido o código da B (`src/orcamento.py`, `src/database.py`) e o contrato (`tests/importacao/contrato.py`). Não usei `building-react-agents`, `tracing-with-langfuse` nem `integrating-featherless` além de um span `orcamentos.gravar` (sem entrada/saída capturadas).
  - **Arquivos:** `src/rotas_orcamentos.py` (novo), `tests/test_rotas_orcamentos.py` (novo), duas linhas em `src/main.py` (`include_router`). Nada em `frontend/`, nos arquivos de João/Enzo nem em `src/rotas_revisao.py`/`src/revisao.py` (etapas 05/06).
  - **Fluxo:** valida o corpo (Pydantic estrito: quantidade em texto, unidade fora da lista, CEP, orçamento do cliente, UUID e ids repetidos dão 422) → monta itens com `classificar_item()` (A) → chama a função SQL `criar_orcamento` (itens em `buscando`) → 409 se o mesmo UUID chegou com conteúdo diferente → chama `pesquisar_orcamento(id)` da B na mesma requisição, nos casos `criado` e `existente` (a reserva da B impede pesquisa dupla) → devolve `{orcamento_id, resultado, itens, complementos_recusados_ignorados, pesquisa}`. Falha da pesquisa: 502 com `orcamento_id` e `recuperavel: true` (o orçamento fica gravado; reenviar o mesmo corpo é seguro). Erro de regra do banco (SQLSTATE 23514 etc.): 422. Outro erro do banco: 502. Sem Supabase: 503.
  - **Resultados reais:** 32 testes novos passam e a suíte inteira deu 563 passam, 18 skipped, 16 deselected, na imagem Docker `hackathon-api` (com `pip install -r requirements.txt`; a imagem não tinha `openpyxl`). O payload que a rota monta foi aceito pela função SQL real em Postgres 16 descartável: 1ª chamada `criado`, 2ª `existente`; itens `buscando`, classificação gravada, complemento com regra/origem/aceito/estimativa_consumo, CEP `01310100` e `1234.56` preservados.
  - **NÃO testado:** Supabase real; `pesquisar_orcamento` real (o teste usa um falso); timeout na Vercel; perda da resposta contra o deploy; duas requisições simultâneas com a B real; o deploy na Vercel (João diz que está desatualizado); botão "Enviar para a IA" na tela (depende de `Caderno.tsx`/`lista.ts`, que a etapa 06 altera).
  - **PROPOSTAS (sem aceite):** complemento com `aceito: false` NÃO é gravado (ficaria `buscando` e a B o pesquisaria à toa); o hash de conflito cobre obra e itens, não a `origem`; limite de 5000 itens por requisição (o contrato aceita 100 mil); o corpo usa `id` (ID estável da tela) como `id_linha`.
  - **Divergência a resolver com Enzo:** `BancoSupabase` da B reserva e grava com UPDATE direto e NÃO usa `reservar_pesquisa`/`gravar_resultado_item`/`finalizar_pesquisa` do SQL (sem número de tentativa nem proteção contra gravação atrasada). Funciona, mas a proteção de execução lenta/retomada que testamos no SQL não está em uso. Também: a B grava `premissa`, coluna que o SQL não tem (ela já contorna).
  - **Próximo passo:** depois da 06, ligar o botão "Enviar para a IA" (incluindo UUID já gerado na tela, tratamento de 409/502/422 e reenvio), e a etapa 07 (`useOrcamento` e página de resultado).

- **Etapa 06 feita (07/11/2026) — sugestões A/C e aceite na tabela. Commit de 07/11/2026.** Skills carregadas: `managing-orcamento-data` e `building-orca-ui` (instruções de `skills/05` e `skills/07`). Regras aplicadas: correções e complementos são só propostas e o clique aplica uma vez; editar a lista invalida o que foi calculado antes; quantidade estimada de complemento (consumo, da C) visualmente distinta de preço estimado (da B); complemento só vira linha depois do aceite; estados vazio, leitura, erro com recuperação e C indisponível; foco e rótulos nos botões. Skills `integrating-featherless`, `tracing-with-langfuse` e `building-react-agents` não foram usadas (nada de LLM, tool ou prompt novo).
  - **Decisão (Samuel, opção B):** `POST /revisao/sugestoes` é do João (`src/rotas_resultado.py`, devolve só `{complementos}`) e seus testes dependem dele; nenhum arquivo do João foi alterado. O endpoint combinado da A é **`POST /revisao/sugestoes/completo`**, em `src/rotas_revisao.py`, chamando `sugerir_complementos(itens)` direto (quantidade de texto convertida para número). No frontend o caminho está numa constante única, `CAMINHO_SUGESTOES` em `frontend/src/lib/revisao/api.ts`.
  - **PROPOSTA (sem aceite do João): unificação futura.** O João remove o handler `sugestoes` e o `SugestoesIn` de `src/rotas_resultado.py` (linhas 124–131) e troca nos testes dele (`tests/test_rotas_resultado.py`, `tests/test_integracao_fatia_c.py`) as chamadas à rota por chamadas diretas a `sugerir_complementos`; a A então assume `POST /revisao/sugestoes` (mesmo corpo e resposta do `/completo`) e só `CAMINHO_SUGESTOES` muda no frontend.
  - **Resposta do `/completo`:** `{revisao_id, erros[], complementos[], complementos_disponiveis, complementos_erro}`. Cada complemento: `id` estável (hash de regra + descrição, então uma recusa vale depois de editar quantidades), `regra`, `descricao`, `quantidade`, `unidade`, `categoria`, `motivo`, `origem_linhas`, `origem_item_ids`, `estimativa_consumo` (o `estimativa` do João, renomeado para não se confundir com a estimativa de preço da B). Se a C falhar, os erros E1 saem do mesmo jeito, `complementos_disponiveis=false` e a mensagem não expõe a exceção.
  - **Frontend (`frontend/src/lib/revisao/`, `components/PainelSugestoes.tsx`):** `lista.ts` ganhou `decisoes` (id → aceita/recusada) e as ações `aceitar_correcao`, `aceitar_complemento`, `recusar_sugestao`, todas idempotentes no reducer (aceite repetido não reaplica; correção só aplica se o valor atual ainda é o que a regra viu; remover um complemento aceito libera a sugestão; substituir a lista zera as decisões). Linha de complemento aceito: campo `sugerida` (regra, motivo, origem, `estimativaConsumo`). `revisor.ts` (sem React) recalcula 700 ms depois da última edição, cancela a consulta em voo e descarta respostas de versão antiga ou de consulta antiga; sugestões de versão antiga ficam travadas (Aceitar desabilitado) até a nova chegar. A tela chama com `redigir: false` (texto fixo, sem LLM a cada edição).
  - **Resultados reais:** backend `tests/revisao`: **79 OK** (eram 71; 8 novos do `/completo`: exemplo do João, ids estáveis, quantidade em texto BR, quantidade vazia, Casa Térrea, C indisponível, lista vazia, rota do João intacta). Frontend: `npm run typecheck` sem erros; `npm test` **163 OK** em 10 arquivos, dos quais **40 são desta etapa**, em `lib/revisao/`: aplicação, decisões no reducer, revisor com retorno atrasado/edição durante a leitura/erro de rede/C indisponível/parar, API, e dois exemplos reais); `npm run build` OK. Suíte Python inteira: 562 OK, 18 ignorados, 1 falha em `tests/test_rotas_orcamentos.py::test_rota_registrada_no_app`, arquivo novo da etapa 08 que apareceu na árvore durante esta sessão (não é desta etapa; não investiguei).
  - **Exemplos reais:** a entrada sai do leitor de CSV de verdade e a resposta foi capturada do backend real (`frontend/src/lib/revisao/fixtures/{casa-terrea,joao}.json`, sem LLM). Casa Térrea: 4 erros (`sc`×2, `br`×2) e 4 complementos; aceitar as 4 correções troca só a unidade dessas linhas, recusar deixa a lista idêntica. Exemplo do João (porcelanato 48 m², tinta 120 m²): argamassa 15, rejunte 5, niveladores 3, selador 2, massa 3, fita 8, lixa 60, sem erros E1. O primeiro teste de cada exemplo falha se o leitor mudar a entrada (a fixture precisa ser recapturada).
  - **Navegador (REAL: Chrome instalado no Windows via playwright-core fora do projeto, front em `next dev` na porta 3101, API real no Docker na porta 8010 com C real; só o Langfuse desligado): 30/30 verificações OK**, desktop 1280 px e 375 px: Casa Térrea mostra 4 erros e complementos, lista intacta antes do clique, duplo clique em Aceitar altera exatamente 1 linha, Recusar não altera a lista, demais correções aplicadas e o envio continua bloqueado (o número ambíguo `9.500` segue inválido: sugestão não desbloqueia nada), complemento aceito entra como linha "Sugerido · aceito por você" com selo "Quantidade estimada" e linhas de origem, exemplo do João digitado à mão gera 15/5/3 e nada entra sem clique, sem rolagem horizontal em 375 px antes e depois de aceitar, botão Aceitar com 40 px de altura, sem erros de console. **SIMULADO no navegador (rotas interceptadas):** resposta atrasada em 2,5 s com edição no meio (a resposta velha não aparece; 2 consultas), C indisponível (resposta real com `complementos_disponiveis` forçado a false), erro de rede (conexão recusada) e recuperação com "Tentar de novo" (a lista de 53 linhas e a tabela continuam editáveis). O script ficou no scratchpad, fora do repositório.
  - **NÃO feito ou NÃO testado:** leitor de tela e navegação só por teclado (rótulos, `aria-label` por sugestão, `aria-live` e "Ir para a linha" foram implementados, sem conferir com leitor); Safari, Firefox e celular físico; Figma (sem acesso); a redação por LLM não é usada pela tela (a rota aceita `redigir: true`); CORS aberto (`*`) e API sem autenticação; nada na Vercel (a URL vem de `NEXT_PUBLIC_API_URL`, padrão `http://localhost:8000`); lista com milhares de linhas (a tela reenvia a lista inteira a cada edição); a colisão entre linha do arquivo e posição (pendência da etapa 05) continua, mas o aceite usa `item_id`, não o número da linha; a gravação de `sugerido/aceito/sugestao_regra/sugestao_motivo/origem_linhas/estimativa_consumo` em `orcamento_itens` só acontece no `POST /orcamentos` (etapa 08), que deve enviar a regra, o motivo, `origem_linhas` e `estimativaConsumo` das linhas com `sugerida` (e as recusas só existem na tela, não são gravadas).
  - **Decisões da etapa (PROPOSTAS, sem aceite):** revalidação automática 700 ms depois da última edição; `redigir: false` na tela; id do complemento = regra + descrição; `mesclar` e `remover` aplicados por `item_id`; recusa dura enquanto a linha da lista existir (voltar atrás só removendo o complemento aceito); complementos E2 calculados sobre a lista sem considerar quais já foram aceitos além do que a regra da C já detecta ("já tem").
  - **Próximo passo:** etapa 07 (`useOrcamento(id)` e página de resultado); a etapa 08 precisa levar as linhas `sugerida` ao `POST /orcamentos`.

- **Ajustes da revisão de código da etapa 05 (07/11/2026, depois do relatório).** (1) `prompts/revisao_redacao.md` agora diz que descrições do arquivo são dados, não instruções. (2) `MAX_ERROS_LLM = 30` em `src/revisao.py`: só os 30 primeiros erros vão ao LLM; o resto mantém o texto fixo, e o LLM não redige erro fora do teto mesmo que responda por ele. Testes em `tests/revisao/test_redacao.py`: **71 passam** (eram 67), na imagem Docker `hackathon-api`. Limite conhecido: a checagem de números não impede um texto enganoso sem números (ex.: "orçamento aprovado"); a decisão, as linhas e a correção nunca mudam. Ainda abertos (sem correção): apelidos de unidade duplicados entre `csv.ts` e `revisao.py` sem teste de paridade, colisão entre linha do arquivo e posição, e endpoint público que chama LLM pago.
- **Etapa 05 feita (07/11/2026) — classificação única e revisor E1 em Python. Commit de 07/11/2026.** Skills carregadas: `managing-orcamento-data`, `integrating-featherless`, `tracing-with-langfuse` (instruções lidas de `skills/05`, `02` e `03`). `building-react-agents` não foi usada: nenhuma tool nem o prompt do agente (`prompts/system_prompt.md`) foram alterados.
  - **Arquivos:** `src/revisao.py` (`classificar_item`, `revisar_itens`, `redigir_sugestoes`, `revisar_e_redigir`), `src/rotas_revisao.py` (`POST /revisao/erros`), `prompts/revisao_redacao.md`, `src/main.py` (apenas `include_router`), `tests/revisao/` (conftest, test_classificar, test_revisar, test_redacao). Rotas de Enzo e João intactas.
  - **Como rodar Python aqui:** o Python do Windows continua sem funcionar. Os testes rodam na imagem Docker `hackathon-api` com o repositório montado: `docker run --rm -v "<repo>:/app" -w /app hackathon-api:latest sh -c "pip install -q pytest tavily-python ddgs && python -m pytest tests"`. A imagem está desatualizada em relação ao `requirements.txt` (falta `tavily`).
  - **Comportamento:** `classificar_item(desc)` → `definido` (marca ou modelo reconhecido em lista de ~100 marcas/linhas, palavra inteira, sem acento; "cor coral" não conta) ou `pendente`. `revisar_itens(itens)` é pura e determinística, não altera a lista, e devolve erros com `id` estável (hash), `regra`, `linhas`, `item_ids`, `campo`, `valor_atual`, `correcao` (`alterar`/`remover`/`mesclar` ou `None`), `motivo`, `fatos`, `texto`, `redacao`. Regras: **unidade** (fora da lista oficial como `sc`/`br`/`cx`→`un`; grafia como `mts`→`m`; incompatível com a família do produto, p.ex. tinta em `m`, vaso em `m²`; em branco com família conhecida), **quantidade** (faixa plausível por família e unidade; correção só para erro de milhar; rejunte/argamassa acima de 1,5× a área de revestimentos da lista), **duplicado** (mesmo nome normalizado → mesclar somando; nomes distintos com mesma família, unidade e quantidade, sem conflito de cor/acabamento/medida e com ao menos uma linha genérica → remover a genérica), **colunas trocadas** (um erro agrupa todas as linhas com número em Unidade e texto ou vazio em Quantidade). O LLM (`redigir_sugestoes`) recebe só fatos e correção já decididos, devolve uma frase por `id`; texto com número fora dos fatos, vazio, longo ou JSON inválido, e qualquer falha de rede, voltam ao texto fixo. `id`, `linhas` e `correcao` nunca vêm do modelo.
  - **Langfuse:** span `revisao.e1` (chain) com só contagens (itens, erros por regra, quantos redigidos pelo LLM; sem descrições) e generation `llm.featherless` com modelo, tokens e custo; falha de redação marca WARNING no span. Tracing ligado testado uma vez com a conta real; a árvore não foi inspecionada na interface do Langfuse.
  - **Resultados reais:** `tests/revisao`: **67 testes OK** (classificação 22, revisor 31, redação e rota 14). Suíte inteira: 446 OK, 17 ignorados, 0 falhas depois de instalar `tavily`/`ddgs` na imagem (antes disso 1 falha do Enzo, `test_rodizio_pula_chave_esgotada`, por falta do módulo). `python -m scripts.check_setup` (Docker): Featherless GLM-5.2 com tool calling, Langfuse, Supabase, Tavily e DuckDuckGo OK. Caminho feliz real: Casa Térrea Aldeia → 4 erros (`sc`×2, `br`×2) redigidos pelo GLM-5.2 sem número inventado. Exceção: falha do LLM, JSON inválido, número inventado e corpo inválido na rota (422), todos testados. Acervo: `lista_com_duplicados.csv` acusa exatamente as 9 linhas genéricas esperadas e nada além; `lista_colunas_trocadas.csv` gera 1 erro com as 26 linhas; `quantidades_unidades_bagunçadas.csv` e `lista_materiais_INCOMPLETA.csv` geram os erros de unidade esperados; Casa Térrea não gera duplicado nem coluna trocada. Falsos positivos cobertos por regra: unidade (`m²`/`m2`, `pç` em montante), quantidade (3.000 parafusos, 9.500 tijolos, rejunte sem referência), duplicado (duas marcas definidas, cor, medida, acabamento, quantidade, unidade ou nível diferentes), colunas (unidade numérica com quantidade numérica, quantidade vazia com unidade válida), classificação ("tinta cor coral").
  - **Defeito achado e corrigido nos testes:** "seda" nunca era lida como acabamento acetinado (o radical cortava para "sed"), então "Toque de Seda" × "fosca" virava duplicata falsa.
  - **NÃO feito ou NÃO testado:** o frontend não chama a rota nem mostra as sugestões (etapa 06); `POST /revisao/sugestoes` com os complementos de João não existe aqui; nada foi aplicado no Vercel; as listas de marcas, famílias e faixas foram montadas a partir do acervo sintético e tendem a deixar passar produtos fora dele (o erro vira omissão, não falso alarme); "quantidade desproporcional" usa faixas por família, não a área da obra (a tela ainda não tem área); colunas Descrição × Quantidade trocadas e TXT/XLSX/PDF não são cobertos; a lista da tela não leva `ambiente`/`extras`, então a mesma peça repetida em ambientes diferentes pode ser proposta como mesclagem (sempre depende do clique); o Python do conftest imita o `csv.ts`, não o roda; a árvore do trace não foi conferida na interface.
  - **Decisões da etapa (PROPOSTAS, sem aceite):** `sc`, `br`, `cx`, `lata` etc. → `un` (a B converte a embalagem); correção de milhar só quando o valor é múltiplo de 1000; duplicado de nomes distintos só com ao menos uma linha `pendente` (duas marcas definidas nunca se apontam); mesclar soma as quantidades; `revisao_id` = hash do conteúdo da lista; formato de `correcao` (`acao`, `alteracoes[{item_id, linha, campo, de, para}]`, `remover[{item_id, linha}]`) e rota `POST /revisao/erros`, para a etapa 06 compor com os complementos da C; modelo da redação = `FEATHERLESS_MODEL_FAST` se existir, senão o principal.
  - **Próximo passo:** etapa 06 (`POST /revisao/sugestoes`, IDs e `revisao_id` com a C, botão Aceitar na tabela).

- **Etapa 04 feita (07/11/2026) — CSV e três exemplos em `frontend/`. Não commitada.** Skills usadas: `importing-materials` e `building-orca-ui` (instruções lidas de `skills/06-material-import.md` e `skills/07-orca-ui-fatia-a.md`). Especificação seguida: `docs/testes/casos-de-teste-importacao.md`, decisões D1–D7, contrato de `tests/importacao/contrato.py`.
  - **Arquivos:** `frontend/src/lib/importar/{tipos,csv,paraLinhas,exemplos}.ts`, testes `csv.fixtures.test.ts` e `exemplos.test.ts`, `frontend/src/components/Importador.tsx`, `frontend/public/exemplos/{apto-boa-viagem,casa-terrea-aldeia,escritorio-ilha-do-leite}.csv` (cópias de `docs/arquivos-teste`, bytes originais mantidos), mudanças em `Caderno.tsx`, `lista.ts` (campo opcional `linhaOrigem`) e `globals.css`; `papaparse` 5.4.1 e `@types/papaparse` fixados; entrada `orca-frontend` em `.claude/launch.json`.
  - **Comportamento:** o leitor decide codificação (BOM UTF-8/UTF-16, UTF-8 estrito, UTF-8 com byte defeituoso com aviso, senão Windows-1252), separador (`;`, tab, `,`, `|` por consistência de colunas, sem a detecção do PapaParse), cabeçalho (primeira linha com 2+ papéis; cabeçalho em duas linhas; título acima), sinônimos pt/en, unidade no cabeçalho `Área (m²)`, número BR/EN pelo estilo dominante do arquivo (D4; sem contexto, `NUMERO_AMBIGUO` e quantidade fica vazia), `extras` com valor bruto, moeda `R$` como número, SketchUp (descarta `Group`, unidade `un`), limites de 20 MB e 100 mil itens, recusa de binário/PNG/PDF/zip. Na tela: botão "Escolher arquivo CSV" e "Usar arquivo de exemplo" (3 obras) passam pelo mesmo `processar()`; lista existente pede "Acrescentar", "Substituir" ou "Cancelar"; arquivo com erro mantém a lista e mostra mensagem de recuperação; avisos listados com a linha do arquivo; campos vazios ou inválidos aparecem já marcados.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **116 testes OK**, dos quais **68 estão em `csv.fixtures.test.ts`** (todas as variantes CSV de `tests/importacao/fixtures` contra os `esperado.json`, mais TC-100 determinismo e o limite de 20 MB); `npm run build` OK. No navegador (servidor `next dev`): exemplo Apartamento Boa Viagem lê 47 itens em Windows-1252 sem erro; editar uma linha, carregar a Casa térrea e "Acrescentar" mantém a edição (47+53=100) e marca 5 campos com erro; PNG renomeado, arquivo vazio, sem cabeçalho e aspas não fechadas mostram o erro e preservam a lista; "Substituir" troca a lista; celular de 375 px sem rolagem horizontal; sem erros de console.
  - **Achados nos exemplos:** Casa térrea tem unidades `sc` (saco) e `br` (barra), fora da lista oficial, e o valor `9.500` ambíguo sem contexto (tijolo, linha 16): 5 campos ficam marcados e o envio bloqueado até o arquiteto corrigir. Apartamento (47 itens) e Escritório (33) entram sem erro. A etapa 05 pode propor a correção de `sc`/`br`.
  - **NÃO feito ou NÃO testado:** casos de TXT/XLSX/ods/html/PDF do mesmo acervo (etapas 09–11); `run-front.mjs` não foi usado (o leitor é TypeScript; os casos rodaram pelo vitest com a mesma comparação); TC-084 (50 mil linhas) e TC-085 (25 MB) dependem de `gerar_fixtures.py --grandes` (Python do Windows não roda): o limite de 20 MB foi testado com bytes sintéticos; a tela renderiza todas as linhas, sem virtualização; leitor de tela, teclado completo e Safari/Firefox; Figma (sem acesso); confirmar no JSON enviado à API depende da etapa 08 (hoje o envio é desabilitado).
  - **Decisões da etapa (PROPOSTAS, sem aceite):** `NUMERO_AMBIGUO` deixa a quantidade em branco em vez de adivinhar; alias `pç/pc/peça → un` e `ml → m`; `UNIDADES_MISTAS` só avisa quando m, cm e mm aparecem na mesma categoria; unidades fora da lista oficial (`sc`, `br`) permanecem como texto e viram erro da tela. Os três exemplos escolhidos por Samuel (confirmado): 01 Apartamento Boa Viagem, 02 Casa térrea Aldeia, 06 Escritório Ilha do Leite; o par `lista_materiais_INCOMPLETA.csv` (01) segue como candidato à demo de erros.
  - **Próximo passo:** etapa 05 (classificação única e revisor E1).

- **Skills implementadas para a Fatia A** — `building-orca-ui` em `skills/07-orca-ui-fatia-a.md`, `managing-orcamento-data` em `skills/05-orcamento-data.md` e `importing-materials` em `skills/06-material-import.md`. Registradas em `.claude/skills` e `.agents/skills` pelo script do repositório. CLAUDE.md exige carregar a skill aplicável antes de editar e os 14 prompts indicam seus nomes. As três skills anteriores de agente, Featherless e Langfuse continuam disponíveis. Validação estrutural concluída; uso efetivo na sessão do Claude será conferido no próximo retorno.

- **CORREÇÃO (07/11/2026, depois do commit cd46ae7): `cache_precos` agora segue o formato REAL do Enzo** (`sql/002_cache_precos.sql` e `src/cache.py` no origin/main: chave, descricao, ofertas, imagem_url, modelo, provedor, iteracoes, atualizado_em). A versão aplicada por Samuel renomeou a tabela do Enzo para `cache_precos_antiga_*` e criou outra com `resultado`, o que quebraria o código dele. O SQL novo nunca renomeia: completa as colunas faltantes e remove `resultado`. Bateria: 275 OK / 0 falhas em duas execuções (inclui tabela do Enzo com dados e o estado da versão anterior); verificação: 91 ok. **Samuel precisa rodar o `sql/002_orcamentos.sql` novamente no Supabase** e depois o verificar; os dados do cache antigo, se importarem, estão em `cache_precos_antiga_*`.
- **SQL APLICADO no Supabase real (07/11/2026), informado por Samuel.** Samuel rodou `sql/002_orcamentos.sql` e `sql/verificar_supabase.sql` no SQL Editor e relatou que "deu tudo certo" (não vi a saída; o número exato do resumo não foi registrado). A 1ª tentativa falhou com `ERROR 42703: column "resultado" does not exist`: já existia uma `cache_precos` de outro formato no projeto. Correção: o SQL agora renomeia uma `cache_precos` fora do contrato para `cache_precos_antiga_<data>` e cria a tabela limpa (teste novo, bateria em 273 OK / 0 falhas em duas execuções). Próximo: avisar Enzo e João (usar `service_role` no backend), seed de `fornecedores`. Ainda NÃO testado no real: Realtime entregando eventos, chamadas `supabase.rpc` de B/C. O texto abaixo, escrito antes da aplicação, descreve o preparo.
- **SQL pronto para aplicar no Supabase (07/11/2026).** Skill usada: `managing-orcamento-data` (`skills/05-orcamento-data.md`). Arquivos: `sql/002_orcamentos.sql` (acrescentado `orcamentos.ganho jsonb` nullable, mais `ADD COLUMN IF NOT EXISTS` para `logistica`, `viabilidade` e `ganho` em bancos que tenham versão anterior do arquivo; removido `create extension pgcrypto`, desnecessário no Postgres 13+/Supabase), `scripts/testar_sql_orcamentos.sh` (nova seção 10b e checagens de papéis para as escritas de João), `sql/verificar_supabase.sql` (somente leitura: tabelas+RLS, colunas, funções e permissões, políticas, publicação Realtime; uma tabela `secao|item|situacao|detalhe` e linha de resumo) e `docs/APLICAR-SUPABASE.md` (passo a passo). Confirmado por leitura: todas as colunas listadas por Enzo e João existem com os nomes exatos (`fornecedores`: id, nome, dominio, cep, lat, lon, frete_base, rs_por_km, pedido_minimo; `orcamentos` e `orcamento_itens` conforme o pedido, `origem_linhas` é `integer[]`).
  - **Testes reais (Postgres 16 descartável em Docker, papéis simulados anon/authenticated/service_role): 270 verificações OK, 0 falhas, em duas execuções seguidas** (1ª rodada teve 1 falha do próprio teste, valor esperado errado, corrigido). Cobrem: criação limpa 2x e reaplicação; migração do rascunho (dados preservados, esquema e regras idênticos a banco novo); João grava `logistica`/`viabilidade`/`ganho` com `service_role`, `anon` lê e não grava; gravar esses jsonb não altera `tentativa_pesquisa`, `status_pesquisa` nem heartbeat, a tentativa da B segue válida e a finalização da B não apaga os resultados da C; reaplicar sobre banco sem `ganho` recria a coluna; RLS, Realtime nas duas tabelas, corrida controlada da troca de tentativa e teste de mutação. `verificar_supabase.sql` rodado em transação read-only: 87 ok / 0 FALTA no banco simulado; num banco sem `ganho` e sem `orcamento_itens` no Realtime acusou as 2 FALTAs.
  - **NÃO testado (antes da aplicação; ver o registro de aplicação acima):** SQL no Supabase real (nenhuma conexão feita por mim); Realtime entregando eventos de verdade; papéis reais (só simulados); avisos do SQL Editor sobre `drop`; as chamadas `supabase.rpc` e a API Python de B/C; Vercel. A primeira aplicação real é a prova.
  - **CONFIRMADO** (pelos requisitos enviados por Enzo/João e por Samuel): nomes e tipos de colunas listados acima; estados do item; fontes obrigatórias em qualquer preço; `ganho`, `logistica` e `viabilidade` em `orcamentos` (pedido por João em `PARA-SAMUEL.md`, que reverte a ideia anterior de "sem colunas"). **PROPOSTA da A, ainda sem aceite de B/C:** protocolo `reservar_pesquisa`/`gravar_resultado_item`/`finalizar_pesquisa`/`renovar_pesquisa` com número de tentativa e prazo de 180 s desde a última atividade; `pesquisa_iniciada_em`/`pesquisa_concluida_em` no lugar dos `iniciado_em`/`concluido_em` que João citou; `lat`/`lon` como `numeric(9,6)` (João pediu double precision; o cliente recebe número igual); complementos em colunas explícitas e `estimativa_consumo` separada de `estimativa`; `classificacao` definido/pendente; validade do cache = `atualizado_em` + 7 dias; `similar` com fonte própria. **Em aberto:** quem faz o seed de `fornecedores` (João oferece `sql/003_seed_fornecedores.sql`); prazo de 180 s × duração máxima real na Vercel; quem preenche `custo_usd`/`tempo_ms`/`trace_url`.

- **Atualização vigente após respostas de B/C** — Enzo é o autor da primeira mensagem e João da segunda, conforme Samuel. Requisitos exatos e divergências salvos em `CONTRATOS-B-C.md`. Etapa 02 reaberta para compatibilizar SQL, funções e testes. A reserva é responsabilidade da B; protocolo de retomada e gravação ainda precisa de acordo. João calcula resultados na hora, exigindo fechar como a tela os obtém. Os registros de conclusão abaixo representam as versões anteriores do SQL.

- **Etapa 03 feita (07/11/2026) — Nova obra e cadastro manual em `frontend/`. Não commitada.** Skill usada: `building-orca-ui` (instruções de `skills/07-orca-ui-fatia-a.md`); lidas a seção 0 deste arquivo e as seções 3 e 4 do plano. **Figma NÃO foi aberto** (a busca devolveu HTTP 403, exige login): o visual segue a direção descrita na skill e no pedido (papel claro, títulos serifados, azul cobalto, divisórias finas, cota tracejada, hachura 45° nas áreas reservadas) e **ainda precisa ser comparado com os quadros do Figma por quem tem acesso**.
  - **Decisões confirmadas (Samuel):** Next.js + TypeScript em `frontend/` (App Router); `orcamento_id` gerado na tela antes do envio (`crypto.randomUUID`); direção visual "caderno de materiais digital".
  - **Arquivos criados (só em `frontend/`; `sql/` e `src/` intactos):** `package.json` (versões fixas: next 15.5.29, react/react-dom 19.1.10, typescript 5.9.3, vitest 5.1.0) e `package-lock.json`, `tsconfig.json`, `next.config.mjs`, `vitest.config.mts`, `.env.example` (sem chaves; só variáveis públicas, ainda não usadas), `.gitignore` (node_modules, .next, .env*), `src/lib/validacao.ts` (CEP, reais, quantidade, unidade, nome, descrição, `gerarUuid` com fallback), `src/lib/lista.ts` (reducer da lista única: adicionar/editar/remover/tocar/revelar_erros/alternar_modo/importar; erros derivados e indexados por ID), `src/components/{Caderno,NovaObra,TabelaMateriais}.tsx`, `src/app/{layout,page}.tsx`, `globals.css`, `icon.svg`, testes `src/lib/{validacao,lista}.test.ts`.
  - **Comportamento implementado:** tela Nova obra (nome, CEP texto de 8 dígitos com zero inicial, orçamento em reais aceitando "20.000,50", "20000,5", "R$ 20.000"; recusa vazio, zero, negativo e texto; validação no envio, com foco no primeiro campo inválido); `orcamento_id` nasce ao iniciar a obra e é mantido ao editar a obra; tabela editável com ID estável por linha (UUID, nunca o índice), adicionar/remover, quantidade com vírgula → número com ponto, unidades m/m2/m3/un/kg/l/cm/mm (aceita "m²"), categoria opcional; abas de modo (manual, CSV, Excel, Revit, PDF) trocam só o painel, a lista é única e preservada; áreas reservadas vazias: avisos E1, complementos E2, "Usar arquivo de exemplo" (desabilitado) e "Enviar para a IA" (desabilitado com lista vazia ou erro estrutural, com motivo em texto e atalho "Ir para o primeiro erro"); estados vazio, edição e erro; responsivo (grade no desktop, cartões no celular). Não há importação, sugestões nem envio.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **40 testes OK** (validação e lista, incluindo exclusão de linha com erro sem alterar os erros das outras e preservação ao alternar modo); `npm run build` OK. **No Chrome real (playwright-core, fora do projeto, servidor `next start`)**: caminho feliz; orçamento vazio/0/negativo/texto/"1,2,3" recusados com mensagem e foco; CEP curto recusado e CEP com zero inicial mantido; quantidade vazia/0/negativa/texto com erro no campo e envio bloqueado; exclusão de linha sem erro e de linha com erro, com os erros das demais linhas intactos; UUID mantido ao editar a obra; celular de 390 px sem rolagem horizontal; sem erros de console. Rodou 3 vezes seguidas, tudo OK. O script de navegador não está no repositório (ficou no scratchpad).
  - **Defeito achado e corrigido na verificação:** erro exibido ao sair do campo deslocava o layout entre pressionar e soltar o mouse e o clique no botão se perdia. Agora a Nova obra valida só no envio e cada linha da tabela reserva uma linha de espaço para as mensagens.
  - **NÃO testado / não feito:** comparação com o Figma; leitor de tela e navegação só por teclado (rótulos, `aria-invalid`, `aria-describedby` e foco foram implementados, mas não conferidos com leitor); Safari, Firefox e celular físico; rascunho não persiste ao recarregar a página (recarregar perde a obra, a lista e o UUID); confirmação "acrescentar ou substituir" da skill fica para os importadores (o reducer já tem `importar` com os dois modos); deploy na Vercel; o script `python -m scripts.check_setup` segue sem rodar (Python do Windows).
  - **PROPOSTAS da A (não confirmadas):** quantidade "1.234" (ponto com três dígitos, sem vírgula) é recusada como ambígua e orçamento "20.000" é lido como vinte mil; quantidade com no máximo 3 casas e orçamento com 2; nome da obra até 120 caracteres e descrição até 300; unidade vazia é erro (não há padrão); linha com todos os campos vazios também bloqueia o envio.
  - **Bloqueios:** nenhum para a etapa 04. Pendências abertas herdadas: como a tela obtém frete/viabilidade/ganho/Excel da C; Supabase real ainda sem as tabelas.
- **Etapa 02 reaberta e refeita para o contrato de B/C (07/11/2026) — SQL pronto para conferência, NÃO aplicado no Supabase.** Skill usada: `managing-orcamento-data` (carregada via Skill; instruções de `skills/05-orcamento-data.md`). Arquivos: `sql/002_orcamentos.sql` (reescrito), `scripts/testar_sql_orcamentos.sh` (reescrito), `scripts/fixtures/002_rascunho_anterior.sql` (cópia do rascunho antigo, só para testar a migração). **Evidência de aplicação anterior:** consulta de leitura ao Supabase real devolveu `PGRST205` nas 4 tabelas, ou seja, o rascunho nunca foi aplicado lá; a migração cobre bancos locais que o tenham recebido.
  - **Regras aplicadas (da skill):** nomes/tipos/defaults de `CONTRATOS-B-C.md` (`produto_normalizado`, `imagem_url`, `unidade_preco`, `motivo`, `iteracoes`, `preco_emb_*` numeric(12,2), `preco_un_*` numeric(12,4), `preco_data` timestamptz, `atualizado_em` por trigger, `status_pesquisa` pendente/pesquisando/concluida/falhou, `pesquisa_erro`, cache com `imagem_url`/`atualizado_em`, fornecedores com `rs_por_km`, `lat`, `lon`, obrigatórios NOT NULL); qualquer um dos seis preços exige `fontes` válidas (loja, dominio normalizado, url http(s), preco_embalagem, embalagem texto opcional), inclusive com `estimativa=true`, também no `similar` e no cache; `classificacao` separada de `status`; `orcamento_cliente` em reais e CEP texto preservados; protocolo único `reservar_pesquisa` → `gravar_resultado_item` → `finalizar_pesquisa` (+ `renovar_pesquisa`), com número de tentativa e bloqueio `FOR NO KEY UPDATE` da linha do orçamento antes de conferir a tentativa e gravar (ordem de bloqueio: orcamentos → itens); `pesquisa_heartbeat_em` renova o prazo (180 s só libera execução parada, a segurança é o número da tentativa).
  - **Testes executados (Postgres 16 descartável, Docker): 251 verificações OK em duas execuções seguidas.** Criação limpa 2x; colunas do contrato; criação, reenvio, conflito, falha parcial; 12 criações simultâneas e 8 com conteúdo diferente; seis preços isolados sem fonte, com estimativa e com fonte inválida; escrita exata de B (todos os campos) e de C (exemplo de porcelanato do João, fornecedores com os nomes dele); protocolo: 12 reservas simultâneas, execução lenta, retomada, reabrir; **troca de tentativa durante a gravação com intercalamento controlado** (reserva segura a linha em transação aberta e a gravação/finalização da tentativa velha espera e é recusada) e **teste de mutação** (sem o `FOR NO KEY UPDATE` a gravação velha passa, e o teste pega); permissões com papéis simulados do Supabase; migração do rascunho (dados e tipos preservados, esquema e regras idênticos aos de um banco novo, falha segura com fornecedor sem CEP). O teste de migração achou um defeito real (`finalizar_pesquisa` com parâmetro renomeado) já corrigido.
  - **NÃO testado:** SQL no Supabase real; Realtime entregando eventos; papéis reais (só simulados); a API Python e as chamadas `supabase.rpc` de B/C (código deles); Vercel.
  - **PROPOSTAS da A a revisar por B/C (não confirmadas):** (B) `reservar_pesquisa(id, expira_s=180, reabrir=false)` devolve `{reservado, tentativa, status_pesquisa}` e B usa as funções em vez de UPDATE direto; prazo contado desde a última atividade, não de `pesquisa_iniciada_em`; `reabrir=true` para `repesquisar_item`; B não escreve `classificacao` (é da A); `iteracoes` gravado como valor; validade do cache = `atualizado_em` + 7 dias; resultado do cache usa as mesmas chaves de preço e `fontes` do item; `resposta` do arquiteto fica em coluna do item (escrita pela A); domínio das fontes normalizado dentro de `gravar_resultado_item`. (C) `pesquisa_concluida_em` como "concluído em"; complementos em colunas explícitas (`sugerido`, `sugestao_regra`, `sugestao_motivo`, `origem_linhas int[]` com os números de `linha`, `aceito`) e `estimativa_consumo` separada de `estimativa`; `linha` obrigatória (A numera listas digitadas); `"similar"` jsonb exige `descricao` e, com preço, fonte própria (nome entre aspas no SQL por ser palavra reservada); `logistica`/`viabilidade` mantidas como jsonb opcionais, pois João calcula na hora; domínio de `fornecedores` normalizado por trigger. (Ambos) `classificacao` passa a `definido`/`pendente` (antes `definido`/`generico`).
  - **Decisões em aberto para a revisão posterior:** como a tela obtém frete, viabilidade, ganho e Excel calculados por João na hora (função/rota e sinal de "pronto"); duração máxima efetiva da função na Vercel × prazo de 180 s; se `custo_usd`/`trace_url`/`tempo_ms` ficam em `orcamentos` (B grava ao finalizar); leitura pública `anon` com `using (true)` segue só para a demo sintética.
- **Etapa 01 concluída (leitura e planejamento, sem código).** Verificado no checkout: só existem `src/` (main, agent, tools, database, config), `sql/001_agent_runs.sql`, `prompts/`, `skills/01–03`, `scripts/`. NÃO existem `frontend/`, `tests/`, `docs/arquivos-teste/`, `contrato.py`, `skills/07-orca-ui-fatia-a.md` nem as 4 tabelas. `src/main.py` só tem `/health` e `/agent/run`. Python do Windows não roda (alias da Microsoft Store). **Propostas (não confirmadas):** UUID gerado pelo cliente como `orcamento_id` e chave de reenvio; hash do conteúdo para detectar conflito (409); coluna `classificacao` separada de `status`; estados gerais `recebido|pesquisando|concluido|erro`; sugestão com `id`, `revisao_id`, `linhas`, `acao`, `campos`. Pendências com Enzo/João: ver resposta da etapa 01. Próxima tarefa: etapa 02 (SQL único).
- **Etapa 02 concluída (SQL único), 07/11/2026.** Decisões confirmadas por Samuel: Next.js + TypeScript em `frontend/`; UUID gerado pela tela como `orcamento_id` (mesmo UUID em reenvio; mesmo conteúdo recupera, conteúdo diferente dá conflito). Criados: `sql/002_orcamentos.sql` (4 tabelas, `criar_orcamento()` transacional, `iniciar_pesquisa()` com trava, RLS, Realtime) e `scripts/testar_sql_orcamentos.sh`. **Testado de verdade** em Postgres 16 descartável (Docker): 47 verificações OK, duas execuções seguidas — criação idempotente, gravação, falha parcial desfeita, reenvio, conflito, 12 chamadas simultâneas (1 cria, 11 recuperam; 8 com conteúdo diferente: 1 cria, 7 conflitos), trava da pesquisa (só 1 vence), restrições, cascata, RLS e Realtime com papéis simulados do Supabase. **Revisão da etapa 02 (mesmo dia):** (1) regra de fontes corrigida: qualquer `preco_emb_min/med/max` exige `fontes` válidas (`fontes_validas()`: loja, dominio, url http(s), preco_embalagem >= 0), inclusive com `estimativa=true`; a B grava tudo num UPDATE via `gravar_resultado_item()`. (2) retomada corrigida: `iniciar_pesquisa()` devolve o número da tentativa (ou NULL), prazo de 180 s sem atividade só serve para retomar execução morta; `gravar_resultado_item`, `renovar_pesquisa` e `finalizar_pesquisa` recusam (retornam false) tentativa velha, então execução lenta não sobrescreve a nova. Testes: 93 verificações OK em duas execuções seguidas (cada campo de preço isolado, estimativa sem fonte, fontes inválidas, execução lenta, corrida de 8 gravações velhas contra 1 nova, 12 pedidos simultâneos antes e depois do prazo). **NÃO testado:** o SQL no Supabase real (não foi aplicado; falta rodar no SQL Editor), a API Python (inexistente; Python do Windows não roda), o Realtime recebendo eventos de verdade. **Propostas ainda não confirmadas por Enzo/João:** estados gerais `recebido|pesquisando|concluido|erro`; `embalagem` como texto; `logistica`/`viabilidade` como jsonb em `orcamentos`; funções da B `gravar_resultado_item`/`finalizar_pesquisa` com número da tentativa (B precisa chamá-las em vez de UPDATE direto); regra "todo preço exige fonte" mesmo em estimativa; `unidade` livre no banco (API valida a lista). Limitação: leitura pública `using (true)` — qualquer um com a chave anon lista todos os orçamentos; ok só para demo sintética.
- Concluído neste chat — cópia da divisão do time e atualização do contexto, do plano por ferramenta e dos 14 prompts.
- Verificação local — implementação da Fatia A pendente. `tests/importacao/contrato.py`, amostras e `skills/07-orca-ui-fatia-a.md` ainda precisam estar disponíveis neste checkout.
- Última verificação de ambiente — `python -m scripts.check_setup` falhou ao iniciar `WindowsApps/python.exe`. Resolver o interpretador para os testes da aplicação.
- Em aberto — framework/local do frontend, formatos Excel, campos finais do SQL e do contrato, nomes dos três exemplos, identificação antecipada do orçamento e tempo efetivo do fluxo na Vercel.
- Prazo de Samuel até a noite de 07/11. Marcos do time — integração às 14h, E1–E7 demonstráveis às 17h, E8–E11 à noite, congelamento domingo às 10h30 e submissão até 12h30.
- Próximo passo (atualizado após a etapa 03) — Samuel confere a tela e o Figma; depois etapa 04 (CSV e três arquivos de exemplo), que alimenta a mesma lista de `frontend/src/lib/lista.ts`. Em paralelo, o SQL abaixo segue aguardando B/C.
- Próximo passo (SQL) — Samuel encaminha `sql/002_orcamentos.sql` a Enzo e João para conferir com o código deles (lista de propostas acima). Só depois de B/C aceitarem (ou ajustarem), aplicar no Supabase pelo SQL Editor e então seguir para a etapa 03 (Nova obra e cadastro manual, em `frontend/`).

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
1. Informa nome, CEP e orçamento do cliente e importa arquivo, usa exemplo ou digita os materiais
2. Na tabela editável, confere os erros E1 e aceita correções e complementos E2
3. Clica em "Enviar para a IA"
4. Os itens vão aparecendo na tela AO VIVO, um a um, com preço e imagem
5. Recebe preços com fontes, perguntas, plano de compra, frete, viabilidade e exportação
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
| Demo | Roteiro atualizado de aproximadamente 75 s dentro do pitch de 3 min, com exemplos, revisão, pesquisa, pergunta, Langfuse e resultado |

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

## 4. Contrato de dados — validar A, B e C

### Entrada: `POST /orcamentos`
O site manda os itens **já revisados pelo arquiteto**:
```json
{
  "obra": { "nome": "Reforma Apto Boa Viagem", "cep": "51020-000", "orcamento_cliente": 20000.00 },
  "origem": { "arquivo": "lista.xlsx", "formato": "xlsx", "software": "revit" },
  "itens": [
    { "linha": 5, "categoria": "Pintura", "descricao": "Tinta acrílica Suvinil Toque de Seda Branco Neve",
      "quantidade": 180, "unidade": "m2", "nivel": "Térreo", "extras": {} }
  ]
}
```
A API grava os itens em `buscando`, chama `pesquisar_orcamento(id)` da B e aguarda a execução na mesma requisição. A resposta inclui `orcamento_id` e o estado acordado após o retorno. `orcamento_cliente` é nome de campo proposto para o valor em reais exigido na nova divisão; confirmar em `tests/importacao/contrato.py`. O acompanhamento durante a requisição depende da identificação antecipada do ID e do hook Realtime.

**Regras do formato:**
- `quantidade` é sempre número com ponto decimal (`12.5`), nunca texto.
- Unidades escritas sempre do mesmo jeito: `m`, `m2`, `m3`, `un`, `kg`, `l`, `cm`, `mm`.
- Colunas desconhecidas vão para `extras`, para nada se perder.
- O plano prevê um modelo em Python em `tests/importacao/contrato.py`. A pasta ainda será criada e commitada.

### Tabelas no Supabase

Samuel consolida o SQL único das quatro tabelas, incorporando os campos pedidos por Enzo e João. O esquema abaixo resume responsabilidades e ainda depende do contrato executável.
| Tabela | Para quê | Campos principais |
|---|---|---|
| `orcamentos` | Um por envio, acompanhado por Realtime | id, estado geral a fechar, nome, cep, orçamento do cliente, totais, logística, viabilidade, tempo e custo |
| `orcamento_itens` | Um por item, acompanhado por Realtime | orcamento_id, descrição original, classificação inicial, produto normalizado, marca, status (`buscando`/`definido`/`pendente_especificacao`/`nao_encontrado`/`erro`), pergunta, quantidade, unidade, embalagem, qtd_embalagens, preco_emb_min/med/max, confianca, estimativa, fontes (loja, dominio, url, preco_embalagem), imagem |
| `fornecedores` | Esquema pela A e cadastro pela C | nome, dominio, site, CEP, coordenadas, frete base, frete por km, pedido mínimo |
| `cache_precos` | Não pesquisar o mesmo produto duas vezes | chave do produto, resultado, validade |

### Saída de logística
```json
{ "estrategia": "loja_unica | dividir", "lojas": ["..."], "frete_total": 180.0, "economia_estimada": 95.0 }
```

### Perguntas em aberto para o Samuel
1. Qual framework e em qual pasta ou repositório vai ficar o site?
2. Quais variantes de Excel e layouts de PDF com texto estão nas amostras?
3. Falta algum campo no contrato para a tela?
4. Quais três obras serão usadas no botão de exemplo e qual delas demonstra dois erros e complementos na demo?

---

## 5. O que já está pronto

### Repositório (GitHub, privado)
```
src/            → backend FastAPI + agente (agent.py, tools.py, database.py, config.py, main.py)
prompts/        → prompt do agente
skills/         → guias para Claude Code / Codex / ChatGPT (ReAct, Featherless, Langfuse)
docs/briefing/  → 3 PDFs: oportunidades, dossiê técnico, plano de ação
scripts/check_setup.py → testa todas as conexões num comando
```

### Arquivos de teste planejados

As pastas `tests/importacao/` (100 casos previstos) e `docs/arquivos-teste/` (acervo previsto de 183 arquivos) ainda serão criadas e commitadas. As características abaixo descrevem o acervo planejado.
- **12 obras fictícias** em Recife e região (apartamento, casa, cozinha, banheiro, loja, escritório, clínica, restaurante, piscina, fachada, studio, casa de praia), com **endereços e CEPs reais**
- **15 formatos**:
  - Revit `.txt`, orçamento `.xlsx`, lista `.csv`, lista de WhatsApp `.txt`
  - SketchUp `.csv`/`.html`, memorial `.docx`, pedido de cotação e prancha em `.pdf`
  - foto de lista escrita à mão `.jpg`/`.png`
  - `.xls`, `.ods`, `.json`, `.xml`, `.tsv`, `.md`
- **Cerca de 116 produtos de marcas reais** (Suvinil, Coral, Portobello, Deca, Docol, Tigre, Quartzolit, Knauf, Blum, Gerdau…) escritos de 3 jeitos: completo, abreviado e **genérico** (que deve virar *Pendente de Especificação*)
- **Arquivos com problema de propósito:** corrompido, vazio, colunas trocadas, PDF escaneado, duplicados, acentos quebrados, fórmulas com `#REF!` etc.
- Índice previsto em `docs/arquivos-teste/LEIAME.md`.

### Armadilhas já descobertas (vale ler antes de codar)
- **O PapaParse pode confundir a vírgula decimal com o separador.** Use tabulação para o TXT tabulado do Revit e confira a amostra do time.
- **CSV salvo pelo Excel pode usar Windows-1252.** Teste também UTF-8 para preservar os acentos nas duas codificações.
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
| 10h | Fechar contratos entre A/B/C e o SQL único da A | Cada fatia testa sua entrada |
| 10h–12h | Leitura dos arquivos + tabela editável no site · ligar Tavily/DuckDuckGo · tabelas no Supabase | |
| 12h–14h | Agente buscando preço de ponta a ponta + Realtime atualizando a tela | **14h: caminho feliz rodando** |
| 14h–16h | "Pendente de Especificação" + logística por CEP | |
| 16h–17h | Integrar revisão, exemplos, compra, pesquisa e frete | **17h — E1–E7 demonstráveis** |
| Noite | E8–E11 · domínio + e-mail (AWS) · slides · métricas · publicação | **link público estável** |

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
| 0:45–2:00 | **Demo de aproximadamente 75 s** — exemplo, dois erros, aceite de correções e complementos, pesquisa, pergunta, Langfuse, viabilidade e exportação. |
| 2:00–2:35 | Negócio: quem paga, preço, mercado, por que agora |
| 2:35–3:00 | Ganho × custo por orçamento, e próximo passo |

---

## 8. Regras de ouro
- **Código do produto só a partir de sábado, 10h.** Commits pequenos e frequentes durante o evento.
- Nada de chaves no GitHub.
- Usar só dados fictícios.
- Se der dúvida sobre alguma regra, perguntar no grupo oficial do WhatsApp.
