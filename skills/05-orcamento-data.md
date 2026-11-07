---
name: managing-orcamento-data
description: Alinha SQL, contratos FastAPI/Pydantic, persistência Supabase, RLS e concorrência da Fatia A com as escritas das fatias B e C. Use ao criar ou revisar 002_orcamentos.sql, RPCs, reenvio de orçamento, reserva da pesquisa, migrações ou testes de banco.
---

# Dados e contratos do orçamento

Leia `CONTRATOS-B-C.md`, a etapa atual do contexto e o código dos chamadores disponíveis. A é responsável pelo SQL das quatro tabelas; B reserva a pesquisa dentro de pesquisar_orcamento e C cadastra fornecedores. Trate propostas e contratos confirmados separadamente.

## Compatibilidade

- Compare nomes, tipos, defaults e estados com os campos exatos de B/C. Ao mudar uma coluna, revise RPCs, chaves JSON permitidas, triggers, retornos, modelos e testes que a usam.
- `status_pesquisa` descreve a execução do orçamento. `status` do item usa buscando, definido, pendente_especificacao, nao_encontrado ou erro. A classificação inicial tem significado próprio.
- `orcamento_cliente` deve existir na obra recebida pela API e na persistência. Preserve centavos e CEP com zero inicial.
- Registre uma representação única para aceite, regra e linhas de origem dos complementos. Diferencie motivo e estimativa de consumo daqueles produzidos pela pesquisa de preço.

## Escrita e concorrência

- Salve orçamento e itens atomicamente. Reenvio com mesmo ID e conteúdo recupera o orçamento; conteúdo diferente produz conflito. Proteja também chamadas simultâneas no banco.
- A reserva pertence à B. Um protocolo de tentativa/heartbeat precisa ser usado consistentemente por quem reserva, grava e finaliza. Confirme compatibilidade com o chamador antes de declarar a integração concluída.
- Tempo decorrido sozinho não comprova término de execução. Teste execução lenta e retomada. Validação da tentativa, gravação e renovação precisam ser atômicas em relação à troca de execução, com ordem consistente de bloqueios.
- Teste a corrida controlada em que uma tentativa muda enquanto um item está sendo gravado. Quantidade de chamadas paralelas, isoladamente, não prova essa proteção.
- Qualquer preço preenchido, por embalagem ou unidade, exige fontes válidas, inclusive em estimativas. Grave preços e fontes na mesma operação.

## Migração e acesso

- Confira se a versão anterior já foi aplicada. CREATE TABLE IF NOT EXISTS não atualiza o esquema de uma tabela existente. Prepare alterações que preservem dados e teste atualização além da criação limpa quando aplicável.
- As duas tabelas de acompanhamento entram no Realtime. Escritas da aplicação usam o backend; leitura anon segue o modelo explícito da demo sintética. Registre o alcance das políticas e teste com os papéis correspondentes.
- Use banco descartável para validar migração, rollback e concorrência. Aplicação remota segue a autorização de publicação da sessão.

## Evidência da entrega

Reaproveite `scripts/testar_sql_orcamentos.sh` quando existir. Inclua casos de sucesso, falha parcial, reenvio equivalente, conflito, escrita exata de B/C, preços sem fonte e tentativa obsoleta. Diferencie testes locais, papéis simulados e verificação no Supabase real. Entregue o SQL completo para revisão do time quando solicitado.
