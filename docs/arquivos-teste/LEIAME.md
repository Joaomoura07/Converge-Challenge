# Arquivos de teste — Orçamentista

Acervo de arquivos para testar o sistema no final: listas de materiais do jeito que arquitetos, clientes, mestres de obra e softwares (Revit, SketchUp, Excel, Word, apps) realmente produzem. **Não há gabarito**: a ideia é jogar os arquivos e conferir se o resultado faz sentido.

- Produtos de **marcas reais** do mercado brasileiro, escritos de três jeitos: completo (com marca e modelo), abreviado (como se fala na obra) e genérico (sem marca, deve virar *Pendente de Especificação*).
- Projetos, clientes, escritórios e lojas são **fictícios**; os endereços e CEPs são reais (ruas de Recife e região).
- Quantidades e embalagens são aproximações plausíveis, não catálogo oficial.

## Obras

| Pasta | Obra | Endereço | CEP |
|---|---|---|---|
| `01-apto-boa-viagem` | Reforma Apartamento Boa Viagem — 68 m² | Av. Boa Viagem, 2850, apto 1202 — Boa Viagem, Recife/PE | 51020-000 |
| `02-casa-terrea-aldeia` | Casa Térrea Aldeia — 120 m² (obra nova) | Estrada de Aldeia, 7215 — Aldeia dos Camarás, Camaragibe/PE | 54783-010 |
| `03-cozinha-gracas` | Cozinha Planejada — Apartamento nas Graças | Rua Amélia, 210, apto 801 — Graças, Recife/PE | 52011-050 |
| `04-banheiro-casa-forte` | Reforma do Banheiro Social — Casa Forte | Av. Dezessete de Agosto, 1480 — Casa Forte, Recife/PE | 52061-540 |
| `05-loja-rua-da-aurora` | Loja de Roupas — Rua da Aurora (45 m²) | Rua da Aurora, 325, térreo — Boa Vista, Recife/PE | 50050-000 |
| `06-escritorio-ilha-do-leite` | Escritório Corporativo — Ilha do Leite (220 m²) | Rua Senador José Henrique, 224, sala 1101 — Ilha do Leite, Recife/PE | 50070-460 |
| `07-clinica-derby` | Clínica Odontológica — Derby (90 m²) | Praça do Derby, 87, sala 4 — Derby, Recife/PE | 52010-140 |
| `08-restaurante-recife-antigo` | Restaurante — Recife Antigo (150 m²) | Rua do Bom Jesus, 183 — Recife, Recife/PE | 50030-170 |
| `09-area-gourmet-piscina` | Área Gourmet e Piscina — Aldeia | Estrada de Aldeia, 9101 — Aldeia dos Camarás, Camaragibe/PE | 54783-010 |
| `10-fachada-madalena` | Pintura de Fachada — Edifício Residencial na Madalena (6 pavimentos) | Rua Real da Torre, 640 — Madalena, Recife/PE | 50610-000 |
| `11-studio-boa-vista` | Studio para Aluguel por Temporada — Boa Vista (32 m²) | Rua do Príncipe, 211, apto 304 — Boa Vista, Recife/PE | 50050-035 |
| `12-casa-praia-porto-de-galinhas` | Casa de Praia — Porto de Galinhas | Rua da Esperança, 120 — Porto de Galinhas, Ipojuca/PE | 55595-084 |

## Arquivos

### 01-apto-boa-viagem

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `Tabela de acabamentos pisos e revestimentos.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só revestimentos e argamassas |
| `Tabela de acabamentos pintura.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só pintura |
| `Tabela de louças e metais.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só hidráulica, louças e metais |
| `Tabela de dispositivos elétricos e luminárias.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só elétrica e iluminação |
| `Tabela de esquadrias e ferragens.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só esquadrias, vidros e ferragens |
| `Orçamento de materiais R02 - Reforma Apartamento Boa Viagem.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_apto-boa-viagem.csv` | CSV | Lista consolidada de materiais | salvo pelo Excel pt-BR: ponto e vírgula, Windows-1252; nomes abreviados |
| `Lista de compras - Reforma Apartamento Boa Viagem (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos); nomes misturados |
| `Reforma_Apartamento_Boa_Viagem_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Reforma Apartamento Boa Viagem.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1100 - Casa Capibaribe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Casa Capibaribe Materiais de Construção |
| `PR-08 Quadro de acabamentos - Reforma Apartamento Boa Viagem.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `QUANTITATIVO_APTO_BOA_VIAGEM.xls` | XLS | Planilha antiga (Excel 97-2003) | aba 'Plan1'; cabeçalho em maiúsculas; nomes misturados |
| `WhatsApp Image 2026-10-14 at 09.00.00.jpeg` | JPEG | Foto de celular de uma lista escrita à mão | só os primeiros itens; com ruído/desfoque; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL (2).xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados; tem aba 'Rev01 (antiga)' com números desatualizados que deve ser ignorada |
| `briefing do cliente - Reforma Apartamento Boa Viagem.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `lista_materiais_INCOMPLETA.csv` | CSV | Lista enviada pela metade | INCOMPLETO: algumas quantidades vazias ou 'verificar' e algumas unidades em branco |

### 02-casa-terrea-aldeia

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `casa-terrea-aldeia_revestimentos_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só revestimentos e argamassas |
| `casa-terrea-aldeia_pintura_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só pintura |
| `casa-terrea-aldeia_hidraulica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só hidráulica, louças e metais |
| `casa-terrea-aldeia_eletrica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só elétrica e iluminação |
| `casa-terrea-aldeia_esquadrias_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só esquadrias, vidros e ferragens |
| `Orçamento de materiais R02 - Casa Térrea Aldeia.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_casa-terrea-aldeia.csv` | CSV | Lista consolidada de materiais | ponto e vírgula, UTF-8 com BOM; nomes abreviados |
| `Lista de compras - Casa Térrea Aldeia (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos), abreviações lt/cx/sc; nomes misturados |
| `Casa_Terrea_Aldeia_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Casa Térrea Aldeia.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1137 - Mangue Acabamentos.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Mangue Acabamentos e Revestimentos |
| `PR-08 Quadro de acabamentos - Casa Térrea Aldeia.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `quantitativos_casa-terrea-aldeia.ods` | ODS | Planilha do LibreOffice Calc | nomes misturados |
| `IMG_20260930_101300.png` | PNG | Foto/scan de lista escrita à mão | só os primeiros itens; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `export_quantitativos.csv` | CSV | Exportação que saiu vazia | ERRO: só o cabeçalho, nenhum item |

### 03-cozinha-gracas

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `Tabela de acabamentos pisos e revestimentos.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só revestimentos e argamassas |
| `Tabela de louças e metais.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só hidráulica, louças e metais |
| `Tabela de dispositivos elétricos e luminárias.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só elétrica e iluminação |
| `Tabela de esquadrias e ferragens.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só esquadrias, vidros e ferragens |
| `Orçamento de materiais R02 - Cozinha Planejada.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_cozinha-gracas.csv` | CSV | Lista consolidada de materiais | salvo pelo Excel pt-BR: ponto e vírgula, Windows-1252; nomes abreviados |
| `Lista de compras - Cozinha Planejada (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos); nomes misturados |
| `Cozinha_Planejada_report.html` | HTML | Relatório 'Generate Report' do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento |
| `Memorial descritivo - Cozinha Planejada.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1174 - Depósito Beberibe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Depósito Beberibe Ltda |
| `orcamento_cozinha-gracas.json` | JSON | Exportação de aplicativo de orçamento | estrutura com obra + itens |
| `WhatsApp Image 2026-10-21 at 11.26.00.jpeg` | JPEG | Foto de celular de uma lista escrita à mão | só os primeiros itens; com ruído/desfoque; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `briefing do cliente - Cozinha Planejada.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `Orçamento R03 - cozinha.xlsx` | XLSX | Arquivo corrompido (download interrompido) | ERRO: arquivo truncado, não abre |

### 04-banheiro-casa-forte

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `banheiro-casa-forte_revestimentos_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-16; todos os campos entre aspas; só revestimentos e argamassas |
| `banheiro-casa-forte_pintura_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-16; todos os campos entre aspas; só pintura |
| `banheiro-casa-forte_hidraulica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-16; todos os campos entre aspas; só hidráulica, louças e metais |
| `banheiro-casa-forte_eletrica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-16; todos os campos entre aspas; só elétrica e iluminação |
| `Orçamento de materiais R02 - Reforma do Banheiro Social.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_banheiro-casa-forte.csv` | CSV | Lista consolidada de materiais | ponto e vírgula, UTF-8 com BOM; nomes abreviados |
| `Lista de compras - Reforma do Banheiro Social (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos), abreviações lt/cx/sc; nomes misturados |
| `Reforma_do_Banheiro_Social_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Reforma do Banheiro Social.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1211 - Casa Capibaribe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Casa Capibaribe Materiais de Construção |
| `PR-08 Quadro de acabamentos - Reforma do Banheiro Social.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `lista_materiais_banheiro-casa-forte.xml` | XML | Exportação XML de sistema de gestão de obra | codificação ISO-8859-1; quantidade com vírgula decimal |
| `IMG_20261003_123900.png` | PNG | Foto/scan de lista escrita à mão | só os primeiros itens; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL (2).xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `briefing do cliente - Reforma do Banheiro Social.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `lista_colunas_trocadas.csv` | CSV | Lista com colunas trocadas | ERRO: os valores de 'Quantidade' e 'Unidade' estão invertidos |

### 05-loja-rua-da-aurora

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `Tabela de acabamentos pintura.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só pintura |
| `Tabela de dispositivos elétricos e luminárias.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só elétrica e iluminação |
| `Orçamento de materiais R02 - Loja de Roupas.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_loja-rua-da-aurora.csv` | CSV | Lista consolidada de materiais | salvo pelo Excel pt-BR: ponto e vírgula, Windows-1252; nomes abreviados |
| `Lista de compras - Loja de Roupas (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos); nomes misturados |
| `Loja_de_Roupas_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Loja de Roupas.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1248 - Mangue Acabamentos.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Mangue Acabamentos e Revestimentos |
| `PR-08 Quadro de acabamentos - Loja de Roupas.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `loja-rua-da-aurora_quantitativos.tsv` | TSV | Texto separado por tab copiado de planilha | sem categoria; nomes abreviados |
| `WhatsApp Image 2026-10-09 at 13.52.00.jpeg` | JPEG | Foto de celular de uma lista escrita à mão | só os primeiros itens; com ruído/desfoque; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `briefing do cliente - Loja de Roupas.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `Digitalização_20261017.pdf` | PDF | Lista escrita à mão digitalizada | PDF só com IMAGEM (sem texto selecionável): precisa de OCR |

### 06-escritorio-ilha-do-leite

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `escritorio-ilha-do-leite_revestimentos_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só revestimentos e argamassas |
| `escritorio-ilha-do-leite_pintura_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só pintura |
| `escritorio-ilha-do-leite_hidraulica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só hidráulica, louças e metais |
| `escritorio-ilha-do-leite_eletrica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só elétrica e iluminação |
| `escritorio-ilha-do-leite_esquadrias_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só esquadrias, vidros e ferragens |
| `Orçamento de materiais R02 - Escritório Corporativo.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_escritorio-ilha-do-leite.csv` | CSV | Lista consolidada de materiais | exportado de software de orçamento em inglês: vírgula e ponto decimal; nomes abreviados |
| `Lista de compras - Escritório Corporativo (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos), abreviações lt/cx/sc; nomes misturados |
| `Escritorio_Corporativo_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Escritório Corporativo.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1285 - Depósito Beberibe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Depósito Beberibe Ltda |
| `PR-08 Quadro de acabamentos - Escritório Corporativo.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `Compras Escritório Corporativo (export Notion).md` | MD | Checklist exportado do Notion | quantidades em EMBALAGENS; itens marcados [x] já comprados |
| `IMG_20260918_140500.png` | PNG | Foto/scan de lista escrita à mão | só os primeiros itens; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados; tem aba 'Rev01 (antiga)' com números desatualizados que deve ser ignorada |
| `lista_com_duplicados.csv` | CSV | Lista juntada de duas pessoas | ERRO: alguns itens aparecem duas vezes com nomes diferentes (abreviado e genérico) |

### 07-clinica-derby

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `Tabela de acabamentos pintura.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só pintura |
| `Tabela de louças e metais.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só hidráulica, louças e metais |
| `Tabela de dispositivos elétricos e luminárias.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; todos os campos entre aspas; só elétrica e iluminação |
| `Orçamento de materiais R02 - Clínica Odontológica.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_clinica-derby.csv` | CSV | Lista consolidada de materiais | salvo pelo Excel pt-BR: ponto e vírgula, Windows-1252; nomes abreviados |
| `Lista de compras - Clínica Odontológica (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos); nomes misturados |
| `Clinica_Odontologica_report.html` | HTML | Relatório 'Generate Report' do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento |
| `Memorial descritivo - Clínica Odontológica.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1322 - Casa Capibaribe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Casa Capibaribe Materiais de Construção |
| `PR-08 Quadro de acabamentos - Clínica Odontológica.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `QUANTITATIVO_CLINICA_DERBY.xls` | XLS | Planilha antiga (Excel 97-2003) | aba 'Plan1'; cabeçalho em maiúsculas; nomes misturados |
| `WhatsApp Image 2026-10-27 at 15.18.00.jpeg` | JPEG | Foto de celular de uma lista escrita à mão | só os primeiros itens; com ruído/desfoque; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL (2).xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `quantidades_unidades_bagunçadas.csv` | CSV | Lista digitada à mão | INCOMPLETO: unidade colada no número com grafias variadas (m2, M2, mts, un., pç), algumas erradas |

### 08-restaurante-recife-antigo

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `restaurante-recife-antigo_revestimentos_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação cp1252; sem aspas; só revestimentos e argamassas |
| `restaurante-recife-antigo_pintura_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação cp1252; sem aspas; só pintura |
| `restaurante-recife-antigo_hidraulica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação cp1252; sem aspas; só hidráulica, louças e metais |
| `restaurante-recife-antigo_eletrica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação cp1252; sem aspas; só elétrica e iluminação |
| `Orçamento de materiais R02 - Restaurante.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_restaurante-recife-antigo.csv` | CSV | Lista consolidada de materiais | ponto e vírgula, UTF-8 com BOM; nomes abreviados |
| `Lista de compras - Restaurante (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos), abreviações lt/cx/sc; nomes misturados |
| `Restaurante_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Restaurante.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1359 - Mangue Acabamentos.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Mangue Acabamentos e Revestimentos |
| `PR-08 Quadro de acabamentos - Restaurante.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `quantitativos_restaurante-recife-antigo.ods` | ODS | Planilha do LibreOffice Calc | nomes misturados |
| `IMG_20261006_093100.png` | PNG | Foto/scan de lista escrita à mão | só os primeiros itens; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `lista_materiais_acentos_quebrados.csv` | CSV | Arquivo aberto e salvo com a codificação errada | ERRO: acentos viraram 'Ã©', 'Ã§' (mojibake) |

### 09-area-gourmet-piscina

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `Tabela de acabamentos pisos e revestimentos.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só revestimentos e argamassas |
| `Tabela de acabamentos pintura.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só pintura |
| `Tabela de louças e metais.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só hidráulica, louças e metais |
| `Tabela de dispositivos elétricos e luminárias.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só elétrica e iluminação |
| `Orçamento de materiais R02 - Área Gourmet e Piscina.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_area-gourmet-piscina.csv` | CSV | Lista consolidada de materiais | salvo pelo Excel pt-BR: ponto e vírgula, Windows-1252; nomes abreviados |
| `Lista de compras - Área Gourmet e Piscina (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos); nomes misturados |
| `Area_Gourmet_e_Piscina_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Área Gourmet e Piscina.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1396 - Depósito Beberibe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Depósito Beberibe Ltda |
| `PR-08 Quadro de acabamentos - Área Gourmet e Piscina.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `orcamento_area-gourmet-piscina.json` | JSON | Exportação de aplicativo de orçamento | estrutura com obra + itens |
| `WhatsApp Image 2026-10-17 at 10.44.00.jpeg` | JPEG | Foto de celular de uma lista escrita à mão | só os primeiros itens; com ruído/desfoque; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `briefing do cliente - Área Gourmet e Piscina.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `lista_numeros_inconsistentes.csv` | CSV | Lista com números estranhos | ERRO: mistura de vírgula e ponto decimal e algumas áreas absurdas (×1000, digitadas em cm²?) |

### 10-fachada-madalena

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `fachada-madalena_pintura_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; todos os campos entre aspas; só pintura |
| `Orçamento de materiais R02 - Pintura de Fachada.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_fachada-madalena.csv` | CSV | Lista consolidada de materiais | exportado de software de orçamento em inglês: vírgula e ponto decimal; nomes abreviados |
| `Lista de compras - Pintura de Fachada (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos), abreviações lt/cx/sc; nomes misturados |
| `Memorial descritivo - Pintura de Fachada.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1433 - Casa Capibaribe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Casa Capibaribe Materiais de Construção |
| `PR-08 Quadro de acabamentos - Pintura de Fachada.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `lista_materiais_fachada-madalena.xml` | XML | Exportação XML de sistema de gestão de obra | codificação ISO-8859-1; quantidade com vírgula decimal |
| `IMG_20260925_115700.png` | PNG | Foto/scan de lista escrita à mão | só os primeiros itens; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL (2).xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `planilha_formulas_quebradas.xlsx` | XLSX | Planilha com fórmulas quebradas | ERRO: várias células com #REF! e #DIV/0! |

### 11-studio-boa-vista

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `Tabela de acabamentos pisos e revestimentos.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só revestimentos e argamassas |
| `Tabela de acabamentos pintura.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só pintura |
| `Tabela de louças e metais.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só hidráulica, louças e metais |
| `Tabela de dispositivos elétricos e luminárias.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só elétrica e iluminação |
| `Tabela de esquadrias e ferragens.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | lista simples; codificação utf-8; sem aspas; só esquadrias, vidros e ferragens |
| `Orçamento de materiais R02 - Studio para Aluguel por Temporada.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_studio-boa-vista.csv` | CSV | Lista consolidada de materiais | salvo pelo Excel pt-BR: ponto e vírgula, Windows-1252; nomes abreviados |
| `Lista de compras - Studio para Aluguel por Temporada (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos); nomes misturados |
| `Studio_para_Aluguel_por_Temporada_report.html` | HTML | Relatório 'Generate Report' do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento |
| `Memorial descritivo - Studio para Aluguel por Temporada.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1470 - Mangue Acabamentos.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Mangue Acabamentos e Revestimentos |
| `PR-08 Quadro de acabamentos - Studio para Aluguel por Temporada.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `studio-boa-vista_quantitativos.tsv` | TSV | Texto separado por tab copiado de planilha | sem categoria; nomes abreviados |
| `WhatsApp Image 2026-10-30 at 12.10.00.jpeg` | JPEG | Foto de celular de uma lista escrita à mão | só os primeiros itens; com ruído/desfoque; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `briefing do cliente - Studio para Aluguel por Temporada.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `Memorial descritivo - Studio para Aluguel por Temporada (sem quantitativos).docx` | DOCX | Memorial descritivo em Word SÓ com especificação | INCOMPLETO: não tem quantidades |

### 12-casa-praia-porto-de-galinhas

| Arquivo | Formato | O que simula | Observações |
|---|---|---|---|
| `casa-praia-porto-de-galinhas_revestimentos_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só revestimentos e argamassas |
| `casa-praia-porto-de-galinhas_pintura_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só pintura |
| `casa-praia-porto-de-galinhas_hidraulica_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só hidráulica, louças e metais |
| `casa-praia-porto-de-galinhas_esquadrias_revit.txt` | TXT (tab) | Exportação de tabela do Revit pt-BR | agrupada por ambiente com subtotais; codificação utf-8; sem aspas; só esquadrias, vidros e ferragens |
| `Orçamento de materiais R02 - Casa de Praia.xlsx` | XLSX | Orçamento do escritório (planilha formatada) | cabeçalho com dados da obra, seções por categoria, nomes completos com marca |
| `lista_materiais_casa-praia-porto-de-galinhas.csv` | CSV | Lista consolidada de materiais | ponto e vírgula, UTF-8 com BOM; nomes abreviados |
| `Lista de compras - Casa de Praia (WhatsApp).txt` | TXT | Mensagem de WhatsApp do mestre de obras / arquiteta | quantidades em EMBALAGENS (latas, caixas, sacos), abreviações lt/cx/sc; nomes misturados |
| `Casa_de_Praia_componentes.csv` | CSV | Relatório de componentes do SketchUp | só componentes contáveis; nomes de definição com underscore, sem acento; colunas em inglês |
| `Memorial descritivo - Casa de Praia.docx` | DOCX | Memorial descritivo em Word | texto corrido por ambiente + quadro-resumo em tabela; nomes completos |
| `Pedido de cotação 2026-1507 - Depósito Beberibe.pdf` | PDF | Pedido de cotação enviado a uma loja (texto selecionável) | quantidades em EMBALAGENS; loja fictícia: Depósito Beberibe Ltda |
| `PR-08 Quadro de acabamentos - Casa de Praia.pdf` | PDF | Prancha A3 com quadro de acabamentos por ambiente | tabela ambiente × piso/parede/teto; só acabamentos; carimbo de prancha |
| `Compras Casa de Praia (export Notion).md` | MD | Checklist exportado do Notion | quantidades em EMBALAGENS; itens marcados [x] já comprados |
| `IMG_20261011_132300.png` | PNG | Foto/scan de lista escrita à mão | só os primeiros itens; algumas linhas riscadas; quantidades em embalagens |
| `Quantitativo por ambiente v3 FINAL.xlsx` | XLSX | Planilha de rascunho do escritório, uma aba por ambiente | quantidades às vezes como texto ('24 m2', '12,50m²'); linhas em branco; nomes misturados |
| `briefing do cliente - Casa de Praia.txt` | TXT | Mensagem do cliente com o que ele quer | INCOMPLETO: só nomes GENÉRICOS (sem marca) e quantidades aproximadas |
| `quantitativo_misturado_outra_obra.xlsx` | XLSX | Planilha com sobra de outra obra no final | ERRO: últimas linhas são de outro projeto (há um aviso em texto no meio da planilha) |

## Resumo por formato

| Formato | Arquivos |
|---|---|
| TXT (tab) | 46 |
| XLSX | 27 |
| CSV | 27 |
| PDF | 24 |
| TXT | 19 |
| DOCX | 13 |
| JPEG | 6 |
| PNG | 6 |
| HTML | 3 |
| XLS | 2 |
| ODS | 2 |
| JSON | 2 |
| XML | 2 |
| TSV | 2 |
| MD | 2 |
| **Total** | **183** |
