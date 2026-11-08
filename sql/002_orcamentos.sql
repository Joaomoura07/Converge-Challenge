-- Orçamentista Autônomo: SQL único da Fatia A (responsável: Samuel).
-- Tabelas: orcamentos, orcamento_itens, cache_precos, fornecedores.
-- Rode inteiro no SQL Editor do Supabase (ou é aplicado no Postgres local via docker-compose).
--
-- Serve para banco novo E para banco que já tenha o rascunho anterior desta etapa:
-- o bloco "MIGRAÇÃO" converte o rascunho no lugar, preservando os dados, e não faz nada
-- em banco novo. Pode ser rodado várias vezes. (Em 07/11/2026 o rascunho NÃO estava
-- aplicado no Supabase do projeto; as 4 tabelas não existiam.)
--
-- Contrato: CONTRATOS-B-C.md (Enzo = B, João = C). O que ainda é PROPOSTA da A, a revisar
-- por B/C, está marcado com "PROPOSTA" nos comentários.
--
-- Modelo de acesso:
--   * Escrita: só o backend, com a chave de serviço (service_role). O navegador não grava.
--   * Leitura de orcamentos e orcamento_itens: chave pública (anon), para o Realtime.
--     O orcamento_id é um UUID gerado na tela, mas a política NÃO filtra por dono:
--     quem tiver a chave anon consegue listar tudo. Aceitável só para a demo sintética.
--   * cache_precos (formato do Enzo) e fornecedores: sem acesso público, só pelo backend.
--
-- ===========================================================================
-- COMO A FATIA B USA A PESQUISA (protocolo único: reservar → gravar → finalizar)
-- ===========================================================================
-- Tudo dentro de pesquisar_orcamento(orcamento_id), chamando estas funções com a chave
-- de serviço (supabase.rpc("nome", {...})). Não faça UPDATE direto nas tabelas durante a
-- pesquisa: só as funções conferem se a sua execução ainda é a vigente.
--
--   1. r = reservar_pesquisa(orcamento_id)
--        -> {"reservado": true,  "tentativa": N, "status_pesquisa": "pesquisando"}
--        -> {"reservado": false, "tentativa": null, "status_pesquisa": "..."}  (devolva o estado e saia)
--      Reserva se status_pesquisa for 'pendente' ou 'falhou', ou 'pesquisando' sem atividade
--      há 180 s. Guarde N: é o seu número de tentativa em todas as chamadas seguintes.
--      repesquisar_item (orçamento já 'concluida'): reservar_pesquisa(id, 180, true).
--   2. Para cada item com status 'buscando':
--        ok = gravar_resultado_item(item_id, N, {...campos do item...})
--        ok = false  -> outra execução assumiu: PARE, não grave mais nada, não finalize.
--      Preços e fontes vão no MESMO dict (a mesma chamada). Cada gravação renova o prazo.
--      Item muito demorado: renovar_pesquisa(orcamento_id, N) de tempos em tempos.
--   3. finalizar_pesquisa(orcamento_id, N, 'concluida' | 'falhou', {pesquisa_erro, custo_usd, ...})
--        ok = false -> outra execução assumiu; descarte.
--   4. Só depois de finalizar, chame calcular_logistica/viabilidade da C.
--
-- Por que é seguro: tentativa velha não grava nem finaliza, mesmo se ainda estiver viva e
-- o prazo de 180 s tiver vencido com ela trabalhando. As funções travam a linha do
-- orçamento ANTES de conferir a tentativa e de gravar o item, então a troca de tentativa
-- não pode acontecer no meio de uma gravação.
-- ===========================================================================

-- gen_random_uuid() é nativo no Postgres 13+ (Supabase usa 15+): nenhuma extensão é necessária.

-- ---------------------------------------------------------------------------
-- Funções auxiliares (sem dependência de tabelas)
-- ---------------------------------------------------------------------------
create or replace function set_atualizado_em() returns trigger
language plpgsql as $$
begin
    new.atualizado_em := now();
    return new;
end;
$$;

-- Domínio canônico, a mesma regra para B e C: minúsculo, sem esquema, sem "www.", sem
-- porta nem caminho. 'https://WWW.LeroyMerlin.com.br/p/1' -> 'leroymerlin.com.br'
create or replace function normalizar_dominio(d text) returns text
language sql immutable as $$
    select nullif(
        regexp_replace(
            regexp_replace(regexp_replace(lower(btrim(d)), '^[a-z][a-z0-9+.-]*://', ''), '^www\.', ''),
            '[/?#:].*$', ''),
        '')
$$;

-- Normaliza o campo dominio de cada fonte (lista jsonb).
create or replace function normalizar_fontes(f jsonb) returns jsonb
language sql immutable as $$
    select case when jsonb_typeof(f) = 'array' then
        coalesce((select jsonb_agg(
                    case when jsonb_typeof(e) = 'object' and jsonb_typeof(e -> 'dominio') = 'string'
                         then jsonb_set(e, '{dominio}', to_jsonb(coalesce(normalizar_dominio(e ->> 'dominio'), '')))
                         else e end
                    order by ord)
                  from jsonb_array_elements(f) with ordinality as t(e, ord)),
                 '[]'::jsonb)
    else f end
$$;

-- Lista de fontes válida: cada fonte é {loja, dominio (já normalizado), url http(s),
-- preco_embalagem >= 0, embalagem (texto, opcional)}. Lista vazia é válida aqui;
-- a exigência de fonte para preço está em fontes_nao_vazias_validas().
create or replace function fontes_validas(f jsonb) returns boolean
language sql immutable as $$
    select case when jsonb_typeof(f) is distinct from 'array' then false
    else not exists (
        select 1 from jsonb_array_elements(f) e
        where case when jsonb_typeof(e) <> 'object' then true
                   else coalesce(btrim(e ->> 'loja'), '') = ''
                     or coalesce(btrim(e ->> 'dominio'), '') = ''
                     or e ->> 'dominio' is distinct from normalizar_dominio(e ->> 'dominio')
                     or coalesce(e ->> 'url', '') !~ '^https?://[^[:space:]]+$'
                     or case when jsonb_typeof(e -> 'preco_embalagem') = 'number'
                             then (e ->> 'preco_embalagem')::numeric < 0
                             else true end
                     or (e ? 'embalagem' and jsonb_typeof(e -> 'embalagem') not in ('string', 'null'))
              end)
    end
$$;

create or replace function fontes_nao_vazias_validas(f jsonb) returns boolean
language sql immutable as $$
    select case when jsonb_typeof(f) = 'array'
                then jsonb_array_length(f) > 0 and fontes_validas(f)
                else false end
$$;

-- true se o objeto traz algum dos seis preços preenchidos.
create or replace function resultado_com_preco(r jsonb) returns boolean
language sql immutable as $$
    select coalesce(r ->> 'preco_emb_min', r ->> 'preco_emb_med', r ->> 'preco_emb_max',
                    r ->> 'preco_un_min', r ->> 'preco_un_med', r ->> 'preco_un_max') is not null
$$;

-- ---------------------------------------------------------------------------
-- MIGRAÇÃO do rascunho anterior (no lugar, preservando dados). Não faz nada em banco novo.
-- Detecta o rascunho pela coluna orcamentos.estado. Mapeamentos:
--   orcamentos: estado recebido/pesquisando/concluido/erro -> status_pesquisa pendente/
--     pesquisando/concluida/falhou; erro_mensagem -> pesquisa_erro; updated_at -> atualizado_em
--   orcamento_itens: produto -> produto_normalizado; imagem -> imagem_url; erro_mensagem ->
--     motivo; updated_at -> atualizado_em; preco_data date -> timestamptz; classificacao
--     'generico' -> 'pendente'; preços por embalagem para numeric(12,2); domínios das fontes
--     normalizados; linha vazia recebe a posição do item
--   cache_precos: criado_em -> atualizado_em (expira_em some: validade = atualizado_em + 7 dias)
--   fornecedores: frete_por_km -> rs_por_km; latitude/longitude -> lat/lon
-- Falha de propósito (e desfaz tudo) se houver fornecedor sem CEP/frete_base/rs_por_km/
-- pedido_minimo, que passam a ser obrigatórios: complete os dados e rode de novo.
-- ---------------------------------------------------------------------------
do $$
declare
    r record;
begin
    if to_regclass('orcamentos') is null
       or not exists (select 1 from information_schema.columns
                      where table_schema = current_schema() and table_name = 'orcamentos'
                        and column_name = 'estado') then
        return;
    end if;

    -- As regras do rascunho saem primeiro (elas usariam as funções novas, mais rígidas, nos
    -- UPDATEs abaixo). As regras novas são criadas no bloco "Regras", mais adiante.
    for r in
        select c.conrelid::regclass as tabela, c.conname
          from pg_constraint c
         where c.contype = 'c'
           and c.conrelid in ('orcamentos'::regclass, 'orcamento_itens'::regclass,
                              'cache_precos'::regclass, 'fornecedores'::regclass)
    loop
        execute format('alter table %s drop constraint %I', r.tabela, r.conname);
    end loop;

    -- orcamentos
    drop trigger if exists orcamentos_updated_at on orcamentos;
    alter table orcamentos add column status_pesquisa text;
    update orcamentos set status_pesquisa = case estado
        when 'recebido' then 'pendente' when 'pesquisando' then 'pesquisando'
        when 'concluido' then 'concluida' else 'falhou' end;
    alter table orcamentos alter column status_pesquisa set not null;
    alter table orcamentos alter column status_pesquisa set default 'pendente';
    alter table orcamentos drop column estado;
    alter table orcamentos rename column erro_mensagem to pesquisa_erro;
    alter table orcamentos rename column updated_at to atualizado_em;

    -- orcamento_itens
    drop trigger if exists orcamento_itens_updated_at on orcamento_itens;
    alter table orcamento_itens rename column produto to produto_normalizado;
    alter table orcamento_itens rename column imagem to imagem_url;
    alter table orcamento_itens rename column updated_at to atualizado_em;
    alter table orcamento_itens add column unidade_preco text;
    alter table orcamento_itens add column motivo text;
    update orcamento_itens set motivo = erro_mensagem where erro_mensagem is not null;
    alter table orcamento_itens drop column erro_mensagem;
    alter table orcamento_itens add column iteracoes integer not null default 0;
    alter table orcamento_itens add column preco_un_min numeric(12, 4);
    alter table orcamento_itens add column preco_un_med numeric(12, 4);
    alter table orcamento_itens add column preco_un_max numeric(12, 4);
    alter table orcamento_itens add column "similar" jsonb;
    alter table orcamento_itens add column sugerido boolean not null default false;
    alter table orcamento_itens add column sugestao_regra text;
    alter table orcamento_itens add column sugestao_motivo text;
    alter table orcamento_itens add column origem_linhas integer[];
    alter table orcamento_itens add column aceito boolean;
    alter table orcamento_itens add column estimativa_consumo boolean not null default false;
    alter table orcamento_itens alter column preco_data type timestamptz using preco_data::timestamptz;
    alter table orcamento_itens alter column preco_emb_min type numeric(12, 2);
    alter table orcamento_itens alter column preco_emb_med type numeric(12, 2);
    alter table orcamento_itens alter column preco_emb_max type numeric(12, 2);
    update orcamento_itens set fontes = normalizar_fontes(fontes);
    update orcamento_itens i set linha = n.pos
      from (select id, row_number() over (partition by orcamento_id order by created_at, id_linha) as pos
              from orcamento_itens) n
     where i.id = n.id and i.linha is null;
    alter table orcamento_itens alter column linha set not null;
    update orcamento_itens set classificacao = 'pendente' where classificacao = 'generico';

    -- cache_precos
    alter table cache_precos rename column criado_em to atualizado_em;
    alter table cache_precos drop column expira_em;
    alter table cache_precos add column imagem_url text;

    -- fornecedores
    alter table fornecedores rename column frete_por_km to rs_por_km;
    alter table fornecedores rename column latitude to lat;
    alter table fornecedores rename column longitude to lon;
    update fornecedores set dominio = coalesce(normalizar_dominio(dominio), dominio);
    alter table fornecedores alter column cep set not null;
    alter table fornecedores alter column frete_base set not null;
    alter table fornecedores alter column rs_por_km set not null;
    alter table fornecedores alter column pedido_minimo set not null;
    alter table fornecedores alter column frete_base type numeric;
    alter table fornecedores alter column rs_por_km type numeric;
    alter table fornecedores alter column pedido_minimo type numeric;

    -- funções antigas
    drop function if exists iniciar_pesquisa(uuid, integer);
    drop function if exists set_updated_at();
end;
$$;

-- ---------------------------------------------------------------------------
-- orcamentos: um por envio. O id vem da tela (UUID v4) e serve de chave de reenvio.
-- ---------------------------------------------------------------------------
create table if not exists orcamentos (
    id                uuid primary key,
    nome              text not null,
    cep               text not null,                        -- texto, com zero à esquerda
    orcamento_cliente numeric(14, 2) not null,              -- em reais, com centavos
    origem            jsonb not null default '{}'::jsonb,   -- {tipo, arquivo, formato, software}
    hash_conteudo     text not null,                        -- resumo do envio: detecta conflito no reenvio
    qtd_itens         integer not null,

    -- Pesquisa (B). status_pesquisa descreve a execução do orçamento, não os itens.
    status_pesquisa       text not null default 'pendente',
    pesquisa_iniciada_em  timestamptz,
    pesquisa_concluida_em timestamptz,   -- PROPOSTA: a C usa como "concluído em" (ganho de tempo)
    pesquisa_erro         text,
    -- Protocolo de tentativa (A+B): número da execução vigente e sua última atividade.
    tentativa_pesquisa    integer not null default 0,
    pesquisa_heartbeat_em timestamptz,

    -- Agregados opcionais (escritos pela B ao finalizar; a C pode ignorar e calcular na hora)
    total_min         numeric(14, 2),
    total_med         numeric(14, 2),
    total_max         numeric(14, 2),
    tempo_ms          integer,
    custo_usd         numeric(12, 6),
    trace_url         text,    -- trace no Langfuse
    -- Resultados da C (João), gravados pelo backend com a chave de serviço e lidos pela tela via
    -- Realtime. Opcionais (null até a C calcular). Gravar estas colunas NÃO mexe no protocolo da
    -- pesquisa (tentativa_pesquisa, status_pesquisa): são UPDATEs de colunas independentes.
    logistica         jsonb,   -- E7
    viabilidade       jsonb,   -- E8
    ganho             jsonb,   -- E10 (ganho de tempo)

    created_at        timestamptz not null default now(),
    atualizado_em     timestamptz not null default now()
    -- regras (checks): bloco "Regras" mais abaixo, igual para banco novo e migrado
);

-- Bancos que receberam uma versão anterior deste mesmo arquivo (sem estas colunas).
alter table orcamentos add column if not exists logistica   jsonb;
alter table orcamentos add column if not exists viabilidade jsonb;
alter table orcamentos add column if not exists ganho       jsonb;

create index if not exists orcamentos_created_at_idx on orcamentos (created_at desc);
create index if not exists orcamentos_status_pesquisa_idx on orcamentos (status_pesquisa);

drop trigger if exists orcamentos_atualizado_em on orcamentos;
create trigger orcamentos_atualizado_em before update on orcamentos
    for each row execute function set_atualizado_em();

-- ---------------------------------------------------------------------------
-- orcamento_itens: um por item. Realtime acompanha por orcamento_id.
-- ---------------------------------------------------------------------------
create table if not exists orcamento_itens (
    id                 uuid primary key default gen_random_uuid(),
    orcamento_id       uuid not null references orcamentos (id) on delete cascade,

    -- Entrada (A). id_linha = identificador estável da linha na tela; linha = posição/origem
    -- (a C usa `linha` em origem_linhas).
    id_linha           text not null,
    linha              integer not null,
    categoria          text,
    descricao_original text not null,
    descricao          text not null,           -- valor revisado: é o que a B pesquisa
    quantidade         numeric(14, 4) not null,
    unidade            text not null,           -- lista de unidades validada pela API, não pelo banco
    nivel              text,
    origem_item        text,                    -- 'arquivo' | 'manual'
    extras             jsonb not null default '{}'::jsonb,
    sugestao_aceita_id text,                    -- auditoria: sugestão E1/E2 aceita que gerou/alterou a linha

    -- Classificação de negócio (A decide, B confirma, C lê). Separada do status.
    -- PROPOSTA: valores 'definido' | 'pendente' (antes eram definido/generico). B confirma.
    classificacao      text not null,

    -- Complementos (C, E2). PROPOSTA: representação única em colunas explícitas.
    sugerido           boolean not null default false,   -- linha criada a partir de um complemento
    sugestao_regra     text,                             -- regra da C (ex.: 'porcelanato')
    sugestao_motivo    text,                             -- motivo da SUGESTÃO (não confundir com `motivo`)
    origem_linhas      integer[],                        -- `linha` dos itens que motivaram o complemento
    aceito             boolean,                          -- true quando o arquiteto aceitou
    estimativa_consumo boolean not null default false,   -- quantidade estimada pela C (≠ `estimativa`)

    -- Resultado da pesquisa (B). Nomes e tipos de CONTRATOS-B-C.md.
    status             text not null default 'buscando',
    produto_normalizado text,
    imagem_url         text,
    embalagem          text,
    unidade_preco      text,
    pergunta           text,
    motivo             text,                    -- motivo do RESULTADO da B (pendente, não encontrado, erro)
    resposta           text,                    -- PROPOSTA: resposta do arquiteto à `pergunta` (escrita pela A)
    marca              text,                    -- opcional
    qtd_embalagens     integer,
    iteracoes          integer not null default 0,
    preco_emb_min      numeric(12, 2),
    preco_emb_med      numeric(12, 2),
    preco_emb_max      numeric(12, 2),
    preco_un_min       numeric(12, 4),
    preco_un_med       numeric(12, 4),
    preco_un_max       numeric(12, 4),
    confianca          text,
    estimativa         boolean not null default false,   -- ESTIMATIVA DE PREÇO (B); exige fonte
    fontes             jsonb not null default '[]'::jsonb,  -- [{loja, dominio, url, preco_embalagem, embalagem}]
    preco_data         timestamptz,             -- data do preço (cache vencido mostra "preço de dd/mm")
    "similar"          jsonb,                   -- PROPOSTA (T2): {descricao, preco_emb_med, fontes:[...]}
    tentativa          integer,                 -- tentativa da pesquisa que gravou o resultado

    created_at         timestamptz not null default now(),
    atualizado_em      timestamptz not null default now(),

    constraint orcamento_itens_orcamento_linha_uk unique (orcamento_id, id_linha)
    -- regras (checks): bloco "Regras" mais abaixo, igual para banco novo e migrado
);

-- Conta da compra que a B grava (ex.: "rendimento ≈ 11 m²/L (selador, 2 demãos)"); a tela mostra "Conta: ...".
-- Sem esta coluna a B tirava o campo calado e a linha nunca aparecia (medido no site em 07/11).
alter table orcamento_itens add column if not exists premissa text;
alter table orcamento_itens add column if not exists pesquisa_detalhes jsonb;

create index if not exists orcamento_itens_orcamento_idx on orcamento_itens (orcamento_id);
create index if not exists orcamento_itens_status_idx on orcamento_itens (orcamento_id, status);

drop trigger if exists orcamento_itens_atualizado_em on orcamento_itens;
create trigger orcamento_itens_atualizado_em before update on orcamento_itens
    for each row execute function set_atualizado_em();

-- Eventos de DELETE do Realtime só trazem a chave primária no padrão; com 'full' trazem o orcamento_id.
alter table orcamento_itens replica identity full;

-- ---------------------------------------------------------------------------
-- cache_precos (B). FORMATO REAL DO ENZO (src/cache.py e sql/002_cache_precos.sql da fatia B):
-- guarda as ofertas conferidas e a imagem; a conta é refeita a cada uso. Validade de 7 dias
-- contada a partir de atualizado_em; vencido continua guardado ("preço de dd/mm").
-- Esta definição vale para banco novo e para banco em que a tabela do Enzo já existe
-- (create table if not exists + colunas faltantes adicionadas). Nunca renomeia nem apaga a tabela.
-- ---------------------------------------------------------------------------
create table if not exists cache_precos (
    chave          text primary key,                      -- descrição normalizada (chave_cache)
    descricao      text not null default '',              -- descrição original, para leitura humana
    ofertas        jsonb not null default '[]'::jsonb,    -- [{loja, dominio, url, titulo, preco, embalagem, mesmo_produto}]
    imagem_url     text,
    modelo         text,
    provedor       text,                                  -- tavily | duckduckgo
    iteracoes      integer not null default 0,
    atualizado_em  timestamptz not null default now()
);

-- Tabela que já existia com formato diferente: completa o que falta, sem perder dados.
alter table cache_precos add column if not exists descricao     text not null default '';
alter table cache_precos add column if not exists ofertas       jsonb not null default '[]'::jsonb;
alter table cache_precos add column if not exists imagem_url    text;
alter table cache_precos add column if not exists modelo        text;
alter table cache_precos add column if not exists provedor      text;
alter table cache_precos add column if not exists iteracoes     integer not null default 0;
alter table cache_precos add column if not exists atualizado_em timestamptz not null default now();
-- `resultado` era do rascunho da A e o código do Enzo não grava nessa coluna (NOT NULL a quebraria).
alter table cache_precos drop column if exists resultado;

create index if not exists cache_precos_atualizado_idx on cache_precos (atualizado_em);

drop trigger if exists cache_precos_atualizado_em on cache_precos;
create trigger cache_precos_atualizado_em before update on cache_precos
    for each row execute function set_atualizado_em();

-- ---------------------------------------------------------------------------
-- fornecedores: esquema pela A, cadastro pela C (as mesmas redes que a busca encontra).
-- Nomes de CONTRATOS-B-C.md: obrigatórios id, nome, dominio, cep, frete_base, rs_por_km,
-- pedido_minimo; opcionais lat, lon, ativo.
-- ---------------------------------------------------------------------------
create table if not exists fornecedores (
    id             uuid primary key default gen_random_uuid(),
    nome           text not null,                -- ex.: "Leroy Merlin Recife"
    dominio        text not null,                -- canônico (ver normalizar_dominio), casa com fontes[].dominio
    site           text,
    cep            text not null,
    cidade         text,
    lat            numeric(9, 6),
    lon            numeric(9, 6),
    frete_base     numeric not null,
    rs_por_km      numeric not null,
    pedido_minimo  numeric not null,
    ativo          boolean not null default true,
    created_at     timestamptz not null default now(),
    constraint fornecedores_dominio_nome_uk unique (dominio, nome)
);

create index if not exists fornecedores_dominio_idx on fornecedores (dominio);

-- Cadastro tolerante: 'www.LeroyMerlin.com.br' entra como 'leroymerlin.com.br'.
create or replace function fornecedores_normaliza() returns trigger
language plpgsql as $$
begin
    new.dominio := coalesce(normalizar_dominio(new.dominio), new.dominio);
    return new;
end;
$$;

drop trigger if exists fornecedores_normaliza_dominio on fornecedores;
create trigger fornecedores_normaliza_dominio before insert or update on fornecedores
    for each row execute function fornecedores_normaliza();

-- ---------------------------------------------------------------------------
-- Regras (checks) das quatro tabelas. Uma definição só, idempotente: vale para banco novo e
-- para banco migrado do rascunho (a tabela já existia e o create table acima não a altera).
-- Os nomes são fixos para a API reconhecer o erro pelo nome da regra violada.
-- ---------------------------------------------------------------------------
do $$
declare
    r record;
begin
    -- Remove as regras antigas do rascunho (nomes automáticos) e as destas tabelas, para recriar.
    for r in
        select c.conrelid::regclass as tabela, c.conname
          from pg_constraint c
         where c.contype = 'c'
           and c.conrelid in ('orcamentos'::regclass, 'orcamento_itens'::regclass,
                              'cache_precos'::regclass, 'fornecedores'::regclass)
    loop
        execute format('alter table %s drop constraint %I', r.tabela, r.conname);
    end loop;
end;
$$;

alter table orcamentos
    add constraint orcamentos_nome_ck check (length(btrim(nome)) > 0),
    add constraint orcamentos_cep_ck check (cep ~ '^[0-9]{8}$'),
    add constraint orcamentos_cliente_ck check (orcamento_cliente > 0),
    add constraint orcamentos_qtd_itens_ck check (qtd_itens > 0),
    add constraint orcamentos_status_pesquisa_ck
        check (status_pesquisa in ('pendente', 'pesquisando', 'concluida', 'falhou'));

alter table orcamento_itens
    add constraint itens_descricao_original_ck check (length(btrim(descricao_original)) > 0),
    add constraint itens_descricao_ck check (length(btrim(descricao)) > 0),
    add constraint itens_quantidade_ck check (quantidade > 0),
    add constraint itens_origem_item_ck check (origem_item in ('arquivo', 'manual')),
    add constraint itens_classificacao_ck check (classificacao in ('definido', 'pendente')),
    add constraint itens_status_ck check (status in ('buscando', 'definido', 'pendente_especificacao',
                                                     'nao_encontrado', 'erro')),
    add constraint itens_confianca_ck check (confianca in ('alta', 'media', 'baixa')),
    add constraint itens_qtd_embalagens_ck check (qtd_embalagens is null or qtd_embalagens >= 0),
    add constraint itens_iteracoes_ck check (iteracoes >= 0),
    add constraint itens_precos_positivos_ck check (
        coalesce(preco_emb_min, 0) >= 0 and coalesce(preco_emb_med, 0) >= 0 and coalesce(preco_emb_max, 0) >= 0
        and coalesce(preco_un_min, 0) >= 0 and coalesce(preco_un_med, 0) >= 0 and coalesce(preco_un_max, 0) >= 0),
    add constraint preco_min_max_ck check (
        (preco_emb_min is null or preco_emb_max is null or preco_emb_min <= preco_emb_max)
        and (preco_un_min is null or preco_un_max is null or preco_un_min <= preco_un_max)),
    add constraint fontes_validas_ck check (fontes_validas(fontes)),
    -- "Nunca preço sem fonte": QUALQUER um dos seis preços (por embalagem ou por unidade)
    -- exige fontes válidas, inclusive quando estimativa = true. Grave preços e fontes
    -- no mesmo UPDATE (gravar_resultado_item faz isso).
    add constraint preco_exige_fonte_ck check (
        not resultado_com_preco(to_jsonb(orcamento_itens)) or fontes_nao_vazias_validas(fontes)),
    -- O similar (T2) também carrega a própria fonte quando tem preço.
    add constraint similar_ck check (
        "similar" is null or (
            jsonb_typeof("similar") = 'object'
            and coalesce(btrim("similar" ->> 'descricao'), '') <> ''
            and ("similar" ->> 'preco_emb_med' is null
                 or fontes_nao_vazias_validas("similar" -> 'fontes')))),
    -- Complemento sugerido: precisa de regra, linhas de origem e decisão registrada.
    add constraint sugestao_ck check (
        not sugerido or (sugestao_regra is not null
                         and coalesce(cardinality(origem_linhas), 0) > 0
                         and aceito is not null));

alter table fornecedores
    add constraint fornecedores_dominio_ck check (dominio = normalizar_dominio(dominio)),
    add constraint fornecedores_cep_ck check (cep ~ '^[0-9]{8}$'),
    add constraint fornecedores_valores_ck check (frete_base >= 0 and rs_por_km >= 0 and pedido_minimo >= 0);

-- ---------------------------------------------------------------------------
-- criar_orcamento (A): grava orçamento e itens numa transação e trata o reenvio.
--   p_obra  = {nome, cep, orcamento_cliente}      (orcamento_cliente em reais)
--   p_itens = [{id_linha, linha, categoria, descricao_original, descricao, quantidade, unidade,
--               nivel, origem_item, extras, classificacao, sugestao_aceita_id,
--               sugerido, sugestao_regra, sugestao_motivo, origem_linhas, aceito, estimativa_consumo}]
-- Retorna {resultado: 'criado' | 'existente' | 'conflito', orcamento_id, status_pesquisa}.
--   criado    -> itens gravados com status 'buscando'; status_pesquisa 'pendente'
--   existente -> mesmo id e mesmo hash (reenvio equivalente): nada é gravado, devolve o estado atual
--   conflito  -> mesmo id com hash diferente: nada é gravado (a API responde 409)
-- Duas chamadas simultâneas com o mesmo id: a segunda espera a primeira confirmar e cai em 'existente'.
-- Qualquer erro (item inválido, por exemplo) desfaz o orçamento inteiro.
-- ---------------------------------------------------------------------------
create or replace function criar_orcamento(
    p_id     uuid,
    p_hash   text,
    p_obra   jsonb,
    p_origem jsonb,
    p_itens  jsonb
) returns jsonb
language plpgsql as $$
declare
    v_inseridos integer;
    v_hash      text;
    v_status    text;
begin
    if jsonb_typeof(p_itens) is distinct from 'array' or jsonb_array_length(p_itens) = 0 then
        raise exception 'lista de itens vazia' using errcode = '22023';
    end if;

    insert into orcamentos (id, nome, cep, orcamento_cliente, origem, hash_conteudo, qtd_itens)
    values (p_id,
            p_obra ->> 'nome',
            p_obra ->> 'cep',
            (p_obra ->> 'orcamento_cliente')::numeric,
            coalesce(p_origem, '{}'::jsonb),
            p_hash,
            jsonb_array_length(p_itens))
    on conflict (id) do nothing;
    get diagnostics v_inseridos = row_count;

    if v_inseridos = 0 then
        -- Já existe (ou outra transação acabou de criar: o on conflict espera ela confirmar).
        select hash_conteudo, status_pesquisa into v_hash, v_status from orcamentos where id = p_id;
        return jsonb_build_object(
            'resultado', case when v_hash = p_hash then 'existente' else 'conflito' end,
            'orcamento_id', p_id,
            'status_pesquisa', v_status);
    end if;

    insert into orcamento_itens (orcamento_id, id_linha, linha, categoria, descricao_original,
                                 descricao, quantidade, unidade, nivel, origem_item, extras,
                                 classificacao, sugestao_aceita_id, sugerido, sugestao_regra,
                                 sugestao_motivo, origem_linhas, aceito, estimativa_consumo, status)
    select p_id, i.id_linha, i.linha, i.categoria,
           coalesce(i.descricao_original, i.descricao), i.descricao, i.quantidade, i.unidade,
           i.nivel, i.origem_item, coalesce(i.extras, '{}'::jsonb),
           i.classificacao, i.sugestao_aceita_id, coalesce(i.sugerido, false), i.sugestao_regra,
           i.sugestao_motivo,
           case when i.origem_linhas is null or jsonb_typeof(i.origem_linhas) = 'null' then null
                else array(select jsonb_array_elements_text(i.origem_linhas)::integer) end,
           i.aceito, coalesce(i.estimativa_consumo, false), 'buscando'
    from jsonb_to_recordset(p_itens) as i(
        id_linha text, linha integer, categoria text, descricao_original text, descricao text,
        quantidade numeric, unidade text, nivel text, origem_item text, extras jsonb,
        classificacao text, sugestao_aceita_id text, sugerido boolean, sugestao_regra text,
        sugestao_motivo text, origem_linhas jsonb, aceito boolean, estimativa_consumo boolean);

    return jsonb_build_object('resultado', 'criado', 'orcamento_id', p_id, 'status_pesquisa', 'pendente');
end;
$$;

-- ---------------------------------------------------------------------------
-- Protocolo da pesquisa (B usa; ver o guia no início do arquivo)
-- ---------------------------------------------------------------------------
drop function if exists iniciar_pesquisa(uuid, integer);

-- Reserva a pesquisa. Retorna {reservado, tentativa, status_pesquisa}.
--   Reserva se: pendente | falhou | (pesquisando sem atividade há p_expira_s) |
--               (concluida e p_reabrir = true, para repesquisar_item).
--   PROPOSTA: prazo de 180 s (os "três minutos" de B), contado desde a ÚLTIMA atividade
--   (reserva, gravação, renovação), não desde pesquisa_iniciada_em. O prazo só decide
--   quando uma execução parada pode ser retomada; a segurança vem do número da tentativa.
-- Um único UPDATE condicional: duas reservas simultâneas nunca vencem as duas.
create or replace function reservar_pesquisa(p_id uuid, p_expira_s integer default 180,
                                             p_reabrir boolean default false)
returns jsonb
language plpgsql as $$
declare
    v_tentativa integer;
    v_status    text;
begin
    update orcamentos
       set status_pesquisa = 'pesquisando',
           tentativa_pesquisa = tentativa_pesquisa + 1,
           pesquisa_iniciada_em = now(),
           pesquisa_heartbeat_em = now(),
           pesquisa_concluida_em = null,
           pesquisa_erro = null
     where id = p_id
       and (status_pesquisa in ('pendente', 'falhou')
            or (p_reabrir and status_pesquisa = 'concluida')
            or (status_pesquisa = 'pesquisando'
                and coalesce(pesquisa_heartbeat_em, pesquisa_iniciada_em)
                    < now() - make_interval(secs => p_expira_s)))
    returning tentativa_pesquisa, status_pesquisa into v_tentativa, v_status;

    if v_tentativa is not null then
        return jsonb_build_object('reservado', true, 'tentativa', v_tentativa, 'status_pesquisa', v_status);
    end if;
    select status_pesquisa into v_status from orcamentos where id = p_id;
    return jsonb_build_object('reservado', false, 'tentativa', null, 'status_pesquisa', v_status);
end;
$$;

-- Renova o prazo sem gravar nada. false = tentativa velha (pare).
create or replace function renovar_pesquisa(p_id uuid, p_tentativa integer)
returns boolean
language plpgsql as $$
begin
    -- Trava a linha do orçamento e confere a tentativa na mesma instrução. Se uma reserva
    -- concorrente está trocando a tentativa, esperamos ela terminar e conferimos de novo.
    perform 1 from orcamentos
     where id = p_id and status_pesquisa = 'pesquisando' and tentativa_pesquisa = p_tentativa
       for no key update;
    if not found then
        return false;
    end if;
    update orcamentos set pesquisa_heartbeat_em = now() where id = p_id;
    return true;
end;
$$;

-- Grava o resultado de UM item, preços e fontes na mesma operação, só se a tentativa for a vigente.
-- p_dados aceita SOMENTE estas chaves (qualquer outra gera erro). Chave ausente = campo intacto;
-- chave com null = limpa o campo:
--   status, produto_normalizado, imagem_url, embalagem, unidade_preco, pergunta, motivo,
--   qtd_embalagens, iteracoes, preco_emb_min, preco_emb_med, preco_emb_max, preco_un_min,
--   preco_un_med, preco_un_max, confianca, estimativa, fontes, preco_data, similar
-- O campo dominio de cada fonte é normalizado aqui. Retorna true se gravou; false se a
-- tentativa é velha (o item não é alterado: pare a execução). Erro de regra (preço sem
-- fonte, status inválido...) levanta exceção e nada é gravado.
-- Ordem de bloqueio: orcamentos primeiro, depois orcamento_itens (sempre a mesma).
create or replace function gravar_resultado_item(p_item_id uuid, p_tentativa integer, p_dados jsonb)
returns boolean
language plpgsql as $$
declare
    v_extras text[];
    v_orc    uuid;
begin
    v_extras := array(select k from jsonb_object_keys(p_dados) k
                      where k <> all (array['status', 'produto_normalizado', 'imagem_url', 'embalagem',
                                            'unidade_preco', 'pergunta', 'motivo', 'qtd_embalagens',
                                            'iteracoes', 'preco_emb_min', 'preco_emb_med', 'preco_emb_max',
                                            'preco_un_min', 'preco_un_med', 'preco_un_max', 'confianca',
                                            'estimativa', 'fontes', 'preco_data', 'similar', 'pesquisa_detalhes']));
    if cardinality(v_extras) > 0 then
        raise exception 'campos não permitidos em gravar_resultado_item: %', v_extras using errcode = '22023';
    end if;

    select orcamento_id into v_orc from orcamento_itens where id = p_item_id;
    if v_orc is null then
        raise exception 'item não encontrado: %', p_item_id using errcode = 'P0002';
    end if;

    -- Trava o orçamento e confere a tentativa vigente na mesma instrução (FOR NO KEY UPDATE).
    -- Se uma reserva está trocando a tentativa agora, esta chamada espera ela confirmar e
    -- confere de novo: a gravação de uma tentativa velha nunca passa.
    perform 1 from orcamentos
     where id = v_orc and status_pesquisa = 'pesquisando' and tentativa_pesquisa = p_tentativa
       for no key update;
    if not found then
        return false;
    end if;

    update orcamento_itens i set
        pesquisa_detalhes   = case when p_dados ? 'pesquisa_detalhes' then nullif(p_dados -> 'pesquisa_detalhes', 'null'::jsonb) else i.pesquisa_detalhes end,
        status              = case when p_dados ? 'status'              then p_dados ->> 'status'                          else i.status end,
        produto_normalizado = case when p_dados ? 'produto_normalizado' then p_dados ->> 'produto_normalizado'             else i.produto_normalizado end,
        imagem_url          = case when p_dados ? 'imagem_url'          then p_dados ->> 'imagem_url'                      else i.imagem_url end,
        embalagem           = case when p_dados ? 'embalagem'           then p_dados ->> 'embalagem'                       else i.embalagem end,
        unidade_preco       = case when p_dados ? 'unidade_preco'       then p_dados ->> 'unidade_preco'                   else i.unidade_preco end,
        pergunta            = case when p_dados ? 'pergunta'            then p_dados ->> 'pergunta'                        else i.pergunta end,
        motivo              = case when p_dados ? 'motivo'              then p_dados ->> 'motivo'                          else i.motivo end,
        qtd_embalagens      = case when p_dados ? 'qtd_embalagens'      then (p_dados ->> 'qtd_embalagens')::integer       else i.qtd_embalagens end,
        iteracoes           = case when p_dados ? 'iteracoes'           then coalesce((p_dados ->> 'iteracoes')::integer, 0) else i.iteracoes end,
        preco_emb_min       = case when p_dados ? 'preco_emb_min'       then (p_dados ->> 'preco_emb_min')::numeric        else i.preco_emb_min end,
        preco_emb_med       = case when p_dados ? 'preco_emb_med'       then (p_dados ->> 'preco_emb_med')::numeric        else i.preco_emb_med end,
        preco_emb_max       = case when p_dados ? 'preco_emb_max'       then (p_dados ->> 'preco_emb_max')::numeric        else i.preco_emb_max end,
        preco_un_min        = case when p_dados ? 'preco_un_min'        then (p_dados ->> 'preco_un_min')::numeric         else i.preco_un_min end,
        preco_un_med        = case when p_dados ? 'preco_un_med'        then (p_dados ->> 'preco_un_med')::numeric         else i.preco_un_med end,
        preco_un_max        = case when p_dados ? 'preco_un_max'        then (p_dados ->> 'preco_un_max')::numeric         else i.preco_un_max end,
        confianca           = case when p_dados ? 'confianca'           then p_dados ->> 'confianca'                       else i.confianca end,
        estimativa          = case when p_dados ? 'estimativa'          then coalesce((p_dados ->> 'estimativa')::boolean, false) else i.estimativa end,
        fontes              = case when p_dados ? 'fontes'              then normalizar_fontes(coalesce(nullif(p_dados -> 'fontes', 'null'::jsonb), '[]'::jsonb)) else i.fontes end,
        preco_data          = case when p_dados ? 'preco_data'          then (p_dados ->> 'preco_data')::timestamptz       else i.preco_data end,
        "similar"           = case when p_dados ? 'similar'
                                   then case when jsonb_typeof(p_dados -> 'similar') = 'object' and (p_dados -> 'similar') ? 'fontes'
                                             then jsonb_set(p_dados -> 'similar', '{fontes}', normalizar_fontes(p_dados -> 'similar' -> 'fontes'))
                                             else nullif(p_dados -> 'similar', 'null'::jsonb) end
                                   else i."similar" end,
        tentativa           = p_tentativa
     where i.id = p_item_id;

    update orcamentos set pesquisa_heartbeat_em = now() where id = v_orc;
    return true;
end;
$$;

-- Encerra a pesquisa da tentativa vigente. p_status = 'concluida' ou 'falhou'. p_dados (opcional)
-- aceita total_min, total_med, total_max, tempo_ms, custo_usd, trace_url, pesquisa_erro.
-- Retorna false se a tentativa é velha (nada é alterado: descarte o resultado).
-- (o rascunho anterior chamava o 3º parâmetro de p_estado; create or replace não renomeia parâmetro)
drop function if exists finalizar_pesquisa(uuid, integer, text, jsonb);

create or replace function finalizar_pesquisa(p_id uuid, p_tentativa integer, p_status text,
                                              p_dados jsonb default '{}'::jsonb)
returns boolean
language plpgsql as $$
declare
    v_extras text[];
begin
    if p_status not in ('concluida', 'falhou') then
        raise exception 'status final inválido: %', p_status using errcode = '22023';
    end if;
    v_extras := array(select k from jsonb_object_keys(p_dados) k
                      where k <> all (array['total_min', 'total_med', 'total_max', 'tempo_ms',
                                            'custo_usd', 'trace_url', 'pesquisa_erro']));
    if cardinality(v_extras) > 0 then
        raise exception 'campos não permitidos em finalizar_pesquisa: %', v_extras using errcode = '22023';
    end if;

    perform 1 from orcamentos
     where id = p_id and status_pesquisa = 'pesquisando' and tentativa_pesquisa = p_tentativa
       for no key update;
    if not found then
        return false;
    end if;

    update orcamentos o set
        status_pesquisa = p_status,
        pesquisa_concluida_em = now(),
        pesquisa_heartbeat_em = now(),
        total_min     = case when p_dados ? 'total_min'     then (p_dados ->> 'total_min')::numeric   else o.total_min end,
        total_med     = case when p_dados ? 'total_med'     then (p_dados ->> 'total_med')::numeric   else o.total_med end,
        total_max     = case when p_dados ? 'total_max'     then (p_dados ->> 'total_max')::numeric   else o.total_max end,
        tempo_ms      = case when p_dados ? 'tempo_ms'      then (p_dados ->> 'tempo_ms')::integer    else o.tempo_ms end,
        custo_usd     = case when p_dados ? 'custo_usd'     then (p_dados ->> 'custo_usd')::numeric   else o.custo_usd end,
        trace_url     = case when p_dados ? 'trace_url'     then p_dados ->> 'trace_url'              else o.trace_url end,
        pesquisa_erro = case when p_dados ? 'pesquisa_erro' then p_dados ->> 'pesquisa_erro'          else o.pesquisa_erro end
     where o.id = p_id;
    return true;
end;
$$;

-- ---------------------------------------------------------------------------
-- Permissões e Realtime. Blocos condicionais: no Postgres local não existem os papéis
-- do Supabase nem a publicação supabase_realtime, e o arquivo continua rodando.
-- ---------------------------------------------------------------------------
alter table orcamentos      enable row level security;
alter table orcamento_itens enable row level security;
alter table cache_precos    enable row level security;
alter table fornecedores    enable row level security;

revoke execute on function criar_orcamento(uuid, text, jsonb, jsonb, jsonb) from public;
revoke execute on function reservar_pesquisa(uuid, integer, boolean) from public;
revoke execute on function renovar_pesquisa(uuid, integer) from public;
revoke execute on function gravar_resultado_item(uuid, integer, jsonb) from public;
revoke execute on function finalizar_pesquisa(uuid, integer, text, jsonb) from public;

do $$
declare
    f regprocedure;
    funcoes regprocedure[] := array[
        'criar_orcamento(uuid, text, jsonb, jsonb, jsonb)',
        'reservar_pesquisa(uuid, integer, boolean)',
        'renovar_pesquisa(uuid, integer)',
        'gravar_resultado_item(uuid, integer, jsonb)',
        'finalizar_pesquisa(uuid, integer, text, jsonb)']::regprocedure[];
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        revoke all on orcamentos, orcamento_itens, cache_precos, fornecedores from anon;
        grant select on orcamentos, orcamento_itens to anon;
        foreach f in array funcoes loop
            execute format('revoke execute on function %s from anon', f);
        end loop;
        drop policy if exists leitura_publica on orcamentos;
        create policy leitura_publica on orcamentos for select to anon using (true);
        drop policy if exists leitura_publica on orcamento_itens;
        create policy leitura_publica on orcamento_itens for select to anon using (true);
    end if;

    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        revoke all on orcamentos, orcamento_itens, cache_precos, fornecedores from authenticated;
        foreach f in array funcoes loop
            execute format('revoke execute on function %s from authenticated', f);
        end loop;
    end if;

    if exists (select 1 from pg_roles where rolname = 'service_role') then
        grant all on orcamentos, orcamento_itens, cache_precos, fornecedores to service_role;
        foreach f in array funcoes loop
            execute format('grant execute on function %s to service_role', f);
        end loop;
    end if;

    if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
        if not exists (select 1 from pg_publication_tables
                       where pubname = 'supabase_realtime' and tablename = 'orcamentos') then
            alter publication supabase_realtime add table orcamentos;
        end if;
        if not exists (select 1 from pg_publication_tables
                       where pubname = 'supabase_realtime' and tablename = 'orcamento_itens') then
            alter publication supabase_realtime add table orcamento_itens;
        end if;
    end if;
end;
$$;
