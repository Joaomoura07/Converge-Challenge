# Renda e posição profissional nos levantamentos CAU

## O mesmo grupo citado como 51% pode ser comparado por renda?

### Takeaway

Sim, pelas **faixas de renda individual mensal** dos microdados públicos do II Censo CAU 2020. O grupo que declarou autonomia na área é 21.260 de 41.897 com fonte de renda informada, ou **50,74%**. Com faixa de renda válida, **59,19%** dos autônomos declararam até três salários mínimos, contra **43,21%** dos demais. O levantamento usa faixas de renda pessoal de todas as fontes e permite analisar a distribuição, mas a soma exata em reais e o faturamento da atividade ficam em aberto.

### Cited Findings

- A coleta optativa ocorreu no primeiro semestre de 2020 e o CAU divulgou o resultado em dezembro de 2021. A autarquia publicou 41.897 profissionais ouvidos, 51% prestadores autônomos e renda pessoal por faixas. O questionário e a dissertação que usou o arquivo documentam “Acerca de sua(s) fonte(s) de renda?” e “Qual a sua renda mensal individual, aproximadamente?”. Há campo separado de renda familiar. [Divulgação CAU/BR](https://caubr.gov.br/acesse-os-resultados-do-ii-censo-das-arquitetas-e-arquitetos-e-urbanistas-do-brasil/) · [Dissertação Ana Laterza, UnB, Anexo 2](https://repositorio.unb.br/bitstream/10482/49383/1/AnaLaterza_DISSERT.pdf)
- A página do painel oficial expõe o link “Baixar base de dados”. O ZIP público de 33.509.632 bytes contém `CENSO-BASE DE DADOS-para dashboard-r01.xlsx`, aba `pivotado`, linhas de dados 4–45388. Extraí a fonte de renda (indicadores G–S, com L para autonomia em arquitetura e urbanismo e M para autonomia em outra área) e a renda individual (Z–AH, com AH para NULL). As categorias de renda declarada são mutuamente exclusivas. As fontes de renda admitem múltiplas marcas. [Página do painel](https://caubr.gov.br/censo2020/?page_id=20) · [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)
- Validação dos denominadores: 45.385 registros, 3.488 sem fonte declarada, 41.897 com fonte declarada, 10.305 com mais de uma fonte. Dos 21.260 autônomos em arquitetura e urbanismo, 7.525 (35,40%) também marcaram outra fonte. Considerando somente quem informou a fonte e uma faixa de renda pessoal, N=40.911 (986 sem faixa válida). A base inteira tem 4.243 sem faixa pessoal válida e 41.142 com faixa válida. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)
- O total de todos os 41.142 com faixa válida, antes de cruzar com fonte, reproduz os percentuais de renda arredondados do CAU (35,50% em 1–3 SM, 26,45% em 3–6 SM, 11,33% em 6–9 SM, 10,33% em até 1 SM, 5,64% sem renda). Os 41.897 com fonte e os 50,74% autônomos em A&U reconciliam os números divulgados pelo CAU. [Divulgação CAU/BR](https://caubr.gov.br/acesse-os-resultados-do-ii-censo-das-arquitetas-e-arquitetos-e-urbanistas-do-brasil/) · [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)

### Comparação descritiva por grupo

SM de R$ 998 segundo as opções do questionário. “Até 3 SM” inclui renda zero e todos os rendimentos até R$ 2.994,00. “Acima de 6 SM” corresponde à soma das quatro faixas acima de R$ 5.988,00. Faixa mediana é o intervalo em que a distribuição acumulada atinge 50%. Os percentuais usam só os integrantes com fonte e faixa individual válida. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)

| Grupo | N com faixa | Até 3 SM | Acima de 6 SM | Acima de 15 SM | Faixa mediana |
| --- | ---: | ---: | ---: | ---: | --- |
| Declarou autonomia em arquitetura e urbanismo | 20.756 | 59,19% | 14,38% | 1,27% | 1–3 SM |
| Demais com fonte informada, sem declarar autonomia em arquitetura e urbanismo | 20.155 | 43,21% | 30,20% | 4,49% | 3–6 SM |
| Somente autônomo em arquitetura e urbanismo | 13.374 | 65,51% | 10,27% | 0,62% | 1–3 SM |
| Somente assalariado público ou privado em arquitetura e urbanismo | 7.757 | 29,77% | 37,46% | 3,98% | 3–6 SM |
| Somente assalariado privado em arquitetura e urbanismo | 4.202 | 42,69% | 25,80% | 1,76% | 3–6 SM |
| Somente assalariado público em arquitetura e urbanismo | 3.555 | 14,49% | 51,25% | 6,61% | 6–9 SM |
| Somente empresário em arquitetura e urbanismo | 2.702 | 26,39% | 40,12% | 7,59% | 3–6 SM |
| Sem autonomia declarada em qualquer área | 18.397 | 40,64% | 32,09% | 4,82% | 3–6 SM |

A primeira e segunda linhas particionam o grupo do 51% contra o restante. As linhas de “somente” são subgrupos de fonte exclusiva, úteis para evitar atribuir renda de outras fontes ao vínculo em questão. A segunda linha inclui quem marcou autonomia **em outra área**. O último grupo exclui qualquer autonomia. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)

### Contagens por faixa para auditoria

| Grupo | Sem renda | Até 1 SM | 1–3 SM | 3–6 SM | 6–9 SM | 9–12 SM | 12–15 SM | Acima de 15 SM | Faixa ausente |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Autônomo em A&U, inclusive misto | 1.071 | 2.712 | 8.503 | 5.485 | 1.722 | 725 | 274 | 264 | 504 |
| Demais com fonte informada, sem autônomo em A&U | 1.158 | 1.507 | 6.043 | 5.361 | 2.933 | 1.531 | 717 | 905 | 482 |
| Somente autônomo em A&U | 870 | 2.017 | 5.874 | 3.240 | 865 | 315 | 110 | 83 | 361 |
| Somente assalariado em A&U, público ou privado | 23 | 154 | 2.132 | 2.542 | 1.584 | 742 | 271 | 309 | 128 |
| Somente empresário em A&U | 40 | 122 | 551 | 905 | 474 | 269 | 136 | 205 | 96 |

Fonte de todas as linhas. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)

### Inferences

- Em 2020, os respondentes que declararam atuação autônoma em A&U se concentravam em faixas de renda individual inferiores às dos demais respondentes. A diferença é descritiva e pode refletir idade, experiência, horas trabalhadas, especialidade, outras fontes e seleção do levantamento voluntário. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip) · [Divulgação CAU/BR](https://caubr.gov.br/acesse-os-resultados-do-ii-censo-das-arquitetas-e-arquitetos-e-urbanistas-do-brasil/)
- O questionário pede renda individual aproximada e registra múltiplas fontes, como assalariamento, aposentadoria e aluguel. Portanto, o total da renda pessoal de quem se declara autônomo seria diferente do dinheiro que esse grupo gerou com serviços de arquitetura, mesmo se os valores exatos fossem conhecidos. [Dissertação Ana Laterza, UnB, Anexo 2](https://repositorio.unb.br/bitstream/10482/49383/1/AnaLaterza_DISSERT.pdf)

### Gaps

- A faixa máxima é aberta (>15 SM), com 264 autônomos e 905 demais respondentes nela. Em ambos os grupos, o total de renda pessoal pode variar dentro das faixas e a cauda tem teto desconhecido. A massa e sua divisão em reais não são identificáveis sem hipóteses adicionais.
- A base do CAU não fornece valor faturado pelos projetos, custo de materiais nem fornecedores. Nenhuma expansão da amostra voluntária para o total de profissionais foi feita.

## O que já havia sido publicado em outras pesquisas do CAU?

### Takeaway

Há cruzamento publicado de renda por propriedade de empresa em 2012 e faixas gerais de renda em 2019. As fontes trabalham com renda pessoal e indicadores de perfil.

### Cited Findings

- O I Censo CAU 2012 (publicação com tabela na seção Renda, p. 12) cruza posse de pessoa jurídica própria com a faixa de renda pessoal. Dentro da faixa de 1–3 SM, 4,18% tinham PJ mista e 4,92% PJ uniprofissional (9,10% somados). Acima de 20 SM, as participações eram 22,06% e 29,59% (51,65% somados). A tabela condiciona por faixa de renda. Posse de PJ não equivale a deixar de ser autônomo. [I Censo CAU/BR, seção Renda](https://caubr.gov.br/wp-content/uploads/2018/03/Censo_CAUBR_06_2015_WEB.pdf#page=12) · [Comparativo oficial 2012–2020](https://caubr.gov.br/wp-content/uploads/2021/12/Comparativo-Censo-2012-2020.pdf)
- A pesquisa CAU/Datafolha 2019 entrevistou 1.500 profissionais e 500 empresas, amostra distribuída por idade e geografia da base registrada. 55% dos profissionais foram classificados como liberais ou autônomos, e 50% do total declararam mais de cinco salários mínimos de renda, sem tabela pública de cruzamento na divulgação encontrada. A comunicação usa “faturar” na frase da faixa, mas situa a variável no parágrafo de renda dos profissionais e não publica receita bruta de serviços para esses grupos. [Perfil CAU/Datafolha 2019](https://caubr.gov.br/pesquisa-cau-br-revela-perfil-profissional-dos-arquitetos-e-urbanistas-brasileiros/) · [Metodologia resumida](https://caubr.gov.br/arquitetos-e-urbanistas-avaliam-positivamente-servicos-do-cau/)
- A dissertação de Ana Laterza (UnB) utilizou os microdados de 2020 para análise de desigualdades. A seção “2. renda”, Figura 37, posiciona a categoria de autonomia em A&U próxima à renda de 1–3 SM em análise exploratória de correspondência. A interpretação descritiva agora tem contagem direta pelos grupos acima. O trabalho identifica explicitamente a pergunta de renda individual, separada da renda familiar. [Dissertação, Figura 37 e Anexo 2](https://repositorio.unb.br/bitstream/10482/49383/1/AnaLaterza_DISSERT.pdf)

### Inferences

- Há evidência de diferença de distribuição salarial entre perfis e da concentração de donos/sócios nas faixas mais altas em outra rodada. As categorias, amostras e anos são distintos, de modo que as proporções não compõem uma série quantitativa de participação da massa de renda. [I Censo CAU/BR](https://caubr.gov.br/wp-content/uploads/2018/03/Censo_CAUBR_06_2015_WEB.pdf) · [II Censo CAU/BR](https://caubr.gov.br/acesse-os-resultados-do-ii-censo-das-arquitetas-e-arquitetos-e-urbanistas-do-brasil/)

### Gaps

- A publicação integral de tabelas detalhadas do CAU/Datafolha 2019 por vínculo e renda não foi localizada. As notícias e o relatório de gestão apontam para os resumos acima. [Relatório de gestão 2019](https://transparencia.caubr.gov.br/arquivos/relatoriodegestao2019.pdf)

## Como reproduzir o cruzamento sem distribuir os microdados?

### Takeaway

O script `cau_censo2020.py` lê a planilha por linhas, sem exportar observações individuais. Executar os dois comandos na pasta das notas após descompactar o ZIP oficial. O TSV intermediário contém combinações agregadas, não linhas individuais.

```powershell
python cau_censo2020.py 'CENSO-BASE DE DADOS-para dashboard-r01.xlsx' G H I J K L M N O P Q R S Z AA AB AC AD AE AF AG AH |
  Set-Content -Encoding utf8 agrupado.tsv
python cau_censo2020.py --summary agrupado.tsv
```

### Cited Findings

- O ZIP e a planilha examinados correspondem, respectivamente, aos SHA-256 `1BC9E6E2DCBD6417408528DA36244E3FE7C79A93AEC946EB803ACFBB0D5833A4` e `A69E447785ABA1000B8399238D9728859468A70418BCB6529207F31D9B68AEE7`. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)
- No arquivo, fonte declarada é ao menos um indicador em G–R. Fonte autônoma de A&U é L=1 e outras fontes admitem múltipla marca. A renda válida é exatamente uma marca em Z–AG, com categorias públicas listadas no questionário. [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip) · [Dissertação, Anexo 2](https://repositorio.unb.br/bitstream/10482/49383/1/AnaLaterza_DISSERT.pdf)

### Inferences

- As contagens de amostra que reproduzem o 51% e as frequências gerais de renda oferecem verificações independentes do recorte. [Divulgação CAU/BR](https://caubr.gov.br/acesse-os-resultados-do-ii-censo-das-arquitetas-e-arquitetos-e-urbanistas-do-brasil/) · [Microdados públicos do CAU](https://caubr.gov.br/censo2020/wp-content/uploads/2021/12/CENSO-BASE-DE-DADOS-para-dashboard-r01.zip)

### Gaps

- O cruzamento foi calculado a partir do ZIP e validado contra os totais divulgados. O painel interativo Power BI não foi usado na extração.
