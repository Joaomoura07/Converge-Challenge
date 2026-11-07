# Aplicar o banco no Supabase

Passo a passo para criar as 4 tabelas, as funções, o RLS e o Realtime. Leva uns 2 minutos. Quem aplica: Samuel (dono do SQL).

## Antes
- O arquivo é `sql/002_orcamentos.sql`. Ele é idempotente: pode rodar de novo sem erro (cria o que falta, mantém os dados).
- Ele não precisa de extensões nem de papéis extras. Usa `anon`, `authenticated` e `service_role`, que o Supabase já tem.
- Só dados sintéticos: a leitura pública (`anon`) de `orcamentos` e `orcamento_itens` é do modelo da demo.

## Passos
1. Abra o projeto no Supabase → **SQL Editor** → **New query**.
2. Cole **todo** o conteúdo de `sql/002_orcamentos.sql` e clique em **Run**.
3. O Supabase pode abrir um aviso de "operação destrutiva" (por causa de `drop constraint` e `drop trigger`, que o arquivo usa para recriar regras). Pode confirmar: ele só recria regras e gatilhos; não apaga linhas.
4. Esperado: **Success. No rows returned**. Se aparecer erro, copie a mensagem inteira e mande ao Claude; o arquivo desfaz a transação inteira em erro de migração, então nada fica pela metade.
5. Abra outra query, cole `sql/verificar_supabase.sql` e clique em **Run**. Ele só lê; não altera nada.

## Resultado esperado da verificação
Uma tabela com as colunas `secao | item | situacao | detalhe`.
- A **última linha** (seção `9. RESUMO`) deve dizer `87 ok / 0 FALTA` e `situacao = ok`.
- Nenhuma linha com `FALTA`. Se houver, a coluna `item` diz o que faltou (tabela, coluna, função, política ou tabela fora do Realtime).
- Seções: 1 tabelas (4, com RLS ligado), 2 colunas (as listadas por Enzo e João), 3 funções (`reservar_pesquisa`, `gravar_resultado_item`, `finalizar_pesquisa`, `renovar_pesquisa`, `criar_orcamento`, executáveis só por `service_role`), 4 políticas RLS (`leitura_publica` em `orcamentos` e `orcamento_itens`), 5 Realtime (`orcamentos` e `orcamento_itens` na publicação `supabase_realtime`).

## Depois
- Avise Enzo e João que o banco está no ar. Eles usam a chave `service_role` (nunca no navegador) e as funções via `supabase.rpc(...)`.
- Seed de `fornecedores`: insira as lojas (João) com `nome, dominio, cep, frete_base, rs_por_km, pedido_minimo` (e `lat`, `lon` se tiver).
- Se o número do resumo mudar (coluna nova), o `87` muda; o que vale é **0 FALTA**.

## O que este passo a passo não garante
O SQL foi testado em Postgres 16 descartável com papéis simulados. A primeira aplicação no Supabase real é a verdadeira prova: se a verificação acusar `FALTA` ou o Run der erro, pare e reporte.
