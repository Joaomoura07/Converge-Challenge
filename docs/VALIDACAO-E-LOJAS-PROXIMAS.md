# Conferência de preço (Serper) e lojas próximas: estado e o que falta ligar

Código pronto e testado **sem rede**. Nada roda até existirem as chaves. O formato real das respostas do Serper (`/shopping` e `/places`) e do OpenRouteService **ainda não foi conferido com chave de verdade**: a leitura é defensiva e o teste com chave está na lista abaixo.

## O que existe
| Peça | Arquivo | O que faz |
|---|---|---|
| Conferência de preço | `src/validacao_serper.py` | Compara o preço do item com a mediana de anúncios parecidos no Google Shopping. Até 25% de diferença = `confirmado`; até 50% = `divergente_leve`; acima = `divergente` (confiança cai para `baixa`); menos de 2 anúncios comparáveis = `sem_dados`. **Nunca troca o preço nem entra em `fontes`** |
| Gancho | `src/orcamento.py` (`_gravar_e_conferir`) | Grava o item (a tela já mostra) e, com chave, confere e regrava só o campo novo. Falha da conferência não afeta o item |
| Campo novo | `src/modelos.py` (`Validacao`, `ResultadoItem.validacao`) | `{status, fonte, mediana, diferenca_pct, n}` |
| Lojas próximas | `src/proximidade.py`, `GET /lojas-proximas?cep=` | Lojas das redes da lista fixa perto do CEP (Serper `/places`), com km e minutos de carro (OpenRouteService; sem chave, estimativa marcada `aproximado`) |
| Config | `src/config.py`, `.env.example` | `SERPER_API_KEYS` (várias, rodízio) e `ORS_API_KEY` |

## O que falta (manual e com outras pessoas)
- [ ] Criar chave no serper.dev e no openrouteservice.org; colocar `SERPER_API_KEYS` e `ORS_API_KEY` no `.env` e na Vercel (sem aspas).
- [ ] Samuel: `alter table orcamento_itens add column if not exists validacao jsonb;`. Sem a coluna o item grava mesmo assim (o código tira a coluna ausente da gravação), só sem a conferência.
- [ ] Teste com chave: cerca de 10 buscas `/shopping` e 3 `/places` para confirmar os campos (`title`, `price`, `latitude`, `longitude`), o custo em créditos e a cota; ajustar a leitura se o formato for diferente.
- [ ] Medir na obra Cozinha Graças: % confirmado e % divergente; calibrar os limites de 25% e 50% (constantes em `validacao_serper.py`).
- [ ] João: usar o tempo e a lista de lojas próximas na logística (`src/logistica.py`, `src/rotas_resultado.py`; ele é o dono).
- [ ] Mostrar na tela do item um selo "conferido no Google" ou "difere do Google" (campo `validacao`).
- [ ] O cache das lojas próximas é em memória e some quando a função da Vercel reinicia; para guardar de verdade falta uma tabela (combinar com o Samuel).

## Limites que valem lembrar
- O Google Shopping lista marketplaces e vendedores diferentes: serve para detectar preço muito fora, não para provar que o preço está certo.
- A comparação só considera anúncios cujo título cita a mesma unidade de medida (litros, m², kg, unidades) e converte para o preço por unidade base.
- O custo de crédito do Serper por chamada e o limite diário do OpenRouteService não foram confirmados.
