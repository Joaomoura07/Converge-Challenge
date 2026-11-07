---
name: building-orca-ui
description: Implementa telas da Fatia A do Orça a partir do Figma, incluindo Nova obra, tabela de revisão, aceite de sugestões e resultado com useOrcamento. Use ao criar ou alterar componentes, formulários, estados da interface ou integração Realtime no frontend.
---

# Interface do Orça

Leia a etapa solicitada em `PLANO-FATIA-A.md` e os campos atuais em `CONTRATOS-B-C.md`. Reaproveite a estrutura de frontend existente. Next.js com TypeScript em `frontend/` foi registrado no contexto como escolha de Samuel.

## Referência e comportamento

- Consulte os quadros correspondentes no Figma indicado no contexto. A direção aprovada usa fundo papel, azul cobalto, títulos editoriais e divisórias finas. A divisão do time pede cota tracejada e hachura de 45 graus durante carregamento dos itens.
- Nova obra contém nome, CEP e orçamento do cliente. Cadastro manual e importadores alimentam a mesma tabela, com ID estável por linha e erros ligados ao campo.
- Preserve as edições ao alternar modos ou falhar no envio. Confirme a escolha entre acrescentar e substituir quando já houver itens.
- Correções e complementos são propostas. O clique Aceitar aplica uma sugestão uma vez. Editar a lista invalida sugestões calculadas sobre uma versão antiga.
- Diferencie visualmente quantidade estimada de complemento e preço estimado pela B. Preserve o significado de cada campo no contrato.
- Mostre estado vazio, leitura, revisão, envio e erro com ação de recuperação. Garanta rótulos, navegação por teclado e foco no erro relevante.

## Integração de resultado

- A entrega o esqueleto e `useOrcamento(id)`. B fornece ItemRow e C os componentes finais. Consulte o contrato antes de escrever os encaixes.
- O POST aguarda B na mesma requisição. Use o ID antecipado acordado para acompanhar Realtime e trate também sucesso/falha do POST.
- O hook consulta e acompanha as duas tabelas por orçamento, reconcilia a carga inicial com eventos, deduplica por ID, recupera estado ao reconectar e remove assinaturas ao desmontar.
- Observe `status_pesquisa` conforme o contrato da B para o botão de envio. A chave de serviço permanece no backend.
- Preços exibidos precisam de fontes. Conversões de embalagens vêm de B e cálculos de frete/viabilidade vêm de C.

## Verificação

Teste a ação solicitada pelo caminho normal do navegador, uma falha que preserve o trabalho e a largura de celular. Para Realtime, inclua reconexão e atualização ocorrida durante a carga inicial. Registre o que foi verificado e se a integração era real ou simulada.
