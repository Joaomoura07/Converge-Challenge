-- Verificação SOMENTE LEITURA, para rodar no SQL Editor do Supabase DEPOIS de aplicar 002_orcamentos.sql.
-- O SQL Editor mostra só o resultado da última consulta, por isso tudo vem numa tabela só:
--   secao | item | situacao ('ok' ou 'FALTA') | detalhe
-- Resultado esperado: nenhuma linha com situacao = 'FALTA'. A última linha traz o resumo.
-- Não altera nada (apenas SELECT em catálogos do sistema).

with
esperado_colunas(tabela, coluna) as (values
    ('fornecedores','id'),('fornecedores','nome'),('fornecedores','dominio'),('fornecedores','cep'),
    ('fornecedores','lat'),('fornecedores','lon'),('fornecedores','frete_base'),('fornecedores','rs_por_km'),
    ('fornecedores','pedido_minimo'),
    ('orcamentos','id'),('orcamentos','nome'),('orcamentos','cep'),('orcamentos','orcamento_cliente'),
    ('orcamentos','logistica'),('orcamentos','viabilidade'),('orcamentos','ganho'),
    ('orcamentos','status_pesquisa'),('orcamentos','pesquisa_iniciada_em'),('orcamentos','pesquisa_concluida_em'),
    ('orcamentos','pesquisa_erro'),('orcamentos','tentativa_pesquisa'),('orcamentos','pesquisa_heartbeat_em'),
    ('orcamentos','custo_usd'),('orcamentos','tempo_ms'),('orcamentos','trace_url'),('orcamentos','created_at'),
    ('orcamento_itens','id'),('orcamento_itens','orcamento_id'),('orcamento_itens','linha'),
    ('orcamento_itens','descricao'),('orcamento_itens','categoria'),('orcamento_itens','quantidade'),
    ('orcamento_itens','unidade'),('orcamento_itens','nivel'),('orcamento_itens','extras'),
    ('orcamento_itens','classificacao'),('orcamento_itens','status'),('orcamento_itens','produto_normalizado'),
    ('orcamento_itens','embalagem'),('orcamento_itens','unidade_preco'),('orcamento_itens','qtd_embalagens'),
    ('orcamento_itens','iteracoes'),
    ('orcamento_itens','preco_emb_min'),('orcamento_itens','preco_emb_med'),('orcamento_itens','preco_emb_max'),
    ('orcamento_itens','preco_un_min'),('orcamento_itens','preco_un_med'),('orcamento_itens','preco_un_max'),
    ('orcamento_itens','confianca'),('orcamento_itens','estimativa'),('orcamento_itens','pergunta'),
    ('orcamento_itens','motivo'),('orcamento_itens','fontes'),('orcamento_itens','similar'),
    ('orcamento_itens','imagem_url'),('orcamento_itens','preco_data'),('orcamento_itens','atualizado_em'),
    ('orcamento_itens','sugerido'),('orcamento_itens','sugestao_regra'),('orcamento_itens','sugestao_motivo'),
    ('orcamento_itens','origem_linhas'),('orcamento_itens','aceito'),('orcamento_itens','estimativa_consumo'),
    ('cache_precos','chave'),('cache_precos','descricao'),('cache_precos','ofertas'),('cache_precos','imagem_url'),('cache_precos','modelo'),('cache_precos','provedor'),('cache_precos','iteracoes'),('cache_precos','atualizado_em')
),
esperado_funcoes(nome) as (values
    ('reservar_pesquisa'),('gravar_resultado_item'),('finalizar_pesquisa'),('renovar_pesquisa'),('criar_orcamento')
),
tabelas(nome) as (values ('orcamentos'),('orcamento_itens'),('cache_precos'),('fornecedores')),

r1 as (
    select 1 as ord, '1. tabelas' as secao, t.nome as item,
           case when c.oid is not null then 'ok' else 'FALTA' end as situacao,
           case when c.oid is null then 'tabela não existe'
                when c.relrowsecurity then 'RLS ligado' else 'RLS DESLIGADO' end as detalhe
      from tabelas t
      left join pg_class c on c.relname = t.nome and c.relkind = 'r'
           and c.relnamespace = 'public'::regnamespace
),
r2 as (
    select 2, '2. colunas', e.tabela || '.' || e.coluna,
           case when i.column_name is not null then 'ok' else 'FALTA' end,
           coalesce(i.data_type || case when i.udt_name = '_int4' then ' (int[])' else '' end, 'coluna não existe')
      from esperado_colunas e
      left join information_schema.columns i
        on i.table_schema = 'public' and i.table_name = e.tabela and i.column_name = e.coluna
),
r3 as (
    select 3, '3. funções', f.nome,
           case when p.oid is not null then 'ok' else 'FALTA' end,
           coalesce(pg_get_function_identity_arguments(p.oid), 'função não existe')
      from esperado_funcoes f
      left join pg_proc p on p.proname = f.nome and p.pronamespace = 'public'::regnamespace
),
r3b as (  -- permissões de execução: só service_role (e o dono) devem poder chamar o protocolo
    select 3, '3. funções (permissão)', f.nome,
           case when has_function_privilege('service_role', p.oid, 'execute')
                 and not has_function_privilege('anon', p.oid, 'execute')
                 and not has_function_privilege('authenticated', p.oid, 'execute')
                then 'ok' else 'FALTA' end,
           'service_role=' || has_function_privilege('service_role', p.oid, 'execute')
           || ' anon=' || has_function_privilege('anon', p.oid, 'execute')
           || ' authenticated=' || has_function_privilege('authenticated', p.oid, 'execute')
      from esperado_funcoes f
      join pg_proc p on p.proname = f.nome and p.pronamespace = 'public'::regnamespace
),
r4 as (  -- políticas RLS: leitura pública (anon) só em orcamentos e orcamento_itens
    select 4, '4. políticas RLS', x.tabela || ' / leitura_publica (anon, select)',
           case when pol.policyname is not null then 'ok' else 'FALTA' end,
           coalesce(pol.cmd || ' para ' || pol.roles::text, 'política não existe')
      from (values ('orcamentos'),('orcamento_itens')) x(tabela)
      left join pg_policies pol
        on pol.schemaname = 'public' and pol.tablename = x.tabela and pol.policyname = 'leitura_publica'
),
r4b as (  -- nenhuma política inesperada (cache_precos e fornecedores não têm acesso público)
    select 4, '4. políticas RLS', 'políticas além das 2 esperadas',
           case when count(*) = 0 then 'ok' else 'FALTA' end,
           coalesce(string_agg(tablename || '.' || policyname, ', '), 'nenhuma')
      from pg_policies
     where schemaname = 'public'
       and tablename in ('orcamentos','orcamento_itens','cache_precos','fornecedores')
       and not (policyname = 'leitura_publica' and tablename in ('orcamentos','orcamento_itens'))
),
r4c as (  -- anon não tem privilégio nas tabelas que não são de acompanhamento
    select 4, '4. políticas RLS', 'anon sem acesso a cache_precos e fornecedores',
           case when not has_table_privilege('anon', 'public.cache_precos', 'select')
                 and not has_table_privilege('anon', 'public.fornecedores', 'select')
                 and not has_table_privilege('anon', 'public.orcamentos', 'insert')
                 and not has_table_privilege('anon', 'public.orcamentos', 'update')
                 and not has_table_privilege('anon', 'public.orcamento_itens', 'delete')
                then 'ok' else 'FALTA' end,
           'anon só deve ler orcamentos e orcamento_itens'
),
r5 as (  -- Realtime
    select 5, '5. publicação supabase_realtime', t.nome,
           case when pt.tablename is not null then 'ok' else 'FALTA' end,
           case when pt.tablename is not null then 'na publicação' else 'fora da publicação' end
      from (values ('orcamentos'),('orcamento_itens')) t(nome)
      left join pg_publication_tables pt
        on pt.pubname = 'supabase_realtime' and pt.schemaname = 'public' and pt.tablename = t.nome
),
todas as (
    select * from r1 union all select * from r2 union all select * from r3 union all select * from r3b
    union all select * from r4 union all select * from r4b union all select * from r4c union all select * from r5
)
select secao, item, situacao, detalhe
  from (
    select ord, secao, item, situacao, detalhe from todas
    union all
    select 9, '9. RESUMO',
           count(*) filter (where situacao = 'ok') || ' ok / ' || count(*) filter (where situacao <> 'ok') || ' FALTA',
           case when count(*) filter (where situacao <> 'ok') = 0 then 'ok' else 'FALTA' end,
           case when count(*) filter (where situacao <> 'ok') = 0
                then 'tudo certo' else 'veja as linhas com FALTA acima' end
      from todas
  ) z
 order by ord, (situacao = 'ok'), item;
