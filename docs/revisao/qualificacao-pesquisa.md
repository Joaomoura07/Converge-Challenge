# Qualificação da pesquisa — 08/11/2026

Pedido: testar se a pesquisa detalhada confirma o produto solicitado e corrigir falhas, preservando os limites de chamadas e o uso de fontes diretas.

## Avaliação

Dez materiais sintéticos, cada um com uma oferta correta e uma variante incompatível: argamassa, tomada, cabo, joelho hidráulico, spot, porcelanato, bacia, tinta, torneira e chuveiro. Cada execução do fluxo pesquisa um item com dois anúncios. Busca, cache e respostas do modelo são simulados; nenhum preço desta avaliação representa uma cotação real.

O modelo simulado responde `SIM` até para a variante errada. Isso testa se a verificação determinística protege o cálculo quando o modelo ou um cache antigo estão incorretos.

Na primeira execução, **18 dos 31 testes novos falharam**. Entre os dez produtos, duas ofertas corretas foram descartadas e sete variantes incompatíveis foram confirmadas indevidamente. O fluxo completo selecionou somente a fonte correta em dois dos dez cenários. Também falhou a proteção contra cor de produto relacionado no trecho da página.

## Correções

- Classe AC-I/II/III, material reconhecido, conexão soldável/roscável e uso interno/externo agora participam da conferência. AC-3 e AC-III são equivalentes.
- Referências com `ref.`, `ref:`, código/modelo numérico e marcas explicitamente informadas são conferidas pelo valor completo. O anúncio não precisa repetir o rótulo.
- Dimensões com unidades são normalizadas: 60×60 cm corresponde a 600×600 mm, mas não a 60×60 mm. Sem unidade no anúncio, a escala exigida pelo pedido não é inventada.
- A similaridade usada nas ofertas estruturadas também respeita a equivalência de unidades.
- Cor, acabamento e outras especificações incompatíveis no título não são corrigidas por uma menção a outro produto no trecho. Variantes de cor misturadas no título não confirmam uma escolha específica.
- Acessórios explicitamente apresentados como “assento para bacia” são descartados quando o pedido é a bacia. “Bacia com assento” continua permitida.
- O agente só conta fontes que passam pelo cálculo para decidir parar. Um teste adicional reproduziu o encerramento precoce com três links de buscador; agora ele continua até encontrar duas fontes diretas, dentro do limite existente de duas reformulações.
- A observação enviada ao agente inclui motivos de descarte e até oito especificações não confirmadas, sem despejar páginas inteiras.

Essas verificações usam Python e não acrescentam chamadas de qualificação ao LLM. A correção da parada pode usar uma reformulação antes indevidamente omitida, respeitando os limites existentes.

## Resultado

- **53 verificações novas aprovadas**: produtos corretos, variantes incompatíveis, fluxo de pesquisa, ofertas estruturadas, referências, dimensões, similares e parada do agente.
- Nos dez materiais da amostra, o fluxo final confirmou somente a fonte correta em **10/10 cenários**. Oferta similar sozinha permaneceu estimativa com pergunta ao usuário.
- Suíte completa: **960 aprovados, 16 ignorados e 16 testes reais excluídos**, com tracing desativado e conexões Python externas bloqueadas.
- A suíte inclui a verificação TypeScript e os testes do frontend. Um aviso de decodificação da saída do Node no Windows foi corrigido usando UTF-8 explícito; os oito testes de interface foram executados novamente e passaram sem esse aviso.
- `git diff --check` aprovado. Os avisos restantes da execução ampla eram de depreciação de parâmetros do cliente Supabase, sem falha de teste.

O pedido anterior de não testar em servidor foi mantido: sem servidor de aplicação, `check_setup`, chamadas reais de pesquisa/LLM ou migrações de produção nesta revisão. Esses resultados medem os cenários controlados; não são uma taxa de acerto em anúncios reais. A interpretação de descrições livres, marcas/linhas não reconhecidas e páginas com múltiplos produtos ainda depende da evidência disponível e da extração pelo modelo.

Fontes locais: `tests/fatia_b/test_qualificacao_pesquisa.py`, `src/especificacao.py`, `src/calculo.py`, `src/google_shopping.py`, `src/precos.py` e `src/pesquisa.py`.
