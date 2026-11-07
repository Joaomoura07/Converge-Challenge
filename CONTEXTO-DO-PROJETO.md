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

- **Etapa 14 PARCIAL (07/11/2026) — demo e entrega: preparada, NÃO validada no link final. Não commitada.** Skills: `building-orca-ui` (jornada) e `tracing-with-langfuse` (só leitura do plano; nenhum trace foi aberto). Plano da etapa 14, `docs/FALTA-ENZO.md` e `docs/SUBMISSAO-FATIA-B.md` lidos.
  - **O que foi feito:** `docs/ENTREGA-FATIA-A.md` (o que está provado e com qual evidência; como publicar o site e fechar a validação em 10 minutos; roteiro da demo; matriz de aceitação do plano × evidência; pendências por função E1 a E11 com responsável; quem faz o quê até a submissão) e `scripts/ensaio_link_final.mjs` (Node, sem dependências: confere as rotas da API, as páginas do site e a RLS com a chave anon; com `--enviar` faz UM orçamento real, mede a duração e confere o resultado pela chave anon; nunca usa a chave de serviço).
  - **Medido com o código real sobre os três exemplos do botão (revisor E1 e complementos E2 da C):** exemplo 1 Apartamento Boa Viagem = **2 erros** (linha 9 cimento em m2 e linha 18 nivelador em m2, ambos propõem `un`) e 3 complementos, **é o exemplo da demo ("dois erros sinalizados")**; exemplo 2 Casa térrea = 4 erros (`sc` e `br`) mais o `9.500` ambíguo que bloqueia o envio; exemplo 3 Escritório = 0 erros e 0 complementos. O `lista_materiais_INCOMPLETA.csv` dá 10 erros (não serve para "dois").
  - **Executado de verdade:** o ensaio SOMENTE-LEITURA contra a API publicada `https://converge-challenge.vercel.app`: 8 verificações ok (`/health` com LLM, Supabase e Langfuse ligados; todas as rotas no `/openapi.json`; `POST /orcamentos` com corpo vazio devolve 422 sem gravar). Todos os testes das etapas anteriores foram repetidos depois do merge com o Enzo: backend 651 ok, frontend 374 ok.
  - **BLOQUEIOS (por que não se pode dizer "validado no link final"):** (1) **o site não está publicado**: `converge-challenge.vercel.app` devolve 404 em `/`, `/nova` e `/obra/...` (só tem a API); falta o segundo projeto da Vercel com Root Directory `frontend` e as variáveis `NEXT_PUBLIC_*` (passo a passo na seção 2.1 do documento); (2) **o envio de um orçamento real à produção NÃO foi feito**: a tentativa de rodar o exemplo pela API publicada foi negada pelo classificador de permissões da ferramenta (grava no Supabase real e gasta LLM e Tavily); não foi contornada; quem tem a autorização roda o comando do documento; (3) **RLS real não verificada por mim**: o `.env` do repositório não tem a chave anon (só a de serviço, que ignora a RLS); a RLS foi provada no Postgres local com papéis simulados e Samuel aplicou e verificou o SQL no Supabase (resumo 91 ok / 0 FALTA, informado por ele); o ensaio com `--anon-key` fecha isso; (4) **duração da função da Vercel**: não há `vercel.json` no repositório, o valor vem do painel; a evidência é indireta (Enzo relata 16 itens em 49 s pelo site e o código da B assume 300 s); a medida direta sai do ensaio com `--enviar`.
  - **Pendências E1 a E11 para os responsáveis:** E1 listas de marcas curtas (A); E2 unificar a rota se o João topar (C); E4 cota do Tavily no domingo às 8h (B); E7 frete em pausa, exibido como "frete a confirmar" (C); E9 reaquecer o cache dos 3 exemplos se vencer em 7 dias (B); E11 download do Excel pelo navegador no link final (C); E3, E5, E6, E8, E10 sem pendência própria além de repetir no link final. Lista completa e prazos na seção 5 e 6 do documento.
  - **Próximo passo:** Samuel (ou quem tem a Vercel) publica o site, confere a duração da função (≥ 60 s) e roda `node scripts/ensaio_link_final.mjs --api ... --site ... --supabase-url ... --anon-key ... --enviar`; cola a saída no grupo; depois, teste como jurado (aba anônima e celular) e o vídeo.

- **Etapa 13 feita (07/11/2026) — bateria e regressões. Não commitada.** Skills: `managing-orcamento-data` e `importing-materials` (regras já carregadas), mais as áreas tocadas (backend da A e tela de importação). Plano da etapa 13 lido.
  - **Bateria rodada (resultados reais, repetidos depois das correções):** (1) **os 100 casos do acervo pelo executor OFICIAL** `tests/importacao/run-front.mjs`, com o leitor real da tela empacotado como módulo `importar({nome, bytes})` (rolldown): **102 ok, 0 falhas**, 7 pulados (os de API, que o pytest cobre), 2 manuais; com as fixtures pesadas geradas por `gerar_fixtures.py --grandes` (TC-084 de 50 mil linhas e TC-085 de 25 MB também passam; as fixtures pesadas e os arquivos regenerados foram descartados depois, o repositório ficou como estava); o autoteste do executor também deu 100 ok. (2) `pytest tests/importacao`: 213 ok, 12 pulados (casos de API que apontam para uma rota `/importacao` que não existe: ver abaixo). (3) `pytest tests` na imagem Docker: **652 ok**, 14 pulados, 16 desselecionados. (4) Frontend: `typecheck` sem erros, **374 testes OK**, `build` OK. (5) SQL no Postgres 16 descartável: **275 verificações OK, 0 falhas** (`scripts/testar_sql_orcamentos.sh`). (6) `python -m scripts.check_setup` com as chaves reais do `.env`: tudo OK (GLM-5.2 'pong' e tool calling, Featherless chave 1/1, Langfuse, Supabase com a tabela agent_runs, Tavily 3/3, DuckDuckGo); custo ≈ US$ 0,0009 de LLM e 3 créditos do Tavily. (7) Sonda somente-leitura no deploy da Vercel: `/health` ok e `/openapi.json` já lista TODAS as rotas (`/orcamentos`, `/revisao/erros`, `/revisao/sugestoes`, `/revisao/sugestoes/completo`, `/orcamentos/{id}/resultado`, `/orcamentos/{id}/exportar.xlsx`, `/orcamento-itens/{id}/repesquisar`, `/agent/run`); `POST /orcamentos` com quantidade em texto e com corpo vazio devolveu 422, sem gravar nada. Ou seja, o deploy que o João dizia desatualizado já tem as rotas.
  - **Regressões acrescentadas (`tests/test_regressoes_a.py`, 37 testes):** os apelidos de unidade do front (`csv.ts`) e do servidor (`revisao.py`) são idênticos (antes, nada impedia os dois de divergirem); a classificação da A é entendida pela B (`definido`/`pendente` → vocabulário da B) e o servidor ignora a do cliente; números brasileiros do revisor; os casos de API 094 a 099 do acervo mapeados para o `POST /orcamentos`; limite de itens igual no front e no servidor. Já existiam e foram rodados: E1 (71 em `tests/revisao`), aceite e decisões (frontend), Realtime (controlador e armazém), reenvio (envio e fluxo A→B→C).
  - **Falhas e decisões da bateria (corrigidas):** (a) `origem` do `POST /orcamentos` era opcional; o contrato (TC-095-b) a exige: agora é obrigatória (422 sem ela). (b) Corpo gigante: o TC-098-b (um milhão de itens, 135 MB) não tinha defesa nenhuma na API; novo `src/limite_corpo.py` recusa com 413 antes de ler (pelo `Content-Length` ou, sem ele, ao passar de 8 MB), só nas rotas de listas (`/orcamentos`, `/revisao`), com CORS acompanhando; o arquivo real devolveu 413 em 0,02 s. O FastAPI engolia a exceção da leitura e respondia 400; o middleware agora troca por 413 (teste cobre). (c) O leitor aceita até 100 mil itens (TC-084), mas o servidor só 5.000 por envio: um CSV de 50 mil linhas importaria e o envio falharia; a tela agora recusa importar acima de 5.000 itens (mensagem e lista mantida) e bloqueia o envio acima disso (`LIMITE_ITENS_ORCAMENTO`, igual ao do servidor, com teste de paridade).
  - **Desvios do plano a decidir (PROPOSTAS):** TC-097 (lista vazia) pede 200 "sem dados"; na API de envio lista vazia é 422 (o importador já devolve o aviso `SEM_DADOS`). Os 12 testes de API do acervo (`IMPORTACAO_URL`) esperam uma rota `/importacao` que não existe (o fluxo é leitura no navegador mais `POST /orcamentos`); foram cobertos pelos equivalentes acima, não pela rota.
  - **NÃO testado / bloqueios:** um caminho feliz REAL (POST com pesquisa de verdade) grava no Supabase real e gasta LLM e Tavily; não foi feito sem o seu OK. O caminho feliz e as exceções rodaram em memória (etapa 12) e a conectividade foi conferida pelo `check_setup`. Realtime real do Supabase, `BancoSupabase` da B contra o banco real, frete ligado, Safari e Firefox, leitor de tela e teclado completos, desempenho de 5.000 linhas renderizadas na tela, TC-087 e TC-090 (manuais, dependem do Langfuse e do agente) e uma exportação real do Revit e do SketchUp continuam abertos. `npm audit`: 2 achados no `postcss` via Next, anteriores às etapas, sem correção sem trocar de versão do Next.

- **Etapa 12 feita (07/11/2026) — encaixe dos componentes da B e da C verificado ponta a ponta. Não commitada.** Skills: `building-orca-ui` e `managing-orcamento-data` (regras já carregadas). Antes de começar, `git pull`: o João já tinha enviado os componentes dele (`frontend/src/components/resultado/`, a tela `/estimativa/[id]` e um `EncaixeResultado` novo em `/obra/[id]`, com subtotal, "cabe ou não", ganho e atalho para a estimativa completa) e o Enzo já tinha o `ResultadoItens`/`ItemRow`; a página `/obra/[id]` já os encaixava. Esta etapa não reescreveu nada deles: provou que o encaixe funciona.
  - **Arquivos:** `tests/test_fluxo_a_b_c.py` (12 testes), `frontend/src/lib/orcamento/fixtures/fluxo-a-b-c.json` (as linhas exatas que o banco guarda depois de A, B e C rodarem; regerada com `ATUALIZAR_FIXTURE_FLUXO=1`; sem a variável o teste só confere que o arquivo continua igual ao fluxo) e `frontend/src/lib/orcamento/fluxo.test.ts` (10 testes). Nenhum arquivo de produção foi alterado.
  - **O que o teste de backend roda de verdade:** a rota `POST /orcamentos` da A, `pesquisar_orcamento` e `repesquisar_item` da B (incluindo o gancho de fim), e `resultado` e `exportar` da C (que leem e gravam pelo mesmo banco). **Simulados:** o banco (um Supabase em memória que as três fatias compartilham; a função SQL `criar_orcamento` e o adaptador `BancoSupabase` da B têm equivalentes em memória) e a pesquisa de preços na internet (tabela de preços sintéticos).
  - **Quem chama quem (provado pela ordem registrada):** A grava e chama a B na mesma requisição; a B reserva, grava cada item, conclui e SÓ DEPOIS chama a C; a rota da A não contém lógica de logística, viabilidade, ganho, Excel nem preço (teste sobre o código-fonte). Responder à pergunta do arquiteto chama a B (`repesquisar_item`), que marca, pesquisa e grava, e depois a C recalcula (total sobe R$ 289,90 e um item sai de "sem preço"). Reenvio do mesmo pedido: a reserva da B nega e nem a pesquisa nem a C repetem. Conteúdo diferente com o mesmo código: 409, sem B nem C. **Teste de mutação:** com o gancho `GANCHOS_FIM` vazio, 6 testes quebram.
  - **Dados do exemplo sintético (Apto Boa Viagem):** 4 itens mais 1 complemento aceito (argamassa) e 1 recusado (rejunte, que nem vira linha). Preços com fonte (Leroy Merlin e C&C), 1 pendente com pergunta, 1 não encontrado com motivo. Total estimado R$ 1.777,30 = tinta 911,80 + massa 295,50 + argamassa do complemento 570,00; viabilidade `completo: false` com 2 itens sem preço; logística com frete R$ 0 (em pausa); as posições de `logistica.lojas[].itens` apontam para a lista ordenada por `linha` (a ordem do `useOrcamento`).
  - **Resultados reais:** backend **611 testes OK** (18 ignorados, 16 desselecionados, imagem Docker `hackathon-api`); frontend `typecheck` sem erros, **374 testes OK**, `build` OK. O teste do frontend carrega a fixture pelo `useOrcamento` e confere que o subtotal da tela é o `total_med` que o servidor gravou, que o que fica fora do subtotal é o que o servidor chama de sem preço, que o veredito não afirma "cabe" com `completo: false`, que o complemento sem aceite não conta e que o Realtime que traz o item respondido recalcula o subtotal. **No navegador** (`/obra/[id]` com um PostgREST falso servindo a fixture, sem Realtime): a lista da B mostrou os 5 itens com links das fontes, o pendente no fim com "Responder"; o encaixe da C mostrou "Subtotal estimado R$ 1.777,30 · 2 fora do subtotal · Ainda não dá para afirmar" e o link para a estimativa; "Enviar resposta" chamou a rota da B com o texto do arquiteto e o item virou "Definido" (progresso "1 sem preço encontrado"); `/estimativa/[id]` mostrou R$ 1.777,30, 3 precificados e 2 pendentes, as linhas com preço e o botão "Baixar plano em Excel" apontando para `<API>/orcamentos/<id>/exportar.xlsx`.
  - **Achado:** a fixture inicial mostrava "undefined itens na lista" na estimativa porque o banco de mentira não gravava `qtd_itens` (o SQL real grava). Corrigido no teste (o fake agora imita o `criar_orcamento`), não na tela.
  - **NÃO testado:** nada disso contra o Supabase real, o Realtime real, a API na Vercel nem a pesquisa real do Enzo (o adaptador `BancoSupabase` da B continua sem teste com o banco real neste fluxo, e ele reserva e grava com UPDATE direto, sem as funções de reserva do SQL); o download real do Excel pelo navegador (só o link e o conteúdo gerado em teste); frete ligado (`FRETE_ATIVO`) e a tabela `fornecedores`; os componentes finais em celular e teclado.
  - **Em aberto fora desta etapa:** deploy da Vercel desatualizado (segundo o João); etapas 13 (bateria e regressões) e 14 (demo e entrega); a pasta `research_notes/Grupos de WhatsApp de arquitetura/` apareceu sem commit e não é desta sessão.

- **Etapa 11 feita (07/11/2026) — leitor de PDF com texto em `frontend/`. Não commitada.** Skill: `importing-materials` (regras já carregadas; plano da etapa 11 e as amostras de PDF do acervo lidos). Dependência: `pdfjs-dist` 6.5.438 (versão fixa); o worker sai do mesmo pacote (o Next o empacota como asset), nunca de CDN com outra versão.
  - **Arquivos:** `frontend/src/lib/importar/pdf.ts` (leitor, recebe o PDF.js por parâmetro), `pdfNavegador.ts` (carrega o PDF.js e o worker sob demanda, só quando alguém envia um PDF), `pdf.test.ts`; `arquivo.ts` (`lerArquivo` agora é assíncrono e despacha `.pdf`), `tipos.ts` (códigos `PDF_SEM_TEXTO`, `EMBALAGEM_COMO_UNIDADE` e `EXTRACAO_AMBIGUA`, formato `pdf`), `Importador.tsx` e `Caderno.tsx` (aba PDF com texto).
  - **Como lê:** o PDF não tem linhas e colunas, só pedaços de texto com posição. As linhas vêm da altura (`y`, tolerância de 3) e as colunas do `x` do cabeçalho. Dois layouts, os das amostras: (1) tabela com cabeçalho, o "Pedido de cotação" (Item, Descrição, Embalagem, Qtd.), com cabeçalho repetido na página 2 e descrição quebrada em duas linhas tratados; as quantidades são de EMBALAGENS, então cada quantidade vira unidades (`un`) da embalagem, que passa para a descrição (ex.: "Selador acrílico (lata 18 L)"), com aviso para conferir; (2) o "Quadro de acabamentos" (Ambiente × Piso/Parede/Teto/Rodapé) com a quantidade dentro da célula ("Portobello cimento 90x90 (24,00 m²)"): vira uma linha por material, com o ambiente, a categoria (a coluna), a quantidade e a unidade; o texto da célula sem quantidade (carimbo da prancha, notas) é ignorado e listado num aviso. Cada aviso por linha cita a página do PDF. Limites: 20 MB e 30 páginas.
  - **Falhas com orientação para CSV, Excel ou cadastro manual:** PDF escaneado (sem texto) `PDF_SEM_TEXTO`; protegido por senha `ARQUIVO_PROTEGIDO`; corrompido ou truncado `ARQUIVO_CORROMPIDO`; arquivo que não é PDF `FORMATO_INVALIDO`; PDF com texto mas sem tabela de materiais `CABECALHO_NAO_ENCONTRADO`. A lista atual nunca é alterada se a leitura falha.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **338 testes OK** (34 novos do PDF): os **12 pedidos de cotação e os 11 quadros de acabamentos** reais de `docs/arquivos-teste` leem sem erro (nos pedidos, a numeração dos itens vai de 1 ao último sem buraco nem duplicata, inclusive a página 2; nenhum acento quebrado), o PDF escaneado (`Digitalização_20261017.pdf`) é reconhecido, o PDF truncado e o arquivo que não é PDF são recusados; `npm run build` OK (o worker foi empacotado). No navegador (`/nova`, aba PDF com texto, PDF.js e worker reais): o pedido da obra 01 leu 47 itens de 2 páginas com os dois avisos; o quadro substituiu a lista por 22 itens, com categoria e unidade certas (m2 e m) e o aviso dos 3 textos do carimbo ignorados; o escaneado e o truncado mostraram a mensagem e mantiveram a lista.
  - **SIMULADOS (não há amostra real):** PDF protegido por senha (stub do PDF.js que lança `PasswordException`); PDF com mais de 30 páginas; PDF com texto sem tabela.
  - **NÃO testado:** PDF com layout diferente dos dois das amostras (outros programas de orçamento, tabelas sem cabeçalho, várias colunas de quantidade); PDF com células mescladas ou rotacionado; OCR (não há: escaneado só recebe orientação); desempenho em PDF grande no celular; Safari e Firefox; teclado e leitor de tela.
  - **PROPOSTAS (sem aceite):** quantidade de embalagem lida como `un` com a embalagem na descrição; no quadro, materiais iguais em ambientes diferentes entram como linhas separadas (o revisor E1 pode propor a mescla); limite de 30 páginas.

- **Etapa 08, lado da tela, feita (07/11/2026) — botão "Enviar para a IA" ligado ao POST /orcamentos. Não commitada.** Skills: `building-orca-ui` e `managing-orcamento-data` (regras já carregadas).
  - **Arquivos:** `frontend/src/lib/envio/{corpo,enviar,armazem,rascunho}.ts` e `envio.test.ts`; `Caderno.tsx` (botão, retomada do rascunho, código novo quando o conteúdo muda); `app/obra/[id]/page.tsx` e `obra.css` (estados do envio).
  - **Fluxo:** o clique monta o corpo (`montarCorpo`, mesmos campos de `src/rotas_orcamentos.py`, quantidade como número, complemento aceito com regra, motivo, linhas de origem e estimativa de consumo), guarda o rascunho na aba (`sessionStorage`), começa o POST (que também pesquisa, pode levar minutos), e VAI NA HORA para `/obra/[id]`, onde o resultado aparece ao vivo. O estado do POST fica num armazém fora dos componentes, então sobrevive à navegação; clique repetido não dispara segundo POST. Na página: "Enviando e pesquisando preços…" enquanto o POST está aberto; 422 diz o campo que o servidor recusou e só oferece "Voltar e corrigir a lista" (restaura obra e lista pelo `?retomar=`); 409 idem; 502 com `recuperavel`, queda de rede e resposta inesperada oferecem "Reenviar o mesmo pedido" (mesmo código e mesmo conteúdo: o servidor recupera sem duplicar); 503 avisa que o servidor não está ligado ao banco. Se o conteúdo mudou depois de um envio com o mesmo código, o próximo envio ganha um código NOVO (senão daria 409).
  - **Resultados reais:** `npm test` 338 OK (20 deles do envio: corpo, cada resposta do servidor, armazém, clique repetido, reenvio, rascunho). O corpo gerado pelo TypeScript foi validado pelo modelo REAL do servidor (`OrcamentoIn`, estrito) e pelo `_item_para_banco` na imagem Docker. No navegador, com um servidor de API FALSO (e Supabase falso): o clique levou a `/obra/<código>` e o corpo recebido tinha os 47 itens do exemplo; 422 mostrou a mensagem e "Voltar e corrigir" devolveu a lista com 47 linhas e o nome da obra; editar uma quantidade para 181 e reenviar gerou código novo e o servidor recebeu 181 (a edição aparece no JSON enviado); 502 mostrou "Reenviar o mesmo pedido", que reenviou com o mesmo código e os mesmos itens (1 POST novo) e mostrou "Enviando…".
  - **NÃO testado:** o POST contra a API REAL na Vercel e contra o Supabase real (os servidores do teste eram falsos); a pesquisa real do Enzo durante o envio; timeout da Vercel numa pesquisa longa e perda de resposta de verdade; o rascunho só vive na aba (recarregar a página perde o estado do envio, mas o orçamento já gravado continua acessível por `/obra/[id]` e o Realtime); teclado e leitor de tela.

- **Etapa 10 feita (07/11/2026) — TXT do Revit em `frontend/`. Não commitada.** Skill: `importing-materials` (regras já carregadas; plano da etapa 10, casos TC-003, 013 e 057 a 066 e as tabelas reais do acervo lidos). Nada de dependência nova (o leitor reaproveita o PapaParse).
  - **Arquivos:** `frontend/src/lib/importar/txt.ts` (novo), `arquivo.ts` (`.txt` agora vai para o leitor do Revit; `.pdf` segue `etapa 11`), `csv.ts` (núcleo: separador forçável, formato `txt`, linhas de grupo, subtotais, total geral, medida imperial, sinônimos do Revit), `Importador.tsx` e `Caderno.tsx` (aba TXT do Revit e textos das abas Excel e Revit), testes `txt.fixtures.test.ts` e `acervo-txt.test.ts`.
  - **Comportamento:** tabulação FORÇADA (a detecção automática erra em "12,50 m²"); codificação UTF-8, UTF-16 com marca ou Windows-1252 como no CSV; título antes do cabeçalho é descartado (um título com só a primeira coluna preenchida não é linha de grupo); linha de uma célula "Nível: Térreo" ou "Ambiente: Banheiros" vira o nível dos itens seguintes (a coluna da própria linha tem prioridade); subtotal com rótulo ("Subtotal") e sem rótulo (só a quantidade preenchida, só em tabela do Revit) é descartado; "Total geral: N" é descartado e conferido com a soma das quantidades lidas (diferença gera `TOTAL_DIVERGENTE` na linha do total); "Família e tipo" com dois-pontos fica inteiro; "Material: Nome" e "Material: Área" mapeiam, o resto vai para `extras` com o texto bruto; medida em pés e polegadas não é convertida (`unidade: "ft-in"`, quantidade vazia, `extras.valor_original`, `UNIDADE_IMPERIAL`); campos entre aspas são aceitos; software `revit` quando o cabeçalho é do Revit; um `.txt` que não é tabela (ex.: lista do WhatsApp) é recusado com orientação e a lista fica como estava.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **284 testes OK** (+67 desta etapa): os 13 casos TC de TXT do acervo (TC-003, 013, 057 a 066, com TC-066 de 5.000 linhas em menos de 3 s), 5 próprios, e **as 46 tabelas do Revit em .txt de `docs/arquivos-teste`** (nenhuma com erro, acento quebrado, grupo ou total virando item, ou item sem quantidade; nenhum aviso), mais o teste de que os outros .txt do acervo (WhatsApp, briefing) não quebram. Os 68 casos CSV e os 29 de Excel continuam passando depois das mudanças no núcleo. `npm run build` OK. No navegador (`/nova`, aba TXT do Revit, arquivos reais): a tabela elétrica da Casa Térrea (grupos por ambiente com subtotais) leu 9 itens em UTF-8; acrescentar a tabela de pisos (com aspas e m²) levou a lista a 20 itens, o último com 4 m2; o TC-060 divergente mostrou "Linha 6: total informado (12) difere da soma (10)"; a lista do WhatsApp mostrou o erro e manteve a lista.
  - **Efeito colateral das mudanças no núcleo (PROPOSTA):** a coluna `Ambiente` passou a mapear para `nivel` (antes ia para `extras`), porque as tabelas do Revit usam "Ambiente" como grupo. A lista da tela não guarda `nivel` hoje, então nada muda na interface; os testes do CSV e do Excel seguem passando. `Comprimento` e `Length` viram quantidade só quando não existe coluna de quantidade melhor (prioridade menor).
  - **NÃO testado:** uma exportação real do Revit (as amostras do acervo são sintéticas; o próprio acervo manda conseguir uma real e uma do SketchUp antes da demo); Revit em inglês com Level e Count além do TC-063; `.txt` que não seja do Revit mas tenha tabulação; o nível do grupo só aparece depois que a lista guardar `nivel` (hoje o dado é lido e descartado pela tela); teclado e leitor de tela; Safari e Firefox.
  - **Próximo passo:** etapa 11 (PDF com texto) ou ligar o botão "Enviar para a IA" (parte de tela da etapa 08), que ainda impede o fluxo de ponta a ponta.

- **Etapa 09 feita (07/11/2026) — leitor de Excel em `frontend/`. Não commitada.** Skill: `importing-materials` (regras já carregadas; plano da etapa 09, `tests/importacao/README.md` e os casos do bloco H lidos). Dependência: `xlsx` 0.20.3 instalada do CDN oficial (`https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz`, versão fixa), não do npm.
  - **Arquivos:** `frontend/src/lib/importar/excel.ts` (leitor), `arquivo.ts` (despacha pela extensão: .csv, .xlsx/.xls/.xlsm/.ods; .txt e .pdf respondem que chegam nas etapas 10 e 11), `comparar-fixtures.ts` (comparação compartilhada), testes `excel.fixtures.test.ts` e ajuste de `csv.fixtures.test.ts`; `csv.ts` foi refatorado: o núcleo virou `mapearRegistros()`, usado por CSV e Excel (célula pode ser texto, número ou erro; cabeçalho de duas linhas por mesclagem vertical passa a escolher a linha de baixo); `Importador.tsx` e `Caderno.tsx` ganharam a aba Excel e a escolha de aba.
  - **Comportamento:** formatos aceitos .xlsx, .xls e .xlsm (macro nunca é executada); .ods é recusado pela extensão; arquivo de texto com extensão de planilha é lido como CSV com aviso `EXTENSAO_INCORRETA`; binário qualquer dá `FORMATO_INVALIDO`; senha dá `ARQUIVO_PROTEGIDO`; planilha truncada dá `ARQUIVO_CORROMPIDO`; o tamanho descompactado é lido do diretório central do zip, sem descompactar: acima de 128 MB (ou mais de 5000 entradas) dá `ARQUIVO_GRANDE_DEMAIS` (a bomba TC-092 expande para 200 MB); limite de 20 MB e de 2 milhões de células. A primeira aba visível com dados é a padrão; com mais de uma aba visível com dados a tela pede qual importar antes de mexer na lista; abas ocultas são ignoradas. Células mescladas são preenchidas pelo valor de origem; fórmula usa o valor salvo; erro (#DIV/0!, #REF!) e fórmula sem resultado viram `ERRO_FORMULA` com a linha da planilha e quantidade vazia; número vira número bruto (também em `extras`), número escrito como texto passa pelo leitor de números brasileiros; o intervalo declarado não é percorrido (só as células existentes), por isso TC-083 lê 50 linhas rápido. A linha de cada item é a linha da planilha, e os avisos citam essa linha.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **217 testes OK**, dos quais os de importação são 105: 68 do CSV (continuam passando depois da refatoração), 8 dos exemplos e 29 novos do Excel (1 de conferência do acervo, 19 casos TC de planilha: TC-002, 004, 005, 006, 007, 071 a 083 e 092, e 9 próprios de aba oculta e vazia, troca de aba, linha de origem, macro, bomba, 50 linhas e entradas inválidas); `npm run build` OK; `npm audit` não lista `xlsx` (só 2 achados de `postcss` via Next, anteriores a esta etapa). No navegador (`/nova`, aba Excel): TC-071 pede a escolha entre 3 abas (Paredes, Pisos, Esquadrias) sem mexer na lista e importa a aba escolhida; senha, planilha corrompida e .ods mostram a mensagem e mantêm a lista; .xls com a lista cheia pergunta e acrescenta; TC-077 gera avisos `Linha 2` e `Linha 3` com 2 campos vazios marcados e envio bloqueado; celular de 375 px sem rolagem lateral; sem erros de console.
  - **NÃO feito ou NÃO testado:** exemplos em Excel (os 3 exemplos continuam em CSV); planilhas reais do acervo de `docs/arquivos-teste` em .xlsx/.xls (só as fixtures TC-xxx foram rodadas; o acervo tem o orçamento formatado com seções por categoria, o quantitativo por ambiente com aba de resumo e o .xls antigo, que podem exigir ajuste: vale rodar os 3 primeiros); TC-090/091 em Excel; planilha de muitas linhas (só 50 linhas); leitura sem a UI de seleção por teclado e leitor de tela; Safari/Firefox; leitura em Web Worker (a leitura roda na thread principal).
  - **PROPOSTAS (sem aceite):** limite de 128 MB descompactado; recusar .txt e .pdf no despachante até as etapas 10 e 11; aba oculta nunca é a padrão, mas só planilha com dados somente em abas ocultas dá erro pedindo para mostrar a aba.
  - **Próximo passo:** testar as planilhas reais do acervo (orçamento do escritório, quantitativo por ambiente, .xls) e ligar o botão "Enviar para a IA" (etapa 08, lado da tela).

- **Etapa 07 feita (07/11/2026) — esqueleto do resultado e `useOrcamento(id)` em `frontend/`. Não commitada.** Skills: `building-orca-ui` e `managing-orcamento-data` (regras já carregadas na sessão; plano da etapa 07 e PARA-SAMUEL-2.md lidos). Dependência nova: `@supabase/supabase-js` 2.119.0 (versão fixa).
  - **Arquivos:** `frontend/src/lib/supabase.ts` (cliente só com chave anon; null sem `NEXT_PUBLIC_SUPABASE_*`), `frontend/src/lib/orcamento/{tipos,armazem,conexao,controlador,useOrcamento}.ts` e os testes `armazem.test.ts` e `controlador.test.ts`, `frontend/src/app/obra/[id]/{page.tsx,obra.css}`, `frontend/src/components/obra/EncaixeResultado.tsx`, comentário do `.env.example`. Nada de João, Enzo ou das etapas 05/06/08 foi alterado.
  - **Contrato da tela (PROPOSTA a confirmar com João, que ainda não respondeu):** rota `/obra/[id]` (o [id] é o UUID que a tela gerou antes do POST); hook `useOrcamento(id)` em `frontend/src/lib/orcamento/useOrcamento.ts`, devolve `{conexao, carregado, orcamento, itens, erro, recarregar}` (`itens` na ordem de `linha`; `orcamento` null = "aguardando o envio"; `logistica`/`viabilidade`/`ganho` null = "calculando"). Encaixes: o miolo da B é o `ResultadoItens` do Enzo; o da C é `EncaixeResultado`, que João substitui por componentes de `frontend/src/components/resultado/`. Há uma página `/pesquisa` simulada do Enzo, que continua intacta.
  - **Comportamento:** assina as duas tabelas filtradas por orçamento (`orcamento_itens` por `orcamento_id`, `orcamentos` por `id`) e lê depois; em cada `SUBSCRIBED` (inclusive reconexão) lê de novo e reconcilia. Vence a linha com `atualizado_em` mais novo; evento repetido não muda nada; DELETE deixa lápide; evento que chegou durante a leitura é preservado e linha ausente da leitura que nenhum evento tocou é removida; leitura obsoleta é descartada; ao desmontar remove a assinatura e ignora o que estava em voo. Se o Realtime não conectar em 4 s, lê pelo REST e marca "Reconectando…". Estados: sem configuração, conectando, aguardando o envio, erro de leitura com "Tentar de novo", pesquisa que falhou, código inválido.
  - **Resultados reais:** `npm run typecheck` sem erros; `npm test` **188 testes OK** (25 novos desta etapa: 11 do armazém e 14 do controlador, com cliente falso: eventos repetidos, atualização durante a leitura, reconexão, leitura obsoleta, erro e recuperação, limpeza ao desmontar, Realtime que não conecta); `npm run build` OK. No navegador, com um servidor falso que imita o PostgREST (sem Realtime): a página leu um orçamento de 3 itens, mostrou o `ItemRow` do Enzo (definido com cota de preço, pendente com pergunta no fim, buscando), o aviso "ainda não dá para afirmar" do encaixe da C, "Reconectando…" por falta de Realtime, "Aguardando o envio" para um UUID sem orçamento, e "Código de orçamento inválido"; celular de 375 px sem rolagem lateral.
  - **NÃO testado:** Supabase real (nem leitura anon real, nem Realtime real entregando eventos, nem a reconexão de verdade do WebSocket); só o SQL já tinha sido testado com papéis simulados (anon lê, não grava). Os eventos de INSERT/UPDATE/DELETE reais e o filtro `filter` do canal só foram exercitados com o cliente falso. Leitura vazia por RLS não se distingue de orçamento sem itens (o Supabase devolve vazio, sem erro). Teclado e leitor de tela não conferidos. O "Exportar" e os componentes finais da C ainda não existem. O botão "Enviar para a IA" ainda não leva a `/obra/[id]` (parte de tela da etapa 08).
  - **Próximo passo:** ligar "Enviar para a IA" (UUID já existente, navegar para `/obra/[id]`, tratar 409, 422 e 502 do POST) e testar com o Supabase real e a Vercel.

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
