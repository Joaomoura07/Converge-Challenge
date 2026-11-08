-- Migração aditiva: preserva dados e atualiza também a RPC existente.
begin;
alter table public.orcamento_itens add column if not exists pesquisa_detalhes jsonb;
comment on column public.orcamento_itens.pesquisa_detalhes is
  'Consumo observado da última pesquisa do item; não é saldo da conta.';
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
commit;
