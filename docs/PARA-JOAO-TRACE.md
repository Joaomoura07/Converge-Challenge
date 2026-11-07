# Para o João: link do trace e totais (backend, 07/11 noite)

O backend agora grava em `orcamentos`, no fim de cada pesquisa:

| Coluna | O que é | Sugestão de uso na tela |
|---|---|---|
| `trace_url` | Link **público** do trace no Langfuse (abre sem login) | Link discreto no resultado: "Ver o raciocínio da IA" (abre em nova aba) |
| `tempo_ms` | Duração da pesquisa | Já existe o ganho; opcional |
| `total_min`, `total_med`, `total_max` | Os mesmos totais de `viabilidade` | Opcional (já estão em `viabilidade`) |

- `trace_url` pode vir `null` (Langfuse fora ou orçamento antigo): esconda o link nesse caso.
- `viabilidade.estimado_med` (novo) diz quanto da média é estimativa de itens pendentes, e o `resumo` já explica isso
  em texto. O subtotal da tela (só definidos) e a média da viabilidade (definidos + estimativas) continuam diferentes
  de propósito.
- Depois de "Responder", se só houver produtos parecidos, o item volta **definido** com `confianca: "baixa"`,
  `estimativa: true` e um `motivo` ("produto mais próximo..."): vale mostrar o motivo nesse caso.
