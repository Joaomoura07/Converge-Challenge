# Renda dos arquitetos na PNAD Contínua

## Quanto os arquitetos por conta própria recebem em comparação com os demais?

### Takeaway

Uma tabulação própria dos microdados da PNAD Contínua estima que os **arquitetos de edificações por conta própria receberam R$ 668 milhões por mês**, ou **54,4% da renda habitual do trabalho principal** da ocupação no segundo trimestre de 2026. No mesmo trimestre de 2025, a estimativa foi de **R$ 557 milhões por mês e 50,0% da renda da ocupação**. São estimativas nacionais a partir da PNAD, em reais nominais de cada trimestre e com incerteza amostral. [Microdados do IBGE 2026](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/2026/) · [Microdados do IBGE 2025](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/2025/)

### Cited Findings

**Brasil, segundo trimestre de 2026.** Tabulação própria da PNAD Contínua. Renda mensal nominal do trabalho principal e população ponderada. [Microdados de origem](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/2026/PNADC_022026.zip)

| Posição na ocupação | Entrevistas com renda | Ocupados estimados com renda | Média mensal | Mediana mensal | Massa mensal | Parcela da massa |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conta própria | 243 | 106.498 | R$ 6.275 | R$ 5.000 | R$ 668,2 mi | 54,4% |
| Empregados | 146 | 68.387 | R$ 6.794 | R$ 4.000 | R$ 464,6 mi | 37,8% |
| Empregadores | 26 | 11.019 | R$ 8.661 | R$ 7.000 | R$ 95,4 mi | 7,8% |
| Empregados + empregadores | 172 | 79.406 | R$ 7.053 | R$ 4.860 | R$ 560,1 mi | 45,6% |
| Total | 415 | 185.904 | R$ 6.607 | R$ 5.000 | R$ 1.228,3 mi | 100,0% |

**Brasil, segundo trimestre de 2025.** Mesma tabulação em valores nominais de 2025. Comparação das parcelas dentro de cada trimestre dispensa deflação, enquanto comparar a evolução em reais entre os anos exigiria deflatores. [Microdados de origem](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/2025/PNADC_022025.zip) · [Deflatores da PNAD](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/Documentacao/PNADcIBGE_Deflator_Trimestral.pdf)

| Posição na ocupação | Entrevistas com renda | Ocupados estimados com renda | Média mensal | Mediana mensal | Massa mensal | Parcela da massa |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conta própria | 200 | 110.876 | R$ 5.024 | R$ 4.000 | R$ 557,0 mi | 50,0% |
| Empregados | 126 | 73.783 | R$ 6.260 | R$ 4.500 | R$ 461,9 mi | 41,5% |
| Empregadores | 19 | 10.070 | R$ 9.443 | R$ 7.000 | R$ 95,1 mi | 8,5% |
| Empregados + empregadores | 145 | 83.853 | R$ 6.643 | R$ 5.000 | R$ 557,0 mi | 50,0% |
| Total | 345 | 194.729 | R$ 5.721 | R$ 4.500 | R$ 1.114,0 mi | 100,0% |

- **Escopo e variáveis.** Arquitetos de edificações no trabalho principal (`V4010 = 2161`, COD), em domicílios amostrados no Brasil, ocupados na semana de referência (`VD4002 = 1`). A COD separa arquitetos paisagistas (2162) e reúne urbanistas com engenheiros de trânsito (2164), então esses códigos ficaram fora. Usou-se `VD4009 = 09` para conta própria, `08` para empregador e `01–07` para empregados. O rendimento mensal habitual do trabalho principal (`VD4016`) casa com a ocupação observada. `V1028` é o peso calibrado. Em cada trimestre uma entrevista de familiar auxiliar ficou fora da comparação de renda por `VD4016` ausente. Incluindo esse caso na base de ocupados, a parcela ponderada por conta própria foi de 56,8% em 2025 e 57,1% em 2026. [Classificação oficial, COD](https://www.ibge.gov.br/biblioteca/visualizacao/instrumentos_de_coleta/doc3098.pdf) · [Dicionário e layout oficiais](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/Documentacao/) · [Definições de VD4009 e VD4016](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/Documentacao/Definicao_variaveis_derivadas_PNADC_20200211.pdf)
- **Cálculo.** Massa do grupo = soma de `V1028 × VD4016`. Média = massa dividida pela soma dos pesos das pessoas do grupo com renda. Mediana = primeiro valor em que o peso acumulado após ordenar por renda alcança 50%. Parcela da massa = massa do grupo dividida pela massa da ocupação. Cálculo reproduzível com `tabular-pnad.mjs` e resultados em `PNAD-2025T2-agregados.json` e `PNAD-2026T2-agregados.json`, na mesma pasta. Para reproduzir, baixe um dos ZIPs oficiais, liste a entrada com `tar.exe -tf ARQUIVO.zip` e rode `node tabular-pnad.mjs ARQUIVO.zip NOME_DA_ENTRADA.txt`. O script lê diretamente do ZIP e só publica agregados. [Microdados e documentação](https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/)
- **Validação e incerteza.** Os campos de posição original e derivada concordaram em todas as observações do recorte, assim como o valor habitual derivado e a soma dos componentes. A soma ponderada de ocupados de todas as ocupações em 2026 reproduziu 103,1 milhões, arredondada como na divulgação oficial. Os ICs de 95% aproximados foram calculados por linearização de Taylor nos estratos e conglomerados (`Estrato`, `UPA`) de toda a amostra, sem correção de população finita. A parcela da massa dos conta própria ficou em **39,9% a 60,1%** em 2025 e **44,6% a 64,2%** em 2026. A estimativa da diferença de médias em 2026 foi de **−R$ 778/mês** para conta própria menos empregados e empregadores combinados, com IC aproximado de **−R$ 2.644 a +R$ 1.087**. O grupo de empregadores tem só 19 e 26 entrevistas e estimativa de massa com alta variabilidade. [Divulgação oficial do trimestre](https://www.gov.br/secom/pt-br/acompanhe-a-secom/noticias/2026/07/ibge-divulga-resultados-da-pnad-continua-referentes-ao-trimestre-encerrado-em-junho-de-2026/) · [Notas técnicas PNAD](https://www.ibge.gov.br/biblioteca/visualizacao/livros/liv101674_notas_tecnicas.pdf)

### Inferences

- A leitura defensável dos dois trimestres é que o grupo por conta própria recebeu **cerca de metade da renda profissional agregada** dos arquitetos de edificações. Os intervalos incluem 50% e se sobrepõem amplamente. Evitar dizer que a PNAD prova maioria financeira, diferença individual em 2026 ou aumento anual da participação.
- Os 51% do II Censo CAU se referem aos respondentes de uma pesquisa optativa de 2020 entre registrados. A PNAD mede a ocupação declarada no trabalho principal em 2025 e 2026. Cada base mantém seu próprio denominador e recorte. [CAU/BR, II Censo](https://caubr.gov.br/acesse-os-resultados-do-ii-censo-das-arquitetas-e-arquitetos-e-urbanistas-do-brasil/) · [Classificação COD e definição de ocupação](https://www.ibge.gov.br/biblioteca/visualizacao/instrumentos_de_coleta/doc3098.pdf)

### Gaps

- A medida é **rendimento habitual pessoal do trabalho**, que na PNAD é remuneração bruta do empregado ou retirada do autônomo/empregador. Em empreendimento sem registro específico da retirada, o IBGE considera receitas menos despesas. Faturamento bruto dos escritórios, orçamento das obras, compras de materiais e ausência de fornecedor fixo continuam fora da medida. [Notas técnicas da PNAD, seção de rendimento](https://www.ibge.gov.br/biblioteca/visualizacao/livros/liv101674_notas_tecnicas.pdf)
- Entre as tabelas publicadas do Censo 2022 e do SIDRA consultadas, posição na ocupação é divulgada separadamente ou com atividade econômica e o recorte de ocupação da tabela de renda aparece em grandes grupos. O cruzamento detalhado de COD 2161 com posição e renda foi obtido a partir dos microdados da PNAD, e não como tabela pronta do IBGE. [Censo 2022 Trabalho e rendimento](https://www.ibge.gov.br/estatisticas/Sociais/populacao/22827-censo-demografico-2022.html?edicao=44663) · [SIDRA 5439](https://sidra.ibge.gov.br/tabela/5439)
