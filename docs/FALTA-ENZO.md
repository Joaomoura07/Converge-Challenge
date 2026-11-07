# O que falta: Fatia B e entrega (atualizado 07/11, ~18h)

> Submissão **domingo até 13h** (meta 12h30): descrição, **vídeo de até 2 min**, link, material de apresentação,
> ferramentas/modelos/APIs. **Das 13h às 17h os jurados testam o link sozinhos e escolhem 5 grupos** para a final.
> Textos da B prontos para o formulário: `docs/SUBMISSAO-FATIA-B.md`.

## Backend da Fatia B: feito e publicado
- Rodízio das 3 chaves da Featherless (`FEATHERLESS_API_KEYS`), reserva Mistral em paralelo quando o principal demora.
- Busca aberta na região do CEP da obra (+ lista fixa de lojas): 2,1 lojas por item com preço (eram 1,4).
- Janela da reserva de 6 min (> 300 s da função); agente com 90 s na fase 2.
- **Cache aquecido para os 3 exemplos do botão "Usar arquivo de exemplo"** (apto Boa Viagem, casa térrea Aldeia,
  escritório Ilha do Leite), para o jurado ver tudo rápido e igual ao vídeo.
- Um orçamento real já rodou pelo site: 16 itens em 49 s (11 definidos, 4 pedindo especificação, 1 não encontrado).

## Para o time dividir (manual)
| Tarefa | Quem | Quando |
|---|---|---|
| **Vídeo de até 2 min**: exemplo → revisão → "Enviar para a IA" → itens chegando → responder uma pergunta → resultado | ? | domingo cedo (depois do aquecimento, já feito) |
| **Testar o link publicado como jurado**: aba anônima e celular, os 3 exemplos, "Responder" e "Pesquisar de novo" | ? | hoje à noite |
| Descrição do projeto + slides (colar `docs/SUBMISSAO-FATIA-B.md` na parte do agente) | Fatia D | até domingo 11h |
| Preencher o formulário de submissão | Fatia D | até 12h30 |
| Conferir a cota do Tavily (3 chaves × 1.000/mês) | Enzo | domingo 8h |
| Se a cota estiver baixa: desligar a busca aberta (`PESQUISA_BUSCA_ABERTA=false` na Vercel do backend + redeploy) | Enzo | domingo 8h |
| Ensaiar o pitch de 3 min (só se passar no corte, às 17h) | todos | domingo à tarde |
| Cancelar os planos da Featherless das 3 chaves | donos das chaves | depois do evento |

## Não fazer
- **Não rodar `sql/004_fornecedores_seed.sql`**: é de um esquema antigo (`id` texto) e o frete está em pausa
  (`FRETE_ATIVO` desligado no código da C). O erro "invalid input syntax for type uuid" não gravou nada.
- Não dar push na `main` sem avisar o time (deploy automático na Vercel).

## Riscos para a demo
- Featherless oscila: com cache não afeta; sem cache, um orçamento de 24 itens leva ~1,5 min.
- Itens fora dos exemplos (upload do jurado) são pesquisados ao vivo: ~1 em 5 pode sair sem preço confirmado.
- Leroy Merlin não mostra preço na página que a busca lê.
