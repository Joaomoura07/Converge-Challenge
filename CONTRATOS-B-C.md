# Contratos recebidos de Enzo e João

Registrados em 07/11/2026 a partir das mensagens encaminhadas por Samuel neste chat. Samuel identificou a primeira resposta como de Enzo (B) e a segunda como de João (C). Este arquivo registra requisitos de integração e divergências a resolver na etapa 02. A compatibilidade do SQL ainda depende de revisão dos colegas.

## 1. Fatia B — Enzo

A salva os itens e chama `await pesquisar_orcamento(orcamento_id)` na mesma requisição. A interface acompanha o andamento pelo Realtime enquanto a requisição permanece aberta. Preservar o tratamento da resposta e de falhas do POST. O UUID antecipado deve permitir o acompanhamento antes da resposta.

### orcamento_itens — campos escritos pela B

| Coluna | Tipo e regra solicitados |
|---|---|
| status | text; buscando, definido, pendente_especificacao, nao_encontrado, erro; default buscando |
| produto_normalizado | text |
| imagem_url | text |
| embalagem | text |
| unidade_preco | text |
| pergunta | text |
| motivo | text |
| qtd_embalagens | int |
| iteracoes | int, default 0 |
| preco_emb_min, preco_emb_med, preco_emb_max | numeric(12,2) |
| preco_un_min, preco_un_med, preco_un_max | numeric(12,4) |
| confianca | text; alta, media, baixa |
| estimativa | boolean, default false |
| fontes | jsonb, default [] |
| preco_data | timestamptz |
| atualizado_em | timestamptz, default now(), atualizado a cada UPDATE |

Cada fonte enviada por B contém `loja`, `dominio`, `url`, `preco_embalagem` e `embalagem`. A/B precisam gravar preços e suas fontes de forma consistente. A regra geral do time continua exigindo fonte para preços, inclusive os estimados e os novos campos por unidade.

B lê `id`, `orcamento_id`, `descricao`, `quantidade`, `unidade`, `categoria` e `classificacao`. Confirmar os valores aceitos de `classificacao`, pois o SQL atual usa definido/generico e a regra conceitual do plano usa definido/pendente.

### Controle em orcamentos

- `status_pesquisa` text com pendente, pesquisando, concluida e falhou, default pendente.
- `pesquisa_iniciada_em` e `pesquisa_concluida_em` timestamptz.
- `pesquisa_erro` text.
- B reserva a pesquisa dentro de `pesquisar_orcamento`, mediante UPDATE condicional com RETURNING. A chama B uma única vez por tentativa válida.
- Se B não adquirir a reserva, devolve o estado atual. Processa apenas itens com status buscando e pula itens já definidos.
- B propõe retomada após três minutos desde `pesquisa_iniciada_em`, além da retomada de pendente/falhou.
- Ao terminar, B grava concluida ou falhou, erro quando houver e data de conclusão.
- A mantém o botão desabilitado enquanto status_pesquisa for pesquisando e durante o envio ainda sem confirmação da reserva.

### cache_precos

`chave text PRIMARY KEY`, `resultado jsonb`, `imagem_url text`, `atualizado_em timestamptz DEFAULT now()`.

A validade de sete dias consta da divisão do time. Fechar com B se ela será calculada a partir de atualizado_em. Os campos criado_em/expira_em do SQL atual exigem adaptação se continuarem sendo usados por algum chamador.

### Permissões

`orcamentos` e `orcamento_itens` na publicação supabase_realtime, leitura anon conforme o modelo da demo e escrita pelo backend com service_role. Preservar a divulgação da limitação de leitura pública da demo sintética. A validação no Supabase real continua pendente.

## 2. Fatia C — João

### fornecedores

- Obrigatórios para a integração: id, nome, dominio, cep, frete_base (numeric), rs_por_km (numeric), pedido_minimo (numeric).
- Opcionais: lat, lon, ativo.
- Normalizar dominio com a mesma regra usada por B, como `leroymerlin.com.br`, sem `www`. João liga preço e loja por esse campo.

### orcamentos

- nome, cep e created_at.
- concluido_em ou status para calcular o tempo ganho. Propor a reutilização de pesquisa_concluida_em quando representar a conclusão necessária à C e obter confirmação de João.
- orcamento_cliente em reais, também dentro de obra no POST /orcamentos.

O campo orcamento_cliente já existe no SQL atual e no exemplo proposto do contexto. A rota de criação ainda precisa implementá-lo e validar o valor.

### orcamento_itens

Da A, João lê linha, categoria, descricao, quantidade, unidade, nivel e extras jsonb. Da B, lê status, qtd_embalagens, embalagem, preco_emb_min/med/max, estimativa, confianca, pergunta, imagem_url e fontes. A lista de fontes requerida pela C é compatível com a de B, incluindo os campos loja, dominio, url e preco_embalagem.

Solicita também `similar jsonb` com descricao e preco_emb_med. Esse armazenamento permite integrar a sugestão opcional T2 da B. Confirmar como o similar preserva sua própria fonte, conforme a regra do time.

Para complementos, guardar sugerido (boolean), regra, motivo, origem_linhas (int[]) e aceito (boolean). João aceita campos explícitos ou armazenamento em extras, desde que o local seja combinado. Preferir uma representação única e atualizar criação do orçamento, aceite e leitura pela C com a mesma escolha. Separar o motivo de sugestão do motivo de resultado da B quando tiverem significados diferentes.

### Exemplo informado por João

João relatou ter executado o exemplo abaixo. Esse resultado ainda precisa de validação local de integração.

Entrada

```json
[
  {"linha": 1, "categoria": "Revestimentos", "descricao": "Porcelanato 90x90 acetinado", "quantidade": 48, "unidade": "m2"},
  {"linha": 2, "categoria": "Pintura", "descricao": "Tinta acrilica fosca branca", "quantidade": 120, "unidade": "m2"}
]
```

Uma sugestão da saída

```json
{
  "regra": "porcelanato",
  "descricao": "Argamassa colante AC-III 20 kg (saco)",
  "quantidade": 15,
  "unidade": "un",
  "categoria": "Revestimentos e argamassas",
  "motivo": "Para 48 m² de piso/revestimento costumam faltar argamassa, rejunte e niveladores.",
  "origem_linhas": [1],
  "estimativa": true
}
```

João informou também rejunte 5 un, espaçador/nivelador 3 un, selador 2, massa corrida 3, fita crepe 8 e lixa 60. As quantidades são resultados das regras da C para esse exemplo; a A recebe as sugestões e aguarda o aceite. Esse estimativa descreve a sugestão de consumo. Definir como preservá-lo sem confundir com estimativa de preço produzida pela B.

João calcula frete, comparação com orçamento, ganho de tempo e Excel na hora e informou que essas saídas dispensam colunas. Isso exige reconciliar o contrato original, que previa resultados gerais gravados em orcamentos e exibidos por Realtime. Fechar qual função/rota fornece os valores à tela e quais dados sinalizam que estão prontos. O requisito de PDF da Fatia C continua registrado na divisão do time.

### 2.1 Mensagem posterior de João (`PARA-SAMUEL.md`, 07/11/2026)

João relata, na branch local `feat/joao-complementos-e2` (sem push), funções puras prontas: `sugerir_complementos`, `calcular_logistica`, `distancias_km`, `calcular_viabilidade`, `calcular_ganho` e `gerar_xlsx` (257 testes passando, segundo ele; não verificado aqui). Pedidos registrados:

- **Reverte** a informação anterior de que a tela não precisa de colunas: pede `orcamentos.logistica`, `viabilidade` e `ganho` (jsonb), lidos pela tela via Realtime. A atendeu com `ganho jsonb` nullable no SQL.
- `orcamentos`: `cep`, `orcamento_cliente`, `custo_usd` e `iniciado_em`/`concluido_em` para o tempo real. A mapeia para `pesquisa_iniciada_em` e `pesquisa_concluida_em` (PROPOSTA a confirmar com João).
- `fornecedores`: `lat`/`lon` pedidos como double precision e importantes (evitam chamada de CEP); A usa `numeric(9,6)` (PROPOSTA). Seed de 6 a 10 lojas de Recife: João oferece `sql/003_seed_fornecedores.sql`, aguardando resposta de Samuel.
- `orcamento_itens`: mesmas colunas de B, `similar` opcional `{descricao, preco_emb_med}` (A exige também `fontes` quando há preço) e status oficiais iguais aos do plano.
- Rotas dele, em `src/rotas_resultado.py` (`APIRouter`, duas linhas no `main.py` de Samuel): `POST /revisao/sugestoes` (devolve `{complementos}`; A acrescenta `erros`), `POST /orcamentos/{id}/resultado` (lê o banco, calcula logística, viabilidade e ganho e grava em `orcamentos`; Enzo chama ao fim da pesquisa) e `GET /orcamentos/{id}/exportar.xlsx`.
- Esqueleto da página de resultado e `useOrcamento(id)` precisam expor `logistica`, `viabilidade` e `ganho`; botão "Aceitar" por complemento; dependência nova `openpyxl>=3.1`; geocodificação por ViaCEP + Nominatim; só soma preços com `fontes[]`.
- Perguntas a Samuel: nomes de colunas, quem faz o seed, framework e pasta do site, permissão para criar o arquivo de rotas, data de aplicação do SQL.

Estado do SQL após este pedido: ver seção 0 de `CONTEXTO-DO-PROJETO.md`.

## 3. Divergências encontradas no SQL atual

| SQL atual | Requisito recebido | Trabalho necessário |
|---|---|---|
| produto, imagem | produto_normalizado, imagem_url | Adequar colunas, gravações, validação de chaves e testes |
| preco_data date, updated_at | preco_data timestamptz, atualizado_em | Adequar tipos, triggers, índices e leitores |
| Preços por embalagem numeric(14,2) | numeric(12,2), mais preços por unidade numeric(12,4) | Conferir compatibilidade de dados e incluir validações dos seis preços |
| Sem unidade_preco e iteracoes | Campos solicitados por B | Incluir tipos/default e gravações |
| estado, erro_mensagem em orcamentos | status_pesquisa e pesquisa_erro | Definir fonte única do estado da pesquisa e adaptar funções/retornos |
| Reserva prevista na API com RPCs e tentativa | Reserva interna da B com UPDATE condicional | Fechar um único protocolo com B |
| cache com criado_em/expira_em | imagem_url e atualizado_em | Alinhar cache e vencimento com B |
| frete_por_km, latitude, longitude | rs_por_km, lat, lon | Alinhar nomes usados pela C e seus cadastros |
| Auditoria parcial via sugestao_aceita_id/extras | sugerido, regra, motivo, origem_linhas, aceito | Definir representação completa de E2 com C |
| Sem similar | similar jsonb | Preparar o campo para integração opcional |
| logistica/viabilidade persistidos | C calcula na hora | Fechar transporte dos resultados para o frontend |

### Concorrência — decisão que exige acordo com Enzo

A reserva passa a ocorrer dentro da B, conforme o contrato enviado. Há duas propostas diferentes em circulação: o UPDATE simples do Enzo e as funções com tentativa/heartbeat geradas pelo Claude. O protocolo de gravação e finalização precisa ser único e aceito pela B.

Três minutos decorridos não provam que a execução anterior morreu. Confirmar duração máxima efetiva na Vercel e proteger uma eventual nova tentativa contra gravações tardias. Uma execução antiga deve perder autorização para atualizar itens e finalizar o orçamento quando outra assumir.

A revisão do SQL encontrou que gravar_resultado_item verifica a tentativa usando UPDATE com JOIN em orcamentos e só depois atualiza o heartbeat. Testar especificamente a corrida em que a tentativa muda entre a leitura do orçamento e a gravação do item. A exclusão mútua deve proteger atomicamente verificação, escrita e atualização de atividade, com ordem consistente de bloqueios. Testes paralelos que não controlam esse intercalamento podem deixar a regressão passar.

As evidências de 93 verificações são registradas pelo Claude no contexto. A revisão neste chat leu o código e os requisitos; a nova rodada de testes cabe ao ajuste da etapa 02.

## 4. Próximo pedido ao Claude

Reabrir a etapa 02 para compatibilização com este contrato. Produzir SQL e testes atualizados para os nomes exatos e as escritas de B/C. Checar se a versão anterior já foi aplicada e preservar dados existentes com migração adequada. Confirmar o protocolo de reserva com Enzo e a leitura do resultado com João antes de declarar a integração compatível. Entregar o SQL completo em texto para Samuel encaminhar aos dois e registrar as respostas.
