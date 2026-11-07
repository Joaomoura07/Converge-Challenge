-- Orçamentista Autônomo: SQL único da Fatia A (responsável: Samuel).
-- Tabelas: orcamentos, orcamento_itens, cache_precos, fornecedores.
-- Rode no SQL Editor do Supabase (ou é aplicado no Postgres local via docker-compose).
-- Pode ser rodado mais de uma vez (idempotente).
--
-- Modelo de acesso (combinado com Samuel em 07/11/2026):
--   * Escrita: só a API, com a chave de serviço (service_role). Ninguém grava pelo navegador.
--   * Leitura de orcamentos e orcamento_itens: chave pública (anon), para o Realtime.
--     O orcamento_id é um UUID gerado na tela e impossível de adivinhar, mas a política
--     abaixo NÃO filtra por dono: quem tiver a chave anon consegue listar tudo.
--     Aceitável só para a demo com dados sintéticos.
--   * cache_precos e fornecedores: sem acesso público, só pela API.

create extension if not exists pgcrypto;  -- gen_random_uuid() em Postgres < 13

-- ---------------------------------------------------------------------------
-- Utilitário: mantém updated_at
-- ---------------------------------------------------------------------------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

-- Valida o jsonb de fontes: lista de {loja, dominio, url http(s), preco_embalagem >= 0}.
-- Lista vazia é válida aqui; a exigência de fonte para preço está no check do item.
create or replace function fontes_validas(f jsonb) returns boolean
language sql immutable as $$
    select case when jsonb_typeof(f) <> 'array' then false
    else not exists (
        select 1 from jsonb_array_elements(f) e
        where case when jsonb_typeof(e) <> 'object' then true
                   else coalesce(btrim(e ->> 'loja'), '') = ''
                     or coalesce(btrim(e ->> 'dominio'), '') = ''
                     or coalesce(e ->> 'url', '') !~ '^https?://[^[:space:]]+$'
                     or case when jsonb_typeof(e -> 'preco_embalagem') = 'number'
                             then (e ->> 'preco_embalagem')::numeric < 0
                             else true end
              end)
    end;
$$;

-- ---------------------------------------------------------------------------
-- orcamentos: um por envio. O id vem da tela (UUID v4) e serve de chave de reenvio.
-- ---------------------------------------------------------------------------
create table if not exists orcamentos (
    id                uuid primary key,
    estado            text not null default 'recebido'
                      check (estado in ('recebido', 'pesquisando', 'concluido', 'erro')),
    nome              text not null check (length(btrim(nome)) > 0),
    cep               text not null check (cep ~ '^[0-9]{8}$'),
    orcamento_cliente numeric(14, 2) not null check (orcamento_cliente > 0),  -- em reais
    origem            jsonb not null default '{}'::jsonb,   -- {tipo, arquivo, formato, software}
    hash_conteudo     text not null,                        -- resumo do envio, detecta conflito no reenvio
    qtd_itens         integer not null check (qtd_itens > 0),

    -- Execução única da pesquisa (B): ver iniciar_pesquisa(). `tentativa_pesquisa` é o número
    -- da execução atual; toda gravação da B leva esse número e é recusada se estiver velho.
    tentativa_pesquisa    integer not null default 0,
    pesquisa_iniciada_em  timestamptz,
    pesquisa_heartbeat_em timestamptz,   -- última atividade da execução atual
    pesquisa_concluida_em timestamptz,
    erro_mensagem         text,

    -- Totais (escritos pela B ao fechar os itens)
    total_min         numeric(14, 2),
    total_med         numeric(14, 2),
    total_max         numeric(14, 2),

    -- Resultado da C (formato dos JSON ainda a confirmar com João)
    logistica         jsonb,   -- {estrategia, lojas, frete_total, economia_estimada}
    viabilidade       jsonb,   -- {cabe, falta, sugestoes}

    -- Ganho na tela (E10)
    tempo_ms          integer,
    custo_usd         numeric(12, 6),
    trace_url         text,    -- link do trace no Langfuse

    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

create index if not exists orcamentos_created_at_idx on orcamentos (created_at desc);
create index if not exists orcamentos_estado_idx on orcamentos (estado);

drop trigger if exists orcamentos_updated_at on orcamentos;
create trigger orcamentos_updated_at before update on orcamentos
    for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- orcamento_itens: um por item. Realtime acompanha por orcamento_id.
-- ---------------------------------------------------------------------------
create table if not exists orcamento_itens (
    id                 uuid primary key default gen_random_uuid(),
    orcamento_id       uuid not null references orcamentos (id) on delete cascade,

    -- Entrada (A). id_linha é o identificador estável da linha na tabela da tela.
    id_linha           text not null,
    linha              integer,                 -- linha/página de origem no arquivo
    categoria          text,
    descricao_original text not null check (length(btrim(descricao_original)) > 0),
    descricao          text not null check (length(btrim(descricao)) > 0),  -- valor revisado, é o que a B pesquisa
    quantidade         numeric(14, 4) not null check (quantidade > 0),
    unidade            text not null,           -- lista de unidades validada pela API, não pelo banco
    nivel              text,
    origem_item        text check (origem_item in ('arquivo', 'manual')),
    extras             jsonb not null default '{}'::jsonb,
    sugestao_aceita_id text,                    -- auditoria: sugestão E1/E2 que originou/alterou a linha

    -- Classificação de negócio (A decide, B confirma, C lê). Separada do status.
    classificacao      text not null check (classificacao in ('definido', 'generico')),

    -- Processamento (B). Começa em 'buscando'.
    status             text not null default 'buscando'
                       check (status in ('buscando', 'definido', 'pendente_especificacao',
                                         'nao_encontrado', 'erro')),
    produto            text,                    -- nome normalizado
    marca              text,
    pergunta           text,                    -- pergunta ao arquiteto (E5)
    resposta           text,
    embalagem          text,                    -- ex.: "lata 18 L"
    qtd_embalagens     integer check (qtd_embalagens is null or qtd_embalagens >= 0),
    preco_emb_min      numeric(14, 2) check (preco_emb_min is null or preco_emb_min >= 0),
    preco_emb_med      numeric(14, 2) check (preco_emb_med is null or preco_emb_med >= 0),
    preco_emb_max      numeric(14, 2) check (preco_emb_max is null or preco_emb_max >= 0),
    confianca          text check (confianca in ('alta', 'media', 'baixa')),
    estimativa         boolean not null default false,   -- true = faixa estimada de item genérico
    fontes             jsonb not null default '[]'::jsonb,  -- [{loja, dominio, url, preco_embalagem}]
    imagem             text,
    preco_data         date,                    -- data do preço quando veio de cache vencido
    erro_mensagem      text,
    tentativa          integer,                 -- execução da pesquisa que gravou o resultado

    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),

    unique (orcamento_id, id_linha),
    constraint preco_min_max_ck check (preco_emb_min is null or preco_emb_max is null or preco_emb_min <= preco_emb_max),
    constraint fontes_validas_ck check (fontes_validas(fontes)),
    -- "Nunca preço sem fonte": qualquer preço (mín, médio ou máx) exige fonte válida,
    -- inclusive quando estimativa = true. Grave preços e fontes no mesmo UPDATE.
    constraint preco_exige_fonte_ck check ((preco_emb_min is null and preco_emb_med is null and preco_emb_max is null)
           or jsonb_array_length(fontes) > 0)
);

create index if not exists orcamento_itens_orcamento_idx on orcamento_itens (orcamento_id);
create index if not exists orcamento_itens_status_idx on orcamento_itens (orcamento_id, status);

drop trigger if exists orcamento_itens_updated_at on orcamento_itens;
create trigger orcamento_itens_updated_at before update on orcamento_itens
    for each row execute function set_updated_at();

-- Eventos de DELETE do Realtime só trazem a chave primária no padrão; com 'full' trazem o orcamento_id.
alter table orcamento_itens replica identity full;

-- ---------------------------------------------------------------------------
-- cache_precos (B): não pesquisar o mesmo produto duas vezes. Vencido ainda serve de reserva.
-- ---------------------------------------------------------------------------
create table if not exists cache_precos (
    chave      text primary key,                 -- produto normalizado (regra de normalização é da B)
    resultado  jsonb not null,
    criado_em  timestamptz not null default now(),
    expira_em  timestamptz not null default (now() + interval '7 days')
);

create index if not exists cache_precos_expira_idx on cache_precos (expira_em);

-- ---------------------------------------------------------------------------
-- fornecedores: esquema pela A, cadastro pela C (mesmas redes que a busca encontra)
-- ---------------------------------------------------------------------------
create table if not exists fornecedores (
    id             uuid primary key default gen_random_uuid(),
    nome           text not null,                -- ex.: "Leroy Merlin Recife"
    dominio        text not null,                -- ex.: "leroymerlin.com.br", casa com fontes[].dominio
    site           text,
    cep            text check (cep is null or cep ~ '^[0-9]{8}$'),
    cidade         text,
    latitude       numeric(9, 6),
    longitude      numeric(9, 6),
    frete_base     numeric(10, 2) check (frete_base is null or frete_base >= 0),
    frete_por_km   numeric(10, 2) check (frete_por_km is null or frete_por_km >= 0),
    pedido_minimo  numeric(10, 2) check (pedido_minimo is null or pedido_minimo >= 0),
    ativo          boolean not null default true,
    created_at     timestamptz not null default now(),
    unique (dominio, nome)
);

create index if not exists fornecedores_dominio_idx on fornecedores (dominio);

-- ---------------------------------------------------------------------------
-- criar_orcamento: grava orçamento e itens numa transação e trata o reenvio.
--   p_obra  = {nome, cep, orcamento_cliente}
--   p_itens = [{id_linha, linha, categoria, descricao_original, descricao, quantidade,
--               unidade, nivel, origem_item, extras, sugestao_aceita_id, classificacao}]
-- Retorna {resultado: 'criado' | 'existente' | 'conflito', orcamento_id, estado}.
--   criado    -> itens gravados com status 'buscando'
--   existente -> mesmo id e mesmo hash (reenvio): nada é gravado, devolve o estado atual
--   conflito  -> mesmo id com hash diferente: nada é gravado (a API responde 409)
-- Duas chamadas simultâneas com o mesmo id: a segunda espera a primeira confirmar e cai em 'existente'.
-- Qualquer erro (item inválido, por exemplo) desfaz o orçamento inteiro.
-- ---------------------------------------------------------------------------
create or replace function criar_orcamento(
    p_id    uuid,
    p_hash  text,
    p_obra  jsonb,
    p_origem jsonb,
    p_itens jsonb
) returns jsonb
language plpgsql as $$
declare
    v_qtd      integer;
    v_inseridos integer;
    v_hash     text;
    v_estado   text;
begin
    if jsonb_typeof(p_itens) is distinct from 'array' or jsonb_array_length(p_itens) = 0 then
        raise exception 'lista de itens vazia' using errcode = '22023';
    end if;
    v_qtd := jsonb_array_length(p_itens);

    insert into orcamentos (id, nome, cep, orcamento_cliente, origem, hash_conteudo, qtd_itens)
    values (p_id,
            p_obra ->> 'nome',
            p_obra ->> 'cep',
            (p_obra ->> 'orcamento_cliente')::numeric,
            coalesce(p_origem, '{}'::jsonb),
            p_hash,
            v_qtd)
    on conflict (id) do nothing;
    get diagnostics v_inseridos = row_count;

    if v_inseridos = 0 then
        -- Já existe (ou outra transação acabou de criar: o on conflict espera ela confirmar).
        select hash_conteudo, estado into v_hash, v_estado from orcamentos where id = p_id;
        return jsonb_build_object(
            'resultado', case when v_hash = p_hash then 'existente' else 'conflito' end,
            'orcamento_id', p_id,
            'estado', v_estado);
    end if;

    insert into orcamento_itens (orcamento_id, id_linha, linha, categoria, descricao_original,
                                 descricao, quantidade, unidade, nivel, origem_item, extras,
                                 sugestao_aceita_id, classificacao, status)
    select p_id, i.id_linha, i.linha, i.categoria,
           coalesce(i.descricao_original, i.descricao), i.descricao, i.quantidade, i.unidade,
           i.nivel, i.origem_item, coalesce(i.extras, '{}'::jsonb), i.sugestao_aceita_id,
           i.classificacao, 'buscando'
    from jsonb_to_recordset(p_itens) as i(
        id_linha text, linha integer, categoria text, descricao_original text, descricao text,
        quantidade numeric, unidade text, nivel text, origem_item text, extras jsonb,
        sugestao_aceita_id text, classificacao text);

    return jsonb_build_object('resultado', 'criado', 'orcamento_id', p_id, 'estado', 'recebido');
end;
$$;

-- ---------------------------------------------------------------------------
-- Pesquisa (A e B): uma execução por vez, com empréstimo (lease) e número de tentativa.
--
-- Como funciona:
--   1. A API chama iniciar_pesquisa(id). Se ganhou, recebe o número da tentativa (1, 2, ...);
--      se outra execução está ativa ou o orçamento já concluiu, recebe NULL e não pesquisa.
--   2. A pesquisa (B) grava cada item com gravar_resultado_item(..., tentativa, ...) e, no fim,
--      chama finalizar_pesquisa(..., tentativa, ...). Toda gravação renova o empréstimo.
--   3. Se a execução morrer (timeout da Vercel, queda), o empréstimo vence depois de
--      p_expira_s segundos sem atividade e a próxima chamada recebe a tentativa seguinte.
--   4. Uma execução antiga que continue viva depois disso tem as gravações RECUSADAS
--      (a função devolve false), porque o número dela não é mais o da tentativa atual.
--
-- O prazo é só para a execução morta ser retomada; quem protege os dados é o número da
-- tentativa. Por isso o prazo pode ser maior que o limite de duração da função na Vercel.
-- ---------------------------------------------------------------------------
drop function if exists iniciar_pesquisa(uuid, integer);

create or replace function iniciar_pesquisa(p_id uuid, p_expira_s integer default 180)
returns integer   -- número da tentativa, ou NULL se não é a sua vez
language plpgsql as $$
declare
    v_tentativa integer;
begin
    update orcamentos
       set estado = 'pesquisando',
           tentativa_pesquisa = tentativa_pesquisa + 1,
           pesquisa_iniciada_em = now(),
           pesquisa_heartbeat_em = now(),
           pesquisa_concluida_em = null,
           erro_mensagem = null
     where id = p_id
       and (estado in ('recebido', 'erro')
            or (estado = 'pesquisando'
                and coalesce(pesquisa_heartbeat_em, pesquisa_iniciada_em)
                    < now() - make_interval(secs => p_expira_s)))
    returning tentativa_pesquisa into v_tentativa;
    return v_tentativa;
end;
$$;

-- Renova o empréstimo sem gravar nada (para um item muito demorado). false = tentativa velha.
create or replace function renovar_pesquisa(p_id uuid, p_tentativa integer)
returns boolean
language plpgsql as $$
declare
    v_id uuid;
begin
    update orcamentos set pesquisa_heartbeat_em = now()
     where id = p_id and estado = 'pesquisando' and tentativa_pesquisa = p_tentativa
    returning id into v_id;
    return v_id is not null;
end;
$$;

-- Grava o resultado de UM item, preços e fontes no mesmo UPDATE, só se a tentativa for a atual.
-- p_dados aceita apenas estas chaves (qualquer outra gera erro); chave ausente = campo intacto,
-- chave com null = limpa o campo:
--   status, classificacao, produto, marca, pergunta, resposta, embalagem, qtd_embalagens,
--   preco_emb_min, preco_emb_med, preco_emb_max, confianca, estimativa, fontes, imagem,
--   preco_data, erro_mensagem
-- Retorna true se gravou; false se a tentativa é velha (o item não é alterado).
create or replace function gravar_resultado_item(p_item_id uuid, p_tentativa integer, p_dados jsonb)
returns boolean
language plpgsql as $$
declare
    v_extras text[];
    v_item   uuid;
begin
    v_extras := array(select k from jsonb_object_keys(p_dados) k
                      where k <> all (array['status', 'classificacao', 'produto', 'marca', 'pergunta',
                                            'resposta', 'embalagem', 'qtd_embalagens', 'preco_emb_min',
                                            'preco_emb_med', 'preco_emb_max', 'confianca', 'estimativa',
                                            'fontes', 'imagem', 'preco_data', 'erro_mensagem']));
    if cardinality(v_extras) > 0 then
        raise exception 'campos não permitidos em gravar_resultado_item: %', v_extras using errcode = '22023';
    end if;

    update orcamento_itens i set
        status         = case when p_dados ? 'status'         then p_dados ->> 'status'                       else i.status end,
        classificacao  = case when p_dados ? 'classificacao'  then p_dados ->> 'classificacao'                else i.classificacao end,
        produto        = case when p_dados ? 'produto'        then p_dados ->> 'produto'                      else i.produto end,
        marca          = case when p_dados ? 'marca'          then p_dados ->> 'marca'                        else i.marca end,
        pergunta       = case when p_dados ? 'pergunta'       then p_dados ->> 'pergunta'                     else i.pergunta end,
        resposta       = case when p_dados ? 'resposta'       then p_dados ->> 'resposta'                     else i.resposta end,
        embalagem      = case when p_dados ? 'embalagem'      then p_dados ->> 'embalagem'                    else i.embalagem end,
        qtd_embalagens = case when p_dados ? 'qtd_embalagens' then (p_dados ->> 'qtd_embalagens')::integer   else i.qtd_embalagens end,
        preco_emb_min  = case when p_dados ? 'preco_emb_min'  then (p_dados ->> 'preco_emb_min')::numeric    else i.preco_emb_min end,
        preco_emb_med  = case when p_dados ? 'preco_emb_med'  then (p_dados ->> 'preco_emb_med')::numeric    else i.preco_emb_med end,
        preco_emb_max  = case when p_dados ? 'preco_emb_max'  then (p_dados ->> 'preco_emb_max')::numeric    else i.preco_emb_max end,
        confianca      = case when p_dados ? 'confianca'      then p_dados ->> 'confianca'                    else i.confianca end,
        estimativa     = case when p_dados ? 'estimativa'     then coalesce((p_dados ->> 'estimativa')::boolean, false) else i.estimativa end,
        fontes         = case when p_dados ? 'fontes'         then coalesce(nullif(p_dados -> 'fontes', 'null'::jsonb), '[]'::jsonb) else i.fontes end,
        imagem         = case when p_dados ? 'imagem'         then p_dados ->> 'imagem'                       else i.imagem end,
        preco_data     = case when p_dados ? 'preco_data'     then (p_dados ->> 'preco_data')::date           else i.preco_data end,
        erro_mensagem  = case when p_dados ? 'erro_mensagem'  then p_dados ->> 'erro_mensagem'                else i.erro_mensagem end,
        tentativa      = p_tentativa
      from orcamentos o
     where i.id = p_item_id
       and o.id = i.orcamento_id
       and o.estado = 'pesquisando'
       and o.tentativa_pesquisa = p_tentativa
    returning i.id into v_item;

    if v_item is null then
        return false;
    end if;
    update orcamentos set pesquisa_heartbeat_em = now()
     where id = (select orcamento_id from orcamento_itens where id = v_item);
    return true;
end;
$$;

-- Encerra a pesquisa da tentativa atual. p_estado = 'concluido' ou 'erro'. p_dados (opcional) aceita
-- total_min, total_med, total_max, tempo_ms, custo_usd, trace_url, erro_mensagem.
-- Retorna false se a tentativa é velha (nada é alterado).
create or replace function finalizar_pesquisa(p_id uuid, p_tentativa integer, p_estado text,
                                              p_dados jsonb default '{}'::jsonb)
returns boolean
language plpgsql as $$
declare
    v_id     uuid;
    v_extras text[];
begin
    if p_estado not in ('concluido', 'erro') then
        raise exception 'estado final inválido: %', p_estado using errcode = '22023';
    end if;
    v_extras := array(select k from jsonb_object_keys(p_dados) k
                      where k <> all (array['total_min', 'total_med', 'total_max', 'tempo_ms',
                                            'custo_usd', 'trace_url', 'erro_mensagem']));
    if cardinality(v_extras) > 0 then
        raise exception 'campos não permitidos em finalizar_pesquisa: %', v_extras using errcode = '22023';
    end if;

    update orcamentos o set
        estado = p_estado,
        pesquisa_concluida_em = now(),
        pesquisa_heartbeat_em = now(),
        total_min     = case when p_dados ? 'total_min'     then (p_dados ->> 'total_min')::numeric     else o.total_min end,
        total_med     = case when p_dados ? 'total_med'     then (p_dados ->> 'total_med')::numeric     else o.total_med end,
        total_max     = case when p_dados ? 'total_max'     then (p_dados ->> 'total_max')::numeric     else o.total_max end,
        tempo_ms      = case when p_dados ? 'tempo_ms'      then (p_dados ->> 'tempo_ms')::integer      else o.tempo_ms end,
        custo_usd     = case when p_dados ? 'custo_usd'     then (p_dados ->> 'custo_usd')::numeric     else o.custo_usd end,
        trace_url     = case when p_dados ? 'trace_url'     then p_dados ->> 'trace_url'                else o.trace_url end,
        erro_mensagem = case when p_dados ? 'erro_mensagem' then p_dados ->> 'erro_mensagem'           else o.erro_mensagem end
     where o.id = p_id and o.estado = 'pesquisando' and o.tentativa_pesquisa = p_tentativa
    returning o.id into v_id;
    return v_id is not null;
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
revoke execute on function iniciar_pesquisa(uuid, integer) from public;
revoke execute on function renovar_pesquisa(uuid, integer) from public;
revoke execute on function gravar_resultado_item(uuid, integer, jsonb) from public;
revoke execute on function finalizar_pesquisa(uuid, integer, text, jsonb) from public;

do $$
declare
    f regprocedure;
    funcoes regprocedure[] := array[
        'criar_orcamento(uuid, text, jsonb, jsonb, jsonb)',
        'iniciar_pesquisa(uuid, integer)',
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
