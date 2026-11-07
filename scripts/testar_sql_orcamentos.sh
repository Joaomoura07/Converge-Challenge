#!/usr/bin/env bash
# Testa sql/002_orcamentos.sql num Postgres descartável (Docker). Rode da raiz do repositório:
#   docker run -d --name pgtest -e POSTGRES_PASSWORD=postgres postgres:16-alpine
#   MSYS_NO_PATHCONV=1 bash scripts/testar_sql_orcamentos.sh
# Cobre: criação limpa (2x), colunas do contrato B/C, gravação, falha parcial, reenvio, conflito,
# concorrência, fontes, escrita exata de B e C, protocolo de tentativa (inclusive a troca de
# tentativa DURANTE a gravação, com intercalamento controlado), permissões, migração do
# rascunho anterior e um teste de mutação que prova que a corrida controlada pega a regressão.
set -u
CT=${PG_CONTAINER:-pgtest}
D=base
ok=0; falhou=0

check() { # descrição, esperado, obtido
  if [ "$2" == "$3" ]; then echo "OK    $1"; ok=$((ok+1)); else echo "FALHA $1 (esperado '$2', obtido '$3')"; falhou=$((falhou+1)); fi
}
# Roda SQL vindo do argumento (via stdin, sem problemas de aspas) no banco $D. Mostra saída e erros.
Q()  { printf '%s\n' "$1" | docker exec -i "$CT" psql -U postgres -d "$D" -v ON_ERROR_STOP=1 -tA 2>&1; }
# Só o código de saída (0 = ok, !=0 = erro SQL).
Qs() { printf '%s\n' "$1" | docker exec -i "$CT" psql -U postgres -d "$D" -v ON_ERROR_STOP=1 -tA >/dev/null 2>&1; }
# Última linha da saída (para comandos com SET ou BEGIN antes).
Ql() { Q "$1" | tail -1; }
novo_banco() { docker exec "$CT" psql -U postgres -c "drop database if exists $1" -c "create database $1" >/dev/null 2>&1; }
aplicar() { docker exec -i "$CT" psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -q < "${2:-sql/002_orcamentos.sql}" >/dev/null 2>&1; }

OBRA='{"nome":"Reforma Apto","cep":"51020000","orcamento_cliente":20000.00}'
FONTE='[{"loja":"Leroy Merlin","dominio":"leroymerlin.com.br","url":"https://www.leroymerlin.com.br/p/1","preco_embalagem":455.9,"embalagem":"lata 18 L"}]'
ITENS='[{"id_linha":"l1","linha":1,"categoria":"Pintura","descricao":"Tinta acrílica Suvinil Toque de Seda 18L","quantidade":180,"unidade":"m2","classificacao":"definido","origem_item":"arquivo"},
        {"id_linha":"l2","linha":2,"descricao":"tinta branca","quantidade":2,"unidade":"un","classificacao":"pendente","origem_item":"manual"}]'
criar() { Ql "select criar_orcamento('$1','$2','$OBRA','{\"tipo\":\"manual\"}','${3:-$ITENS}')::jsonb ->> 'resultado'"; }
reservar() { Ql "select reservar_pesquisa('$1'${2:+, $2}${3:+, $3})::jsonb ->> 'tentativa'"; }
gravar() { Ql "select gravar_resultado_item('$1', $2, '$3'::jsonb)"; }
gravar_err() { Q "select gravar_resultado_item('$1', $2, '$3'::jsonb)"; }
item_de() { Ql "select id from orcamento_itens where orcamento_id='$1' and id_linha='$2'"; }
envelhecer() { Qs "update orcamentos set pesquisa_heartbeat_em = now() - interval '10 minutes' where id='$1'"; }

# ===========================================================================
echo "## 1. Criação limpa, duas vezes"
novo_banco base
aplicar base; check "aplica o SQL (1ª vez)" 0 $?
aplicar base; check "aplica o SQL (2ª vez, idempotente)" 0 $?
check "4 tabelas criadas" 4 "$(Ql "select count(*) from information_schema.tables where table_schema='public' and table_name in ('orcamentos','orcamento_itens','cache_precos','fornecedores')")"
check "RLS ligado nas 4" 4 "$(Ql "select count(*) from pg_class where relname in ('orcamentos','orcamento_itens','cache_precos','fornecedores') and relrowsecurity")"
check "5 funções do protocolo" 5 "$(Ql "select count(*) from pg_proc where proname in ('criar_orcamento','reservar_pesquisa','renovar_pesquisa','gravar_resultado_item','finalizar_pesquisa')")"
check "função antiga iniciar_pesquisa não existe" 0 "$(Ql "select count(*) from pg_proc where proname='iniciar_pesquisa'")"

echo "## 2. Colunas exatamente como em CONTRATOS-B-C.md (tipo|precisão|escala|nulo|default)"
col() { Ql "select data_type||'|'||coalesce(numeric_precision::text,'')||'|'||coalesce(numeric_scale::text,'')||'|'||is_nullable||'|'||coalesce(column_default,'') from information_schema.columns where table_schema='public' and table_name='$1' and column_name='$2'"; }
check "itens.status default buscando"       "text|||NO|'buscando'::text"           "$(col orcamento_itens status)"
check "itens.produto_normalizado text"      "text|||YES|"                          "$(col orcamento_itens produto_normalizado)"
check "itens.imagem_url text"               "text|||YES|"                          "$(col orcamento_itens imagem_url)"
check "itens.unidade_preco text"            "text|||YES|"                          "$(col orcamento_itens unidade_preco)"
check "itens.motivo text"                   "text|||YES|"                          "$(col orcamento_itens motivo)"
check "itens.qtd_embalagens int"            "integer|32|0|YES|"                    "$(col orcamento_itens qtd_embalagens)"
check "itens.iteracoes int default 0"       "integer|32|0|NO|0"                    "$(col orcamento_itens iteracoes)"
for c in preco_emb_min preco_emb_med preco_emb_max; do check "itens.$c numeric(12,2)" "numeric|12|2|YES|" "$(col orcamento_itens $c)"; done
for c in preco_un_min preco_un_med preco_un_max;    do check "itens.$c numeric(12,4)" "numeric|12|4|YES|" "$(col orcamento_itens $c)"; done
check "itens.estimativa boolean default false" "boolean|||NO|false"                "$(col orcamento_itens estimativa)"
check "itens.fontes jsonb default []"       "jsonb|||NO|'[]'::jsonb"               "$(col orcamento_itens fontes)"
check "itens.preco_data timestamptz"        "timestamp with time zone|||YES|"      "$(col orcamento_itens preco_data)"
check "itens.atualizado_em default now()"   "timestamp with time zone|||NO|now()"  "$(col orcamento_itens atualizado_em)"
check "itens.similar jsonb (C)"             "jsonb|||YES|"                         "$(col orcamento_itens similar)"
check "itens.estimativa_consumo separada da estimativa" "boolean|||NO|false"       "$(col orcamento_itens estimativa_consumo)"
check "orcamentos.status_pesquisa default pendente" "text|||NO|'pendente'::text"   "$(col orcamentos status_pesquisa)"
check "orcamentos.pesquisa_iniciada_em"     "timestamp with time zone|||YES|"      "$(col orcamentos pesquisa_iniciada_em)"
check "orcamentos.pesquisa_concluida_em"    "timestamp with time zone|||YES|"      "$(col orcamentos pesquisa_concluida_em)"
check "orcamentos.pesquisa_erro text"       "text|||YES|"                          "$(col orcamentos pesquisa_erro)"
check "orcamentos.orcamento_cliente numeric(14,2)" "numeric|14|2|NO|"              "$(col orcamentos orcamento_cliente)"
check "cache.imagem_url / atualizado_em"    "text|||YES||timestamp with time zone|||NO|now()" "$(col cache_precos imagem_url)|$(col cache_precos atualizado_em)"
for c in frete_base rs_por_km pedido_minimo; do check "fornecedores.$c numeric obrigatório" "numeric|||NO|" "$(col fornecedores $c)"; done
check "fornecedores.cep/dominio/nome obrigatórios" "NO|NO|NO" "$(Ql "select string_agg(is_nullable, '|' order by column_name desc) from information_schema.columns where table_name='fornecedores' and column_name in ('cep','dominio','nome')")"
check "fornecedores.lat/lon/ativo opcionais (ativo default true)" "YES|YES|NO|true" "$(Ql "select (select is_nullable from information_schema.columns where table_name='fornecedores' and column_name='lat')||'|'||(select is_nullable from information_schema.columns where table_name='fornecedores' and column_name='lon')||'|'||(select is_nullable from information_schema.columns where table_name='fornecedores' and column_name='ativo')||'|'||(select column_default from information_schema.columns where table_name='fornecedores' and column_name='ativo')")"
check "colunas antigas sumiram (estado, produto, imagem, updated_at)" 0 "$(Ql "select count(*) from information_schema.columns where table_schema='public' and ((table_name='orcamentos' and column_name in ('estado','erro_mensagem','updated_at')) or (table_name='orcamento_itens' and column_name in ('produto','imagem','updated_at','erro_mensagem')))")"

echo "## 3. Normalização de domínio"
nd() { Ql "select normalizar_dominio('$1')"; }
check "https://WWW.LeroyMerlin.com.br/p/1" leroymerlin.com.br "$(nd 'https://WWW.LeroyMerlin.com.br/p/1')"
check "www.telhanorte.com.br" telhanorte.com.br "$(nd 'www.telhanorte.com.br')"
check "cec.com.br:8080/x?y=1" cec.com.br "$(nd 'cec.com.br:8080/x?y=1')"
check "  Leroymerlin.com.br  " leroymerlin.com.br "$(nd '  Leroymerlin.com.br  ')"
check "vazio vira NULL" "" "$(nd '')"

echo "## 4. criar_orcamento: gravação, reenvio, conflito, falha parcial"
ID1=11111111-1111-4111-8111-111111111111
check "criar → criado" criado "$(criar $ID1 hashA)"
check "itens gravados em 'buscando'" "2|2" "$(Ql "select count(*), count(*) filter (where status='buscando') from orcamento_itens where orcamento_id='$ID1'")"
check "classificacao separada do status (definido|pendente)" "definido|pendente" "$(Ql "select string_agg(classificacao, '|' order by linha) from orcamento_itens where orcamento_id='$ID1'")"
check "status_pesquisa começa 'pendente'" pendente "$(Ql "select status_pesquisa from orcamentos where id='$ID1'")"
check "descricao_original preenchida por padrão" "Tinta acrílica Suvinil Toque de Seda 18L" "$(Ql "select descricao_original from orcamento_itens where id_linha='l1' and orcamento_id='$ID1'")"
check "orcamento_cliente em reais, com centavos" "20000.00" "$(Ql "select orcamento_cliente from orcamentos where id='$ID1'")"
ID_C=12121212-1212-4121-8121-121212121212
Ql "select criar_orcamento('$ID_C','hC','{\"nome\":\"Casa\",\"cep\":\"01310100\",\"orcamento_cliente\":1234.56}','{}','$ITENS')" >/dev/null
check "CEP com zero à esquerda e centavos preservados" "01310100|1234.56" "$(Ql "select cep||'|'||orcamento_cliente from orcamentos where id='$ID_C'")"
check "reenvio (mesmo id e hash) → existente" existente "$(criar $ID1 hashA)"
check "reenvio não duplica itens" 2 "$(Ql "select count(*) from orcamento_itens where orcamento_id='$ID1'")"
check "mesmo id, hash diferente → conflito" conflito "$(criar $ID1 hashB)"
check "conflito não altera o original" "hashA|2" "$(Ql "select hash_conteudo||'|'||qtd_itens from orcamentos where id='$ID1'")"

ID2=22222222-2222-4222-8222-222222222222
BAD='[{"id_linha":"l1","linha":1,"descricao":"ok","quantidade":1,"unidade":"un","classificacao":"definido"},
      {"id_linha":"l2","linha":2,"descricao":null,"quantidade":1,"unidade":"un","classificacao":"definido"}]'
criar $ID2 hashC "$BAD" >/dev/null; Qs "select criar_orcamento('$ID2','hC','$OBRA','{}','$BAD')"; check "falha parcial retorna erro" 3 $?
check "falha parcial não deixa orçamento" 0 "$(Ql "select count(*) from orcamentos where id='$ID2'")"
check "falha parcial não deixa itens" 0 "$(Ql "select count(*) from orcamento_itens where orcamento_id='$ID2'")"
rej() { Qs "select criar_orcamento('$ID2','h','${3:-$OBRA}','{}','$1')"; local rc=$?; local n=$(Ql "select count(*) from orcamentos where id='$ID2'"); check "$2 (rejeitado e desfeito)" "3|0" "$rc|$n"; }
rej '[]' "lista vazia"
rej '[{"id_linha":"a","linha":1,"descricao":"x","quantidade":0,"unidade":"un","classificacao":"definido"}]' "quantidade zero"
rej '[{"id_linha":"a","linha":1,"descricao":"x","quantidade":1,"unidade":"un","classificacao":"generico"}]' "classificação antiga 'generico'"
rej '[{"id_linha":"a","linha":1,"descricao":"x","quantidade":1,"unidade":"un","classificacao":"definido"},{"id_linha":"a","linha":2,"descricao":"y","quantidade":1,"unidade":"un","classificacao":"definido"}]' "id_linha repetido"
rej '[{"id_linha":"a","descricao":"x","quantidade":1,"unidade":"un","classificacao":"definido"}]' "linha ausente"
rej "$ITENS" "CEP inválido" '{"nome":"x","cep":"123","orcamento_cliente":1}'
rej "$ITENS" "orçamento do cliente zero" '{"nome":"x","cep":"51020000","orcamento_cliente":0}'
rej "$ITENS" "orçamento do cliente ausente" '{"nome":"x","cep":"51020000"}'

echo "## 5. Complementos da C (E2): exemplo exato de João"
ID_E2=23232323-2323-4232-8232-232323232323
SUG='{"regra":"porcelanato","descricao":"Argamassa colante AC-III 20 kg (saco)","quantidade":15,"unidade":"un","categoria":"Revestimentos e argamassas","motivo":"Para 48 m² de piso/revestimento costumam faltar argamassa, rejunte e niveladores.","origem_linhas":[1],"estimativa":true}'
ENT='{"linha":1,"categoria":"Revestimentos","descricao":"Porcelanato 90x90 acetinado","quantidade":48,"unidade":"m2"}'
Qs "select criar_orcamento('$ID_E2','hE2','$OBRA','{}', jsonb_build_array(
   '$ENT'::jsonb || '{\"id_linha\":\"l1\",\"classificacao\":\"definido\"}',
   jsonb_build_object('id_linha','c1','linha',2,'categoria','$SUG'::jsonb->>'categoria','descricao','$SUG'::jsonb->>'descricao',
     'quantidade',('$SUG'::jsonb->>'quantidade')::numeric,'unidade','$SUG'::jsonb->>'unidade','classificacao','definido',
     'sugerido',true,'sugestao_regra','$SUG'::jsonb->>'regra','sugestao_motivo','$SUG'::jsonb->>'motivo',
     'origem_linhas','$SUG'::jsonb->'origem_linhas','aceito',true,'estimativa_consumo',('$SUG'::jsonb->>'estimativa')::boolean,
     'origem_item','manual')))"
check "complemento aceito é gravado" 0 $?
check "regra, linhas de origem e aceite registrados" "porcelanato|{1}|true|true" "$(Ql "select sugestao_regra||'|'||origem_linhas::text||'|'||sugerido||'|'||aceito from orcamento_itens where orcamento_id='$ID_E2' and id_linha='c1'")"
check "estimativa de CONSUMO (C) não vira estimativa de PREÇO (B)" "true|false" "$(Ql "select estimativa_consumo||'|'||estimativa from orcamento_itens where orcamento_id='$ID_E2' and id_linha='c1'")"
check "motivo da sugestão separado do motivo do resultado" "true|" "$(Ql "select (sugestao_motivo like 'Para 48%')||'|'||coalesce(motivo,'') from orcamento_itens where orcamento_id='$ID_E2' and id_linha='c1'")"
check "item original não é sugerido" "false||" "$(Ql "select sugerido||'|'||coalesce(sugestao_regra,'')||'|'||coalesce(aceito::text,'') from orcamento_itens where orcamento_id='$ID_E2' and id_linha='l1'")"
Qs "select criar_orcamento('34343434-3434-4343-8343-343434343434','h','$OBRA','{}','[{\"id_linha\":\"c1\",\"linha\":1,\"descricao\":\"x\",\"quantidade\":1,\"unidade\":\"un\",\"classificacao\":\"definido\",\"sugerido\":true,\"sugestao_regra\":\"r\",\"aceito\":true}]')"
check "complemento sem origem_linhas é rejeitado" 3 $?
Qs "select criar_orcamento('45454545-4545-4454-8454-454545454545','h','$OBRA','{}','[{\"id_linha\":\"c1\",\"linha\":1,\"descricao\":\"x\",\"quantidade\":1,\"unidade\":\"un\",\"classificacao\":\"definido\",\"sugerido\":true,\"sugestao_regra\":\"r\",\"origem_linhas\":[1]}]')"
check "complemento sem decisão (aceito) é rejeitado" 3 $?

echo "## 6. Concorrência na criação"
ID3=55555555-5555-4555-8555-555555555555
rm -f /tmp/conc_*.out
for i in $(seq 1 12); do criar $ID3 hashD > /tmp/conc_$i.out 2>&1 & done; wait
check "12 criações simultâneas: 1 'criado'" 1 "$(cat /tmp/conc_*.out | grep -c '^criado$')"
check "12 criações simultâneas: 11 'existente'" 11 "$(cat /tmp/conc_*.out | grep -c '^existente$')"
check "1 orçamento, 2 itens" "1|2" "$(Ql "select (select count(*) from orcamentos where id='$ID3')||'|'||(select count(*) from orcamento_itens where orcamento_id='$ID3')")"
ID4=66666666-6666-4666-8666-666666666666
rm -f /tmp/conc_*.out
for i in $(seq 1 8); do criar $ID4 "hash$i" > /tmp/conc_$i.out 2>&1 & done; wait
check "8 criações, conteúdos diferentes: 1 criado, 7 conflitos" "1|7" "$(cat /tmp/conc_*.out | grep -c '^criado$')|$(cat /tmp/conc_*.out | grep -c '^conflito$')"

echo "## 7. Fontes: qualquer preço exige fonte válida (6 campos, inclusive estimativa)"
W="where id_linha='l1' and orcamento_id='$ID1'"
upd() { Qs "update orcamento_itens set $1 $W"; }
for c in preco_emb_min preco_emb_med preco_emb_max preco_un_min preco_un_med preco_un_max; do
  upd "$c=10"; check "$c sem fonte é rejeitado" 3 $?
  upd "$c=10, estimativa=true"; check "$c com estimativa=true sem fonte é rejeitado" 3 $?
  upd "$c=10, estimativa=true, fontes='[]'"; check "$c com estimativa=true e fontes vazias é rejeitado" 3 $?
  upd "$c=10, fontes='$FONTE'"; check "$c com fonte válida é aceito" 0 $?
  upd "$c=null, fontes='[]'"
done
upd "preco_emb_min=12, preco_emb_max=10, fontes='$FONTE'"; check "mínimo maior que máximo (embalagem) é rejeitado" 3 $?
upd "preco_un_min=2, preco_un_max=1, fontes='$FONTE'"; check "mínimo maior que máximo (unidade) é rejeitado" 3 $?
upd "preco_emb_med=-1, fontes='$FONTE'"; check "preço negativo é rejeitado" 3 $?
upd "preco_emb_med=10, estimativa=true, fontes='$FONTE'"; check "estimativa=true COM fonte válida é aceita" 0 $?
upd "preco_emb_min=null, preco_emb_med=null, preco_emb_max=null, estimativa=false, fontes='[]'"; check "sem preço e sem fonte é aceito" 0 $?
for ruim in '[{"loja":"L","dominio":"d.com","preco_embalagem":10}]' \
            '[{"loja":"L","dominio":"d.com","url":"ftp://x","preco_embalagem":10}]' \
            '[{"loja":"","dominio":"d.com","url":"https://x","preco_embalagem":10}]' \
            '[{"loja":"L","dominio":"d.com","url":"https://x","preco_embalagem":-1}]' \
            '[{"loja":"L","dominio":"d.com","url":"https://x","preco_embalagem":"dez"}]' \
            '[{"loja":"L","dominio":"www.d.com","url":"https://x","preco_embalagem":10}]' \
            '[{"loja":"L","dominio":"d.com","url":"https://x","preco_embalagem":10,"embalagem":5}]' \
            '["texto"]' '{"loja":"L"}'; do
  upd "preco_emb_med=10, fontes='$ruim'"; check "fonte inválida com preço é rejeitada: ${ruim:0:60}" 3 $?
done
upd "fontes='[{\"loja\":\"L\"}]'"; check "fonte inválida é rejeitada mesmo sem preço" 3 $?
upd "preco_un_med=1.2664, fontes='[{\"loja\":\"L\",\"dominio\":\"d.com\",\"url\":\"https://x\",\"preco_embalagem\":10}]'"
check "fonte sem 'embalagem' (opcional) é aceita" 0 $?
upd "preco_un_med=null, fontes='[]'"
upd "\"similar\"='{\"descricao\":\"Votomassa AC-II\",\"preco_emb_med\":18.9}'"; check "similar com preço sem fonte própria é rejeitado" 3 $?
upd "\"similar\"='{\"descricao\":\"Votomassa AC-II\",\"preco_emb_med\":18.9,\"fontes\":$FONTE}'"; check "similar com preço e fonte é aceito" 0 $?
upd "\"similar\"='{\"preco_emb_med\":18.9,\"fontes\":$FONTE}'"; check "similar sem descricao é rejeitado" 3 $?
upd "\"similar\"=null"
upd "status='qualquer'"; check "status fora da lista é rejeitado" 3 $?
upd "confianca='enorme'"; check "confianca fora da lista é rejeitada" 3 $?
upd "iteracoes=-1"; check "iteracoes negativa é rejeitada" 3 $?

echo "## 8. Escrita exata de Enzo (B) por gravar_resultado_item"
IDB=77777777-7777-4777-8777-777777777777
criar $IDB hashE >/dev/null
IT1=$(item_de $IDB l1); IT2=$(item_de $IDB l2)
check "item começa 'buscando' com iteracoes 0" "buscando|0" "$(Ql "select status||'|'||iteracoes from orcamento_itens where id='$IT1'")"
check "reservar devolve a tentativa 1" 1 "$(reservar $IDB)"
CRIADO_EM=$(Ql "select atualizado_em from orcamento_itens where id='$IT1'")
PAYLOAD_B='{"status":"definido","produto_normalizado":"Tinta Acrílica Suvinil Toque de Seda 18L","imagem_url":"https://img.exemplo.com/t.png","embalagem":"lata 18 L","unidade_preco":"m2","pergunta":null,"motivo":null,"qtd_embalagens":2,"iteracoes":1,"preco_emb_min":420.00,"preco_emb_med":455.90,"preco_emb_max":489.90,"preco_un_min":1.1667,"preco_un_med":1.2664,"preco_un_max":1.3608,"confianca":"alta","estimativa":false,"fontes":[{"loja":"Leroy Merlin","dominio":"www.LeroyMerlin.com.br","url":"https://www.leroymerlin.com.br/p/1","preco_embalagem":455.90,"embalagem":"lata 18 L"}],"preco_data":"2026-11-07T14:30:00-03:00"}'
check "gravação com TODOS os campos de B funciona" t "$(gravar $IT1 1 "$PAYLOAD_B")"
check "preços por embalagem e por unidade gravados" "420.00|455.90|489.90|1.1667|1.2664|1.3608" "$(Ql "select preco_emb_min||'|'||preco_emb_med||'|'||preco_emb_max||'|'||preco_un_min||'|'||preco_un_med||'|'||preco_un_max from orcamento_itens where id='$IT1'")"
check "campos de texto e contadores" "definido|Tinta Acrílica Suvinil Toque de Seda 18L|lata 18 L|m2|2|1|alta|false" "$(Ql "select status||'|'||produto_normalizado||'|'||embalagem||'|'||unidade_preco||'|'||qtd_embalagens||'|'||iteracoes||'|'||confianca||'|'||estimativa from orcamento_itens where id='$IT1'")"
check "domínio da fonte normalizado na gravação" "leroymerlin.com.br" "$(Ql "select fontes -> 0 ->> 'dominio' from orcamento_itens where id='$IT1'")"
check "preco_data é timestamptz (17:30 UTC)" "2026-11-07 17:30:00+00" "$(Ql "set timezone='UTC'; select preco_data from orcamento_itens where id='$IT1'" | tail -1)"
check "atualizado_em avança a cada UPDATE" t "$(Ql "select atualizado_em > '$CRIADO_EM'::timestamptz from orcamento_itens where id='$IT1'")"
check "gravar guarda a tentativa que escreveu" 1 "$(Ql "select tentativa from orcamento_itens where id='$IT1'")"
r=$(gravar_err $IT2 1 '{"status":"definido","preco_emb_med":5}'); check "preço sem fonte via função levanta erro" 1 "$(echo "$r" | grep -c 'preco_exige_fonte_ck')"
r=$(gravar_err $IT2 1 '{"status":"definido","preco_un_med":5,"estimativa":true}'); check "preço por unidade estimado sem fonte levanta erro" 1 "$(echo "$r" | grep -c 'preco_exige_fonte_ck')"
check "gravação recusada deixa o item intacto" "buscando||0" "$(Ql "select status||'|'||coalesce(preco_un_med::text,'')||'|'||iteracoes from orcamento_itens where id='$IT2'")"
r=$(gravar_err $IT2 1 '{"produto":"x"}'); check "nome antigo 'produto' é recusado" 1 "$(echo "$r" | grep -c 'campos não permitidos')"
r=$(gravar_err $IT2 1 '{"imagem":"x"}'); check "nome antigo 'imagem' é recusado" 1 "$(echo "$r" | grep -c 'campos não permitidos')"
r=$(gravar_err $IT2 1 '{"classificacao":"definido"}'); check "classificacao é da A: B não grava" 1 "$(echo "$r" | grep -c 'campos não permitidos')"
r=$(gravar_err $IT2 1 '{"status":"talvez"}'); check "status inválido levanta erro" 1 "$(echo "$r" | grep -c 'itens_status_ck')"
gravar $IT1 1 '{"produto_normalizado":null}' >/dev/null
check "chave com null limpa o campo; ausente preserva o resto" "|455.90" "$(Ql "select coalesce(produto_normalizado,'')||'|'||preco_emb_med from orcamento_itens where id='$IT1'")"
check "pergunta e motivo de pendente (sem preço)" t "$(gravar $IT2 1 '{"status":"pendente_especificacao","pergunta":"Qual acabamento e litragem?","motivo":"Descrição genérica"}')"
check "similar (T2) com fonte própria" t "$(gravar $IT1 1 "{\"similar\":{\"descricao\":\"Votomassa AC-II\",\"preco_emb_med\":18.9,\"fontes\":[{\"loja\":\"L\",\"dominio\":\"WWW.Leroymerlin.com.br\",\"url\":\"https://x\",\"preco_embalagem\":18.9}]}}")"
check "domínio do similar também é normalizado" "leroymerlin.com.br" "$(Ql "select \"similar\" -> 'fontes' -> 0 ->> 'dominio' from orcamento_itens where id='$IT1'")"

echo "## 9. Cache de preços (B): chave, resultado, imagem_url, atualizado_em"
Qs "insert into cache_precos (chave, resultado, imagem_url) values ('tinta-suvinil-18l','{\"preco_emb_med\":455.9,\"fontes\":$FONTE}','https://img/t.png')"
check "cache aceita resultado com fonte" 0 $?
check "validade de 7 dias vem de atualizado_em" t "$(Ql "select atualizado_em > now() - interval '7 days' from cache_precos where chave='tinta-suvinil-18l'")"
Qs "update cache_precos set atualizado_em = now() - interval '9 days' where chave='tinta-suvinil-18l'"
Qs "update cache_precos set resultado = resultado where chave='tinta-suvinil-18l'"
check "UPDATE renova atualizado_em (cache vencido volta a valer)" t "$(Ql "select atualizado_em > now() - interval '1 minute' from cache_precos where chave='tinta-suvinil-18l'")"
Qs "insert into cache_precos (chave, resultado) values ('x','{\"preco_emb_med\":10}')"; check "cache: preço sem fonte é rejeitado" 3 $?
Qs "insert into cache_precos (chave, resultado) values ('y','{\"preco_un_med\":10,\"fontes\":[]}')"; check "cache: preço por unidade com fontes vazias é rejeitado" 3 $?
Qs "insert into cache_precos (chave, resultado) values ('z','{\"fontes\":[{\"loja\":\"L\"}]}')"; check "cache: fonte inválida é rejeitada" 3 $?
Qs "insert into cache_precos (chave, resultado) values ('w','{\"produto\":\"sem preço ainda\"}')"; check "cache: resultado sem preço é aceito" 0 $?
check "cache sem expira_em/criado_em" 0 "$(Ql "select count(*) from information_schema.columns where table_name='cache_precos' and column_name in ('expira_em','criado_em')")"

echo "## 10. Fornecedores (C): nomes exatos"
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km, pedido_minimo) values ('Leroy Merlin Recife','WWW.LeroyMerlin.com.br','51021000',50,2.5,200)"
check "cadastro só com os obrigatórios" 0 $?
check "domínio normalizado no cadastro" leroymerlin.com.br "$(Ql "select dominio from fornecedores where nome='Leroy Merlin Recife'")"
check "opcionais: ativo=true, lat/lon nulos" "true||" "$(Ql "select ativo||'|'||coalesce(lat::text,'')||'|'||coalesce(lon::text,'') from fornecedores where nome='Leroy Merlin Recife'")"
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km, pedido_minimo, lat, lon, ativo, site, cidade) values ('C&C Recife','cec.com.br','50000000',40,2,150,-8.0476,-34.877,false,'https://cec.com.br','Recife')"
check "cadastro com lat, lon e ativo" 0 $?
check "leitura pelas colunas pedidas por João" 0 "$(Qs "select id, nome, dominio, cep, frete_base, rs_por_km, pedido_minimo, lat, lon, ativo from fornecedores"; echo $?)"
check "C lê orcamentos e itens pelas colunas que listou" 0 "$(Qs "select nome, cep, created_at, pesquisa_concluida_em, orcamento_cliente from orcamentos; select linha, categoria, descricao, quantidade, unidade, nivel, extras, status, qtd_embalagens, embalagem, preco_emb_min, preco_emb_med, preco_emb_max, estimativa, confianca, pergunta, imagem_url, fontes, \"similar\", sugerido, sugestao_regra, sugestao_motivo, origem_linhas, aceito from orcamento_itens"; echo $?)"
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km, pedido_minimo) values ('Outra','leroymerlin.com.br','51021000',50,2.5,200)"; check "mesma rede com nome diferente é aceita (outra loja)" 0 $?
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km, pedido_minimo) values ('Leroy Merlin Recife','leroymerlin.com.br','51021000',50,2.5,200)"; check "dominio+nome repetidos são rejeitados" 3 $?
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km) values ('Sem mínimo','a.com','51021000',50,2.5)"; check "pedido_minimo é obrigatório" 3 $?
Qs "insert into fornecedores (nome, dominio, frete_base, rs_por_km, pedido_minimo) values ('Sem CEP','b.com',50,2.5,200)"; check "cep é obrigatório" 3 $?
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km, pedido_minimo) values ('CEP ruim','c.com','123',50,2.5,200)"; check "cep inválido é rejeitado" 3 $?
Qs "insert into fornecedores (nome, dominio, cep, frete_base, rs_por_km, pedido_minimo) values ('Negativo','d.com','51021000',-1,2.5,200)"; check "frete negativo é rejeitado" 3 $?
Qs "insert into fornecedores (nome, dominio, cep, frete_base, frete_por_km, pedido_minimo) values ('Nome antigo','e.com','51021000',50,2.5,200)"; check "nome antigo frete_por_km não existe mais" 3 $?

echo "## 10b. Resultados de João (C): logistica, viabilidade, ganho — colunas exatas e escrita"
lista_cols() { Ql "select string_agg(c, ',' order by c) from unnest(array[$2]) c where c not in (select column_name from information_schema.columns where table_schema='public' and table_name='$1')"; }
check "fornecedores: todas as colunas pedidas existem" "" "$(lista_cols fornecedores "'id','nome','dominio','cep','lat','lon','frete_base','rs_por_km','pedido_minimo'")"
check "orcamentos: todas as colunas pedidas existem" "" "$(lista_cols orcamentos "'cep','orcamento_cliente','logistica','viabilidade','ganho','pesquisa_iniciada_em','pesquisa_concluida_em','custo_usd','tempo_ms','trace_url','nome','created_at'")"
check "orcamento_itens: todas as colunas pedidas existem" "" "$(lista_cols orcamento_itens "'descricao','categoria','quantidade','unidade','status','embalagem','qtd_embalagens','preco_emb_min','preco_emb_med','preco_emb_max','confianca','estimativa','pergunta','fontes','similar','imagem_url','sugerido','sugestao_regra','sugestao_motivo','origem_linhas','aceito','estimativa_consumo','linha','nivel','extras'")"
check "origem_linhas é int[]" "ARRAY|_int4" "$(Ql "select data_type||'|'||udt_name from information_schema.columns where table_name='orcamento_itens' and column_name='origem_linhas'")"
check "logistica/viabilidade/ganho são jsonb opcionais" "jsonb:YES|jsonb:YES|jsonb:YES" "$(Ql "select string_agg(data_type||':'||is_nullable, '|' order by column_name) from information_schema.columns where table_name='orcamentos' and column_name in ('ganho','logistica','viabilidade')")"
IDJ=cccccccc-cccc-4ccc-8ccc-cccccccccccc
criar $IDJ hashJ >/dev/null
TJ=$(reservar $IDJ)
ANTES=$(Ql "select tentativa_pesquisa||'|'||status_pesquisa||'|'||coalesce(pesquisa_heartbeat_em::text,'')||'|'||coalesce(pesquisa_iniciada_em::text,'') from orcamentos where id='$IDJ'")
Qs "update orcamentos set logistica='{\"estrategia\":\"loja_unica\",\"lojas\":[\"Leroy Merlin Recife\"],\"frete_total\":180.0,\"economia_estimada\":95.0}', viabilidade='{\"cabe\":true,\"total_med\":15234.5,\"completo\":true}', ganho='{\"resumo\":\"À mão: ~6 h. Aqui: 28 s. Custo de IA: R\$ 0,30\"}' where id='$IDJ'"
check "João grava logistica, viabilidade e ganho" 0 $?
check "os três jsonb ficam gravados" "loja_unica|true|À mão: ~6 h. Aqui: 28 s. Custo de IA: R\$ 0,30" "$(Ql "select (logistica->>'estrategia')||'|'||(viabilidade->>'cabe')||'|'||(ganho->>'resumo') from orcamentos where id='$IDJ'")"
check "gravar os resultados da C não mexe em tentativa, status_pesquisa nem heartbeat" "$ANTES" "$(Ql "select tentativa_pesquisa||'|'||status_pesquisa||'|'||coalesce(pesquisa_heartbeat_em::text,'')||'|'||coalesce(pesquisa_iniciada_em::text,'') from orcamentos where id='$IDJ'")"
check "a tentativa da B continua válida depois da escrita da C" t "$(gravar $(item_de $IDJ l1) $TJ '{"iteracoes":1}')"
check "B finaliza depois da C ter gravado (e não apaga os resultados da C)" "t|t" "$(Ql "select finalizar_pesquisa('$IDJ', $TJ, 'concluida')")|$(Ql "select (logistica is not null and viabilidade is not null and ganho is not null) from orcamentos where id='$IDJ'")"
Qs "update orcamentos set ganho='{\"resumo\":\"2\"}' where id='$IDJ'"
check "C reescreve ganho depois de concluída; status_pesquisa segue 'concluida'" "concluida|2" "$(Ql "select status_pesquisa||'|'||(ganho->>'resumo') from orcamentos where id='$IDJ'")"
check "reservar_pesquisa não apaga logistica/viabilidade/ganho (reabrir)" "true" "$(Ql "select reservar_pesquisa('$IDJ',180,true)::jsonb ->> 'reservado'")"
check "resultados da C sobrevivem à reabertura" t "$(Ql "select (logistica is not null and viabilidade is not null and ganho is not null) from orcamentos where id='$IDJ'")"
# Banco que recebeu uma versão deste arquivo SEM a coluna ganho: reaplicar acrescenta.
Qs "alter table orcamentos drop column ganho"
aplicar base; check "reaplicar sobre banco sem 'ganho' funciona" 0 $?
check "reaplicar recria orcamentos.ganho (jsonb)" jsonb "$(Ql "select data_type from information_schema.columns where table_name='orcamentos' and column_name='ganho'")"

echo "## 11. Protocolo da pesquisa: reservar → gravar → finalizar"
IDP=88888888-8888-4888-8888-888888888888
criar $IDP hashF >/dev/null
IP1=$(item_de $IDP l1)
rm -f /tmp/conc_*.out
for i in $(seq 1 12); do reservar $IDP > /tmp/conc_$i.out 2>&1 & done; wait
check "12 reservas simultâneas: exatamente 1 recebe tentativa" 1 "$(cat /tmp/conc_*.out | grep -cE '^[0-9]+$')"
check "as outras 11 recebem NULL (não pesquisam)" 11 "$(cat /tmp/conc_*.out | grep -cvE '^[0-9]+$')"
check "tentativa 1 e status_pesquisa 'pesquisando'" "1|pesquisando" "$(Ql "select tentativa_pesquisa||'|'||status_pesquisa from orcamentos where id='$IDP'")"
check "perdedor recebe o estado atual" "false|pesquisando" "$(Ql "select (r->>'reservado')||'|'||(r->>'status_pesquisa') from (select reservar_pesquisa('$IDP') r) x")"
check "reserva dentro do prazo não retoma a execução ativa" "" "$(reservar $IDP)"
check "orçamento inexistente não explode" "false|" "$(Ql "select (r->>'reservado')||'|'||coalesce(r->>'status_pesquisa','') from (select reservar_pesquisa('00000000-0000-4000-8000-000000000000') r) x")"

# Execução lenta: a tentativa 1 passa do prazo sem atividade, a 2 assume, a 1 acorda depois.
envelhecer $IDP
check "execução parada além do prazo é retomada (tentativa 2)" 2 "$(reservar $IDP)"
check "tentativa 2 grava o item" t "$(gravar $IP1 2 "{\"status\":\"definido\",\"produto_normalizado\":\"NOVO\",\"preco_emb_med\":20,\"fontes\":$FONTE}")"
check "tentativa 1 (lenta) NÃO sobrescreve o item" f "$(gravar $IP1 1 "{\"status\":\"erro\",\"produto_normalizado\":\"VELHO\",\"preco_emb_med\":99,\"fontes\":$FONTE}")"
check "item continua com o resultado da tentativa 2" "definido|NOVO|20.00|2" "$(Ql "select status||'|'||produto_normalizado||'|'||preco_emb_med||'|'||tentativa from orcamento_itens where id='$IP1'")"
check "tentativa 1 não renova o prazo" f "$(Ql "select renovar_pesquisa('$IDP', 1)")"
check "tentativa 1 não finaliza" f "$(Ql "select finalizar_pesquisa('$IDP', 1, 'falhou', '{\"pesquisa_erro\":\"velho\"}')")"
check "orçamento segue 'pesquisando' na tentativa 2, sem erro" "pesquisando|2|" "$(Ql "select status_pesquisa||'|'||tentativa_pesquisa||'|'||coalesce(pesquisa_erro,'') from orcamentos where id='$IDP'")"

# Corrida em massa (não prova a proteção sozinha, mas pega regressões grosseiras)
rm -f /tmp/conc_*.out
for i in $(seq 1 8); do gravar $IP1 1 "{\"produto_normalizado\":\"VELHO$i\"}" > /tmp/conc_v$i.out 2>&1 & done
gravar $IP1 2 '{"produto_normalizado":"NOVO2"}' > /tmp/conc_n.out 2>&1 &
wait
check "8 gravações atrasadas da tentativa 1 são recusadas" 8 "$(cat /tmp/conc_v*.out | grep -c '^f$')"
check "a da tentativa 2 grava e o valor final é o dela" "t|NOVO2" "$(cat /tmp/conc_n.out)|$(Ql "select produto_normalizado from orcamento_itens where id='$IP1'")"

# Prazo
envelhecer $IDP
check "renovar_pesquisa da tentativa atual funciona" t "$(Ql "select renovar_pesquisa('$IDP', 2)")"
check "pesquisa renovada não é retomada" "" "$(reservar $IDP)"
envelhecer $IDP; gravar $IP1 2 '{"iteracoes":1}' >/dev/null
check "gravar um item também renova o prazo" "" "$(reservar $IDP)"
envelhecer $IDP
rm -f /tmp/conc_*.out
for i in $(seq 1 12); do reservar $IDP > /tmp/conc_$i.out 2>&1 & done; wait
check "prazo vencido, 12 reservas simultâneas: 1 assume (tentativa 3)" "1|3" "$(cat /tmp/conc_*.out | grep -cE '^[0-9]+$')|$(Ql "select tentativa_pesquisa from orcamentos where id='$IDP'")"

# Finalização
check "finalizar com a tentativa atual" t "$(Ql "select finalizar_pesquisa('$IDP', 3, 'concluida', '{\"custo_usd\":0.05,\"tempo_ms\":28000,\"trace_url\":\"https://langfuse/t/1\"}')")"
check "orçamento 'concluida' com data de conclusão e custo" "concluida|true|0.050000|28000" "$(Ql "select status_pesquisa||'|'||(pesquisa_concluida_em is not null)||'|'||custo_usd||'|'||tempo_ms from orcamentos where id='$IDP'")"
check "execução antiga não grava em orçamento concluído" f "$(gravar $IP1 3 '{"iteracoes":2}')"
check "orçamento concluído não é pesquisado de novo" "" "$(reservar $IDP)"
check "repesquisar_item: reabrir permite reservar de novo (tentativa 4)" 4 "$(reservar $IDP 180 true)"
check "finalizar como 'falhou' guarda o erro" t "$(Ql "select finalizar_pesquisa('$IDP', 4, 'falhou', '{\"pesquisa_erro\":\"Tavily fora do ar\"}')")"
ERRO_ANTES=$(Ql "select pesquisa_erro from orcamentos where id='$IDP'"); T5=$(reservar $IDP)
check "estado 'falhou' guarda o erro e pode ser retomado (tentativa 5, erro limpo)" "Tavily fora do ar|5|" "$ERRO_ANTES|$T5|$(Ql "select coalesce(pesquisa_erro,'') from orcamentos where id='$IDP'")"
Qs "select finalizar_pesquisa('$IDP', 5, 'andando')"; check "status final inválido é rejeitado" 3 $?
Qs "update orcamentos set status_pesquisa='concluido' where id='$IDP'"; check "status_pesquisa fora da lista (antigo 'concluido') é rejeitado" 3 $?

# Troca de tentativa DURANTE a gravação — intercalamento controlado (ver função corrida abaixo)
corrida() { # banco -> preenche R_A, R_A_MS, R_A_ITEM, R_B, R_D
  local db=$1 oid=$2 it t0 t1
  D=$db
  criar $oid hashR >/dev/null
  it=$(item_de $oid l1)
  reservar $oid >/dev/null                                  # tentativa 1 em andamento
  # Caso A: a reserva da tentativa 2 está no meio da troca (linha travada) quando a tentativa 1 tenta gravar.
  envelhecer $oid
  ( printf "begin; select reservar_pesquisa('%s'); select pg_sleep(3); commit;" "$oid" | docker exec -i "$CT" psql -U postgres -d "$db" -tA >/tmp/race_x.out 2>&1 ) &
  sleep 1
  t0=$(date +%s%N)
  R_A=$(gravar "$it" 1 '{"produto_normalizado":"VELHO"}')
  t1=$(date +%s%N); R_A_MS=$(( (t1 - t0) / 1000000 ))
  wait
  R_A_ITEM=$(Ql "select coalesce(produto_normalizado,'') from orcamento_itens where id='$it'")
  R_A_TENT=$(Ql "select tentativa_pesquisa from orcamentos where id='$oid'")
  # Caso B: a tentativa 2 grava (e renova o prazo) dentro de uma transação aberta; uma reserva concorrente
  # enxerga o prazo velho ao começar, mas depois da gravação o prazo está novo e ela deve ser negada.
  envelhecer $oid
  ( printf "begin; select gravar_resultado_item('%s', 2, '{\"produto_normalizado\":\"NOVO\"}'); select pg_sleep(3); commit;" "$it" | docker exec -i "$CT" psql -U postgres -d "$db" -tA >/tmp/race_w.out 2>&1 ) &
  sleep 1
  R_B=$(Ql "select reservar_pesquisa('$oid')::jsonb ->> 'reservado'")
  wait
  # Caso D: finalização de tentativa velha enquanto a reserva troca a tentativa.
  envelhecer $oid
  ( printf "begin; select reservar_pesquisa('%s'); select pg_sleep(3); commit;" "$oid" | docker exec -i "$CT" psql -U postgres -d "$db" -tA >/tmp/race_x.out 2>&1 ) &
  sleep 1
  R_D=$(Ql "select finalizar_pesquisa('$oid', 2, 'concluida')")
  wait
}
echo "## 12. Troca de tentativa durante a gravação (intercalamento controlado)"
corrida base 99999999-9999-4999-8999-999999999999
check "A: gravação da tentativa 1 durante a troca é recusada" f "$R_A"
check "A: ela ESPEROU a troca terminar (bloqueio, não corrida de leitura)" 1 "$([ "$R_A_MS" -ge 1000 ] && echo 1 || echo "0 (${R_A_MS} ms)")"
check "A: o item não recebeu o valor da tentativa velha" "" "$R_A_ITEM"
check "A: a tentativa vigente passou a ser a 2" 2 "$R_A_TENT"
check "B: reserva concorrente a uma gravação em curso é negada (prazo renovado)" false "$R_B"
check "D: finalização da tentativa velha durante a troca é recusada" f "$R_D"

# ===========================================================================
echo "## 13. Teste de mutação: sem o bloqueio da linha, a corrida controlada tem que FALHAR"
sed 's/ for no key update;/;/' sql/002_orcamentos.sql > /tmp/002_mutado.sql
check "o arquivo mutado realmente perdeu o bloqueio" 0 "$(grep -c 'for no key update' /tmp/002_mutado.sql)"
novo_banco mutado; aplicar mutado /tmp/002_mutado.sql; check "arquivo mutado aplica" 0 $?
corrida mutado aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa
check "mutação detectada: sem o bloqueio a gravação velha PASSA (t) — o teste da seção 12 pega isso" t "$R_A"
D=base

# ===========================================================================
echo "## 14. Permissões e Realtime com os papéis do Supabase (simulados)"
novo_banco papeis
docker exec -i "$CT" psql -U postgres -d papeis -v ON_ERROR_STOP=1 -q >/dev/null 2>&1 <<'SQL'
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname='service_role') then create role service_role nologin bypassrls; end if;
end $$;
create publication supabase_realtime;
SQL
aplicar papeis; check "SQL aplica com papéis do Supabase" 0 $?
aplicar papeis; check "SQL reaplica com papéis do Supabase" 0 $?
D=papeis
check "Realtime publica as 2 tabelas de acompanhamento" "orcamento_itens,orcamentos" "$(Ql "select string_agg(tablename, ',' order by tablename) from pg_publication_tables where pubname='supabase_realtime'")"
Q "select criar_orcamento('$ID1','h','$OBRA','{}','$ITENS')" >/dev/null
check "anon lê orcamentos" 1 "$(Ql "set role anon; select count(*) from orcamentos")"
check "anon lê orcamento_itens" 2 "$(Ql "set role anon; select count(*) from orcamento_itens")"
Qs "set role anon; insert into orcamentos (id,nome,cep,orcamento_cliente,hash_conteudo,qtd_itens) values (gen_random_uuid(),'x','51020000',1,'h',1)"; check "anon NÃO grava em orcamentos" 3 $?
Qs "set role anon; update orcamentos set nome='hack'"; check "anon NÃO atualiza orcamentos" 3 $?
Qs "set role anon; delete from orcamento_itens"; check "anon NÃO apaga itens" 3 $?
Qs "set role anon; select count(*) from cache_precos"; check "anon NÃO lê cache_precos" 3 $?
Qs "set role anon; select count(*) from fornecedores"; check "anon NÃO lê fornecedores" 3 $?
Qs "set role authenticated; select count(*) from orcamentos"; check "authenticated NÃO lê orcamentos (só anon, modelo da demo)" 3 $?
IT_P=$(Ql "select id from orcamento_itens limit 1")
for chamada in "criar_orcamento(gen_random_uuid(),'h','$OBRA','{}','$ITENS')" "reservar_pesquisa('$ID1')" "renovar_pesquisa('$ID1',1)" \
               "gravar_resultado_item('$IT_P',1,'{}')" "finalizar_pesquisa('$ID1',1,'concluida')"; do
  Qs "set role anon; select $chamada"; check "anon NÃO executa ${chamada%%(*}" 3 $?
  Qs "set role authenticated; select $chamada"; check "authenticated NÃO executa ${chamada%%(*}" 3 $?
done
check "service_role executa criar_orcamento" criado "$(Ql "set role service_role; select criar_orcamento(gen_random_uuid(),'h','$OBRA','{}','$ITENS')::jsonb ->> 'resultado'")"
check "service_role reserva a pesquisa" 1 "$(Ql "set role service_role; select reservar_pesquisa('$ID1')::jsonb ->> 'tentativa'")"
check "service_role grava e finaliza" "true|true" "$(Ql "set role service_role; select gravar_resultado_item((select id from orcamento_itens where orcamento_id='$ID1' limit 1), 1, '{\"iteracoes\":1}')||'|'||finalizar_pesquisa('$ID1',1,'concluida')")"
check "service_role (João) grava logistica/viabilidade/ganho" "UPDATE 1" "$(Ql "set role service_role; update orcamentos set logistica='{\"estrategia\":\"dividir\"}', viabilidade='{\"cabe\":false}', ganho='{\"resumo\":\"ok\"}' where id='$ID1' returning 1")"
check "anon lê logistica/viabilidade/ganho (Realtime/tela)" "dividir|false|ok" "$(Ql "set role anon; select (logistica->>'estrategia')||'|'||(viabilidade->>'cabe')||'|'||(ganho->>'resumo') from orcamentos where id='$ID1'")"
Qs "set role anon; update orcamentos set ganho='{}'"; check "anon NÃO grava ganho" 3 $?
Qs "set role authenticated; update orcamentos set ganho='{}'"; check "authenticated NÃO grava ganho" 3 $?
check "service_role lê/escreve cache e fornecedores" 0 "$(Qs "set role service_role; insert into fornecedores (nome,dominio,cep,frete_base,rs_por_km,pedido_minimo) values ('S','s.com','51021000',1,1,1); select count(*) from cache_precos"; echo $?)"
D=base

# ===========================================================================
echo "## 15b. cache_precos pré-existente com outro formato (caso do Supabase real)"
novo_banco cacheantigo
docker exec pgtest psql -U postgres -d cacheantigo -q -c "create table cache_precos (chave text primary key, valor jsonb, criado_em timestamptz default now()); insert into cache_precos values ('k','{\"a\":1}')" >/dev/null 2>&1
aplicar cacheantigo; check "aplica sobre cache_precos de outro formato" 0 $?
aplicar cacheantigo; check "reaplica (não renomeia de novo)" 0 $?
check "tabela antiga preservada com os dados; nova tem as 4 colunas" "1|1|4" "$(docker exec pgtest psql -U postgres -d cacheantigo -tA -c "select (select count(*) from pg_class where relname like 'cache_precos_antiga_%' and relkind='r')||'|'||(select count(*) from cache_precos_antiga_$(docker exec pgtest psql -U postgres -d cacheantigo -tA -c "select substr(relname,21) from pg_class where relname like 'cache_precos_antiga_%' and relkind='r'") )||'|'||(select count(*) from information_schema.columns where table_name='cache_precos')")"

echo "## 15. Migração do rascunho anterior (dados preservados)"
novo_banco rascunho
aplicar rascunho scripts/fixtures/002_rascunho_anterior.sql; check "aplica o rascunho anterior (fixture)" 0 $?
D=rascunho
Q "insert into orcamentos (id,estado,nome,cep,orcamento_cliente,hash_conteudo,qtd_itens,tentativa_pesquisa,erro_mensagem) values
   ('a1000000-0000-4000-8000-000000000001','concluido','Obra A','01310100',1234.56,'h1',3,2,null),
   ('a2000000-0000-4000-8000-000000000002','erro','Obra B','51020000',10,'h2',1,1,'falhou x'),
   ('a3000000-0000-4000-8000-000000000003','recebido','Obra C','51020000',10,'h3',1,0,null),
   ('a4000000-0000-4000-8000-000000000004','pesquisando','Obra D','51020000',10,'h4',1,1,null)" >/dev/null
Q "insert into orcamento_itens (orcamento_id,id_linha,linha,descricao_original,descricao,quantidade,unidade,classificacao,status,produto,imagem,preco_emb_min,preco_emb_med,preco_emb_max,fontes,preco_data,estimativa,erro_mensagem) values
   ('a1000000-0000-4000-8000-000000000001','l1',null,'Tinta','Tinta',10,'un','generico','definido','Tinta X','https://img/1.png',8,9.5,11,'[{\"loja\":\"Leroy\",\"dominio\":\"leroymerlin.com.br\",\"url\":\"https://x/1\",\"preco_embalagem\":9.5}]','2026-11-01',true,null),
   ('a1000000-0000-4000-8000-000000000001','l2',null,'Rejunte','Rejunte',5,'un','definido','erro',null,null,null,null,null,'[]',null,false,'timeout'),
   ('a1000000-0000-4000-8000-000000000001','l3',7,'Areia','Areia',1,'m3','definido','buscando',null,null,null,null,null,'[]',null,false,null)" >/dev/null
Q "insert into cache_precos (chave,resultado) values ('tinta-x','{\"preco_emb_med\":9.5,\"fontes\":[{\"loja\":\"L\",\"dominio\":\"leroymerlin.com.br\",\"url\":\"https://x\",\"preco_embalagem\":9.5}]}')" >/dev/null
Q "insert into fornecedores (nome,dominio,cep,frete_base,frete_por_km,pedido_minimo,latitude,longitude) values ('Leroy Merlin Recife','www.leroymerlin.com.br','51021000',50,2.5,200,-8.05,-34.9)" >/dev/null
check "rascunho tem os dados de teste" "4|3|1|1" "$(Ql "select (select count(*) from orcamentos)||'|'||(select count(*) from orcamento_itens)||'|'||(select count(*) from cache_precos)||'|'||(select count(*) from fornecedores)")"
aplicar rascunho; check "migração: aplica o SQL novo sobre o rascunho" 0 $?
aplicar rascunho; check "migração: reaplica (idempotente)" 0 $?
A1=a1000000-0000-4000-8000-000000000001
check "migração: status_pesquisa mapeado (concluída/falhou/pendente/pesquisando)" "concluida|falhou|pendente|pesquisando" "$(Ql "select string_agg(status_pesquisa, '|' order by nome) from orcamentos")"
check "migração: erro_mensagem → pesquisa_erro" "falhou x" "$(Ql "select pesquisa_erro from orcamentos where nome='Obra B'")"
check "migração: CEP com zero, centavos e tentativa preservados" "01310100|1234.56|2" "$(Ql "select cep||'|'||orcamento_cliente||'|'||tentativa_pesquisa from orcamentos where id='$A1'")"
check "migração: classificacao generico → pendente" "pendente|definido|definido" "$(Ql "select string_agg(classificacao, '|' order by id_linha) from orcamento_itens where orcamento_id='$A1'")"
check "migração: produto/imagem renomeados com valores" "Tinta X|https://img/1.png" "$(Ql "select produto_normalizado||'|'||imagem_url from orcamento_itens where orcamento_id='$A1' and id_linha='l1'")"
check "migração: preços e estimativa preservados" "8.00|9.50|11.00|true" "$(Ql "select preco_emb_min||'|'||preco_emb_med||'|'||preco_emb_max||'|'||estimativa from orcamento_itens where orcamento_id='$A1' and id_linha='l1'")"
check "migração: domínio da fonte normalizado" "leroymerlin.com.br" "$(Ql "select fontes -> 0 ->> 'dominio' from orcamento_itens where orcamento_id='$A1' and id_linha='l1'")"
check "migração: preco_data date → timestamptz" "timestamp with time zone" "$(col orcamento_itens preco_data | cut -d'|' -f1)"
check "migração: erro do item vira motivo" "timeout" "$(Ql "select motivo from orcamento_itens where orcamento_id='$A1' and id_linha='l2'")"
check "migração: linha vazia recebe a posição, linha existente fica" "1|2|7" "$(Ql "select string_agg(linha::text, '|' order by id_linha) from orcamento_itens where orcamento_id='$A1'")"
check "migração: cache mantém a chave e o resultado; sem expira_em" "tinta-x|0" "$(Ql "select chave||'|'||(select count(*) from information_schema.columns where table_name='cache_precos' and column_name in ('expira_em','criado_em')) from cache_precos")"
check "migração: fornecedor com rs_por_km, lat, lon e domínio normalizado" "2.50|-8.050000|-34.900000|leroymerlin.com.br" "$(Ql "select rs_por_km||'|'||lat||'|'||lon||'|'||dominio from fornecedores")"
# O esquema migrado precisa ser igual ao de um banco novo
esquema() { Ql "select md5(string_agg(table_name||'.'||column_name||':'||data_type||':'||coalesce(numeric_precision::text,'')||':'||coalesce(numeric_scale::text,'')||':'||is_nullable||':'||coalesce(column_default,''), ',' order by table_name, column_name)) from information_schema.columns where table_schema='public' and table_name in ('orcamentos','orcamento_itens','cache_precos','fornecedores')"; }
regras() { Ql "select md5(string_agg(conrelid::regclass||'.'||conname||'='||pg_get_constraintdef(oid), ',' order by conrelid::regclass::text, conname)) from pg_constraint where contype='c' and connamespace='public'::regnamespace"; }
E_MIG=$(esquema); R_MIG=$(regras); D=base; E_NOVO=$(esquema); R_NOVO=$(regras); D=rascunho
check "migração: colunas (nome, tipo, nulo, default) idênticas às de um banco novo" "$E_NOVO" "$E_MIG"
check "migração: regras (checks) idênticas às de um banco novo" "$R_NOVO" "$R_MIG"
Qs "update orcamento_itens set preco_emb_med=10 where orcamento_id='$A1' and id_linha='l2'"; check "migração: regra de preço sem fonte vale nos dados migrados" 3 $?
# Protocolo funciona sobre dados migrados
check "migração: reserva de orçamento 'pendente' migrado" 1 "$(reservar a3000000-0000-4000-8000-000000000003)"
check "migração: orçamento 'concluida' migrado só reabre com p_reabrir" "|3" "$(reservar $A1)|$(reservar $A1 180 true)"
IT_M=$(item_de $A1 l2)
check "migração: B grava item migrado" t "$(gravar $IT_M 3 "{\"status\":\"definido\",\"preco_un_med\":2.5,\"fontes\":$FONTE}")"
check "migração: tentativa velha recusada no item migrado" f "$(gravar $IT_M 2 '{"iteracoes":9}')"
check "migração: criar_orcamento novo funciona" criado "$(criar bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb hashM)"
check "migração: funções antigas removidas (iniciar_pesquisa, set_updated_at)" 0 "$(Ql "select count(*) from pg_proc where proname in ('iniciar_pesquisa','set_updated_at')")"
# Falha segura: fornecedor antigo sem CEP bloqueia a migração e desfaz tudo
novo_banco rascunho2
aplicar rascunho2 scripts/fixtures/002_rascunho_anterior.sql
D=rascunho2
Q "insert into fornecedores (nome,dominio,frete_por_km) values ('Sem dados','x.com',2)" >/dev/null
aplicar rascunho2; check "migração: fornecedor sem CEP/frete bloqueia com erro" 3 $?
check "migração: bloqueio desfaz tudo (rascunho intacto)" "estado" "$(Ql "select column_name from information_schema.columns where table_name='orcamentos' and column_name in ('estado','status_pesquisa')")"
D=base

echo; echo "Resumo: $ok ok, $falhou falha(s)"
[ "$falhou" -eq 0 ]
