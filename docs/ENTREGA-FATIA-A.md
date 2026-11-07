# Entrega da Fatia A: o que está provado, o que falta e como fechar (etapa 14)

> Escrito em 07/11/2026, ~21h30, depois das etapas 01 a 13. Quem executa cada pendência está na seção 6.
> **Resumo honesto:** o produto da Fatia A está pronto e testado em ambiente controlado. O que NÃO foi feito é a validação
> no **link final**, porque o site ainda não está publicado (só o backend está) e o envio real à produção não foi autorizado
> na sessão. Os comandos para fechar isso em 10 minutos estão na seção 2.

> **Atualização (07/11, depois de Samuel publicar o site em `https://converge-challenge-3k6i.vercel.app`):** o bloqueio 1 caiu.
> Verificado de fora, SEM gravar nada: `ensaio_link_final.mjs --site` deu **12 ok, 0 falhas** (`/`, `/nova` e o exemplo `/exemplos/apto-boa-viagem.csv` respondem 200).
> No navegador, no site publicado: o exemplo "Apartamento Boa Viagem" leu **47 itens em Windows-1252**; o revisor chamou a API publicada e mostrou
> **5 botões "Aceitar" (2 erros E1 + 3 complementos E2, exatamente o medido)**, sem erro de rede nem "indisponível" (logo, CORS e `NEXT_PUBLIC_API_URL` estão certos);
> `/obra/<código inexistente>` mostrou "Aguardando o envio" com a conexão **"Ao vivo"** e sem erros no console: o **Realtime real do Supabase conectou
> com a chave anon e a leitura anon não foi recusada** (evidência real de que as variáveis `NEXT_PUBLIC_SUPABASE_*` estão certas e de que a anon consegue ler as duas tabelas).
> **Continua sem ser provado:** um orçamento real de ponta a ponta pelo site (`--enviar`, grava no Supabase real), a duração da função (≥ 60 s), a recusa de escrita pela anon e o Excel baixado no navegador.

## 1. O que está provado (e como)

| Camada | Evidência real | Onde |
|---|---|---|
| Os 100 casos de importação | 102 ok, 0 falhas pelo executor oficial `run-front.mjs` com o leitor real da tela | `tests/importacao/` |
| Backend (A, B, C) | 651 testes ok, 18 ignorados | `python -m pytest tests` (imagem Docker `hackathon-api`) |
| Frontend | 374 testes ok, `typecheck` e `build` ok | `cd frontend && npm test` |
| SQL das 4 tabelas | 275 verificações ok em Postgres 16 descartável, aplicado e verificado no Supabase real por Samuel | `scripts/testar_sql_orcamentos.sh`, `sql/verificar_supabase.sql` |
| Encaixe A → B → C | `POST /orcamentos` chama a pesquisa da B, que chama a C no fim; ordem provada; com o gancho desligado 6 testes quebram | `tests/test_fluxo_a_b_c.py` |
| Ambiente real | `check_setup`: GLM-5.2 com tool calling, Featherless, Langfuse, Supabase, Tavily 3/3, DuckDuckGo ok | `python -m scripts.check_setup` |
| Backend publicado | `/health` ok (LLM, Supabase, Langfuse ligados); `/openapi.json` lista todas as rotas; `POST /orcamentos` inválido devolve 422 sem gravar | `node scripts/ensaio_link_final.mjs --api https://converge-challenge.vercel.app` |

Tudo que depende de **Supabase real + Realtime real + pesquisa real pelo link** foi simulado nos testes e **não** foi provado em produção
(exceção: o Enzo relata, em `docs/FALTA-ENZO.md`, um orçamento real pelo site: 16 itens em 49 s, US$ 0,0026).

## 2. Como fechar a validação no link final (10 minutos)

### 2.1 Publicar o site (hoje só o backend está publicado)
`https://converge-challenge.vercel.app` responde **404 em `/`, `/nova` e `/obra/...`**: lá só existe a API. O front é um **segundo projeto** na Vercel:

1. Vercel → **Add New → Project** → o mesmo repositório → **Root Directory: `frontend`** (framework Next.js, comandos padrão).
2. **Environment Variables** (sem aspas):
   - `NEXT_PUBLIC_API_URL` = `https://converge-challenge.vercel.app`
   - `NEXT_PUBLIC_SUPABASE_URL` = a URL do projeto Supabase
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = a chave **pública (anon)**. **Nunca** a `service_role`: ela iria para o navegador.
3. Deploy. Anote a URL do site.

### 2.2 Duração da função do backend (meta do time: aguentar ≥ 60 s)
- Não há `vercel.json` no repositório; a duração vem das **configurações do projeto do backend** na Vercel (Settings → Functions → Max Duration).
  O código da B assume 300 s (`TEMPO_MAXIMO_FUNCAO` e janela de 6 min). Confirme que está em **60 s ou mais**; o ideal é 300 s.
- Evidência indireta de que passa de 10 s: o orçamento de 16 itens em 49 s relatado pelo Enzo. Medida direta: o `--enviar` abaixo imprime a duração.

### 2.3 Rodar o ensaio (lê as rotas, o site e a RLS; com `--enviar` faz UM orçamento real)
```bash
node scripts/ensaio_link_final.mjs --api https://converge-challenge.vercel.app --site https://SEU-SITE.vercel.app --supabase-url https://XXXX.supabase.co --anon-key eyJ...
```
Só leitura: confere as rotas, as páginas `/`, `/nova` e o exemplo `/exemplos/apto-boa-viagem.csv`, e a **RLS com a chave anon**
(anon lê `orcamentos` e `orcamento_itens`; não lê `cache_precos` nem `fornecedores`; não grava; não executa as funções do protocolo).
Para o teste de duração e do fluxo real, acrescente `--enviar`: grava um orçamento chamado "TESTE ETAPA 14 (pode apagar)", mede a requisição,
e confere pela chave anon que concluiu, que todo preço tem fonte, que há uma pergunta ao arquiteto e que a C gravou logística, viabilidade e ganho, e baixa o Excel.
Depois, apague essa linha do orçamento no Supabase (a exclusão apaga os itens em cascata).

### 2.4 Teste como jurado (aba anônima e celular)
Siga o roteiro da seção 3 com os **três exemplos**. Faça no celular também: os jurados testam sozinhos entre 13h e 17h.

## 3. Roteiro da demo (~75 s dentro do pitch de 3 min)

Medido com o código real (revisor E1 e complementos E2 da C) sobre os três exemplos do botão:

| Exemplo | Itens | E1 (erros a aceitar) | E2 (itens esquecidos) | Serve para |
|---|---|---|---|---|
| **1. Apartamento Boa Viagem** | 47 | **2** (linha 9: cimento em `m2`; linha 18: nivelador em `m2`; ambos propõem `un`) | 3 | **a demo: "dois erros sinalizados"** |
| 2. Casa térrea Aldeia | 53 | 4 (unidades `sc` e `br`) e um número ambíguo (`9.500`) que bloqueia o envio até corrigir | 4 | mostrar que erro bloqueia e que o aceite corrige |
| 3. Escritório Ilha do Leite | 33 | 0 | 0 | o caminho limpo, sem sugestões |

**Passo a passo (exemplo 1):**
1. **Nova obra:** nome, CEP `51020-000`, orçamento do cliente `20.000,00`. "Iniciar obra".
2. **"Usar arquivo de exemplo" → Apartamento Boa Viagem.** 47 itens entram na tabela editável.
3. **Dois erros sinalizados.** Clique em **Aceitar** em cada um: a unidade muda para `un`. Mostre que só muda depois do clique.
4. **Itens esquecidos.** Aceite um complemento (ele entra na lista como "Sugerido · aceito por você", com "quantidade estimada").
5. **"Enviar para a IA".** A tela vai para `/obra/<código>` e **os itens aparecem ao vivo, um a um**, com preço e fonte.
6. **Pergunta ao arquiteto.** Um item genérico (ex.: "tinta vermelha") pede especificação. Clique **Responder**, escreva uma marca e modelo, e veja o item ser pesquisado de novo.
7. **Resultado.** Subtotal estimado e "cabe ou não" (nunca diz "cabe" com itens sem preço), ganho de tempo ("À mão: ~X h. Aqui: Y s"), **Baixar plano em Excel**.
8. **Langfuse:** abra o trace do orçamento (uma árvore por orçamento, um galho por item).

Riscos já conhecidos (de `docs/FALTA-ENZO.md`): itens fora dos exemplos são pesquisados ao vivo (cerca de 1 em 5 pode ficar sem preço); o cache aquecido cobre só os três exemplos; Leroy Merlin não mostra preço na página lida pela busca.

## 4. Matriz de aceitação do plano (seção 7) × evidência

| Caso | Situação | Evidência |
|---|---|---|
| Revisor E1 propõe, aplicação exige Aceitar, falso positivo preserva o item | Provado | `tests/revisao` (79), testes de decisões, navegador (Casa Térrea) |
| Complemento aceito duas vezes → uma inclusão | Provado | reducer idempotente (testes), duplo clique no navegador |
| Sugestão retorna após edição → resposta antiga descartada | Provado (resposta atrasada **simulada** no navegador) | `revisor.test.ts` |
| Orçamento do cliente em reais chega à C | Provado em memória | `test_fluxo_a_b_c.py` (viabilidade com 4.000) |
| Três exemplos passam pelo mesmo fluxo do upload | Provado (exemplos 1 e 2 no navegador, os três em teste) | `exemplos.test.ts` |
| Realtime durante POST aberto mostra o parcial pelo ID | Provado só **simulado** | `controlador.test.ts`; **Realtime real não testado** |
| Reconexão do hook sem duplicação | Provado só **simulado** | `controlador.test.ts` |
| CSV com 12,50 alterado para 15 chega a 15 | Provado até o JSON enviado | navegador (181 no corpo); banco real não conferido |
| Cadastro manual e depois importação: acrescentar ou substituir | Provado | navegador |
| CSV UTF-8 e Windows-1252 | Provado | 68 casos CSV |
| TXT com unidade na célula | Provado | casos TXT e 46 tabelas do Revit do acervo |
| Excel com abas e célula inválida | Provado | casos de planilha e navegador |
| PDF do layout aprovado | Provado nas 23 amostras do acervo | `pdf.test.ts` |
| Lista vazia, quantidade zero, unidade inválida: bloqueado na tela e recusado na API | Provado | testes do frontend e `test_rotas_orcamentos.py` |
| Descrição genérica válida é aceita e vira pergunta | Provado em memória | `test_fluxo_a_b_c.py` |
| Arquivo vazio, protegido, corrompido ou grande: erro claro, lista preservada | Provado (PDF protegido **simulado**) | importadores e navegador |
| Resposta perdida após salvar: reenvio recupera | Provado em memória e no SQL | `envio.test.ts`, SQL (`criar_orcamento` existente) |
| Duas requisições equivalentes: um orçamento e uma execução | Parcial | SQL: 12 criações simultâneas dão 1 criado e 11 recuperados; **a reserva da B com concorrência real não foi testada** |

## 5. Pendências por função (E1 a E11) e responsável

| # | Função | Responsável | Estado | Pendência |
|---|---|---|---|---|
| E1 | Revisor de erros | A (Samuel) | Pronto | Listas de marcas e famílias são curtas: produto fora do acervo passa sem aviso (omissão, não falso alarme). |
| E2 | Itens esquecidos | C (João) | Pronto | Endpoint combinado está em `/revisao/sugestoes/completo`; unificar com `/revisao/sugestoes` só se o João remover o handler dele (proposta aberta). |
| E3 | Lista de compra com perda | B (Enzo) | Pronto | — |
| E4 | Pesquisa agêntica | B (Enzo) | Pronto | Cerca de 1 em 5 itens fora do cache sai sem preço; conferir a cota do Tavily no domingo às 8h. |
| E5 | Pergunta ao arquiteto | B (Enzo) | Pronto | Provado no navegador com API simulada; repetir no link final. |
| E6 | Confiança e fonte | B (Enzo) | Pronto | Nunca preço sem fonte: garantido no SQL, no modelo da B e na tela. |
| E7 | Frete por CEP | C (João) | **Em pausa** | Frete sempre R$ 0 (`FRETE_ATIVO` desligado, `fornecedores` vazia). Decidir: apresentar como "frete a confirmar" (é o que a tela faz hoje). |
| E8 | Viabilidade | C (João) | Pronto | Avisa quando há itens sem preço. |
| E9 | Arquivo de exemplo | A (Samuel) | Pronto | Cache dos 3 exemplos aquecido pelo Enzo; reaquecer se o cache vencer (7 dias). |
| E10 | Ganho na tela | C (João) | Pronto | — |
| E11 | Exportar | C (João) | Pronto no servidor | O download pelo navegador no link final ainda não foi testado. |

**Pendências abertas da Fatia A** (nenhuma bloqueia a demo, todas devem ser conhecidas):
1. Publicar o site (seção 2.1) e rodar o ensaio (2.3). **Bloqueia a validação no link final.**
2. Confirmar a duração máxima da função no projeto do backend (≥ 60 s).
3. O adaptador do Enzo reserva e grava com `UPDATE` direto, sem usar as funções de reserva do SQL (`reservar_pesquisa` e outras): funciona, mas a proteção contra gravação atrasada que testamos no banco não está em uso.
4. A leitura pública (`anon`) de `orcamentos` e `orcamento_itens` é só para a demo sintética: qualquer pessoa com a chave anon lista todos os orçamentos. Dizer isso na submissão se perguntarem.
5. A API não tem autenticação e o CORS é aberto (decisão do time: é demo). O limite de corpo (8 MB) e de itens (5.000) protege o servidor.
6. Exportações reais do Revit e do SketchUp ainda não foram testadas (as amostras são sintéticas).
7. Acessibilidade (teclado e leitor de tela), Safari e Firefox não foram conferidos; o visual nunca foi comparado com o Figma (sem acesso).
8. Casos manuais TC-087 e TC-090 (prompt do LLM com resumo e injeção de instrução) dependem do Langfuse e do agente.

## 6. Quem faz o quê até a submissão (domingo, meta 12h30)

| Tarefa | Quem | Quando |
|---|---|---|
| Publicar o site e conferir a duração da função (seção 2) | Samuel (ou quem tiver a Vercel) | agora |
| Rodar `ensaio_link_final.mjs` com `--enviar` e colar a saída no grupo | Samuel | agora |
| Testar como jurado (aba anônima e celular, os 3 exemplos, Responder e Pesquisar de novo) | quem estiver livre | hoje à noite |
| Vídeo de até 2 min seguindo a seção 3 | Fatia D | domingo cedo |
| Descrição do projeto e slides (usar `docs/SUBMISSAO-FATIA-B.md` para o agente) | Fatia D | até 11h |
| Formulário de submissão | Fatia D | até 12h30 |
| Conferir a cota do Tavily e, se baixa, desligar a busca aberta (`PESQUISA_BUSCA_ABERTA=false`) | Enzo | domingo 8h |
| Cancelar os planos da Featherless | donos das chaves | depois do evento |
