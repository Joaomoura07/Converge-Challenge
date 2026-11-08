# Revisão do fluxo PDF, DXF, IFC e SKP

Data: 08/11/2026. Pedido: testar em lotes de até 10 itens, corrigir o fluxo existente e apenas avaliar a ideia RVT/DWG/Archicad → IFC.

## Escopo e preservação do trabalho

Consultados README, instruções do projeto, contratos A/B/C, plano da Fatia A, importadores, lista/revisão/envio, rotas e testes de integração/resultado. A referência remota foi consultada e atualizada por `git fetch`, sem merge nem push. O HEAD remoto observado foi `b71cb67`; as diferenças de código em relação ao checkout estavam em Caderno e Shell. A árvore já continha numerosas alterações de outros trabalhos, preservadas.

Após o pedido explícito “não teste em servidor por enquanto”, o servidor local foi encerrado. A finalização usa testes locais e compilação. Não houve publicação.

## Falhas reproduzidas e correções

- PDF: fragmentos da mesma célula eram interpretados separadamente, perdendo a descrição. Agora são reunidos por coluna e linha.
- PDF: material com quantidade vazia e unidade preenchida podia ser anexado ao material anterior. A continuação exige somente descrição e proximidade na mesma página; a linha incompleta permanece revisável.
- PDF: falha de leitura de página retorna erro estruturado; não entrega importação parcial. A página de origem acompanha cada item.
- DXF: bulges de polilinhas eram tratados como retas. Comprimento e área incluem o segmento circular, inclusive sentido horário e círculo de dois vértices. Medidas não positivas ou infinitas ficam pendentes.
- IFC: unidade explícita de IfcQuantityArea e de propriedades numéricas era ignorada. Exemplo reproduzido: 12,5 m² virava 12.500.000 m². A unidade local agora prevalece, com conversão SI e unidades convertidas, rejeitando referências inválidas.
- IFC: zero, negativo e infinito deixam quantidade pendente; unidades convertidas compartilham o mesmo resolvedor, com proteção de referências cíclicas.
- SKP: cobertura era contada como uma peça. Coberturas, telhados, vigas, pilares, concreto e pintura exigem medida revisada.
- Envio: descrição original, pavimento/ambiente e extras do arquivo se perdiam na transformação para a tabela. Agora sobrevivem à edição e ao corpo da API.
- O limite de 20 MB é conferido no ponto de entrada de todos os formatos antes de carregar o leitor.
- A prévia do ItemRow foi alinhada ao site para preservar a resposta digitada ao reabrir a especificação. Esse arquivo já tinha alterações anteriores à sessão.

## Evidência

Os 12 primeiros testes novos falharam antes das correções. A matriz final tem 20 casos novos, com no máximo 3 itens por arquivo, e a execução direcionada totalizou **57 testes aprovados**. TypeScript e build de produção aprovados. O build precisou executar fora do isolamento por um erro EPERM ao criar uma pasta em `.next`; não iniciou servidor.

Antes da restrição de servidor, os testes locais com TestClient, banco e preços simulados comprovaram os quatro formatos até persistência, resultado, exportação Excel/PDF, reenvio idempotente, conflito e rejeição de quantidade ausente: **27 aprovados e 1 ignorado**, incluindo oito casos novos. Houve um aviso de decodificação CP1252 no teste que captura a saída do npm; a execução direta posterior dos testes TypeScript produziu saída e aprovação normais.

A suíte inicial de frontend tinha 558 aprovações. A primeira suíte geral de backend teve 851 aprovações, 17 ignorados, 16 testes reais excluídos e duas falhas (tipagem do novo teste e divergência do ItemRow), corrigidas e verificadas na rodada direcionada. Os testes históricos incluem amostras maiores; os novos ensaios desta revisão respeitam o teto de 10 itens.

O verificador real `python -m scripts.check_setup` foi executado **antes** da restrição posterior: Featherless (três chaves), tool calling, Langfuse, Supabase e DuckDuckGo responderam. Tavily: uma chave sem cota e duas funcionando. Custo informado pela Featherless: US$ 0,001720275. O código existente já trata falha de cota e troca de chave. Nenhum segredo foi registrado aqui.

No navegador, a obra sintética foi criada apenas no estado da página e a aba PDF foi aberta. O upload foi recusado pelo controle de autorização do navegador. Não houve tentativa de contornar o bloqueio. A validação visual dos uploads, dos workers e do fluxo ao vivo permanece pendente; os testes de arquivos executaram os leitores reais localmente. Não se deve afirmar que o fluxo publicado ou todas as versões dos aplicativos CAD foram homologados.

## Ideia de conversão: avaliada, não implementada

- RVT: viável com motor Revit; a Autodesk documenta exportação IFC pela Automation API. Pode ser exportação manual, plugin local ou processamento em nuvem com fila e custo. [Autodesk APS](https://aps.autodesk.com/blog/export-ifc-rvt-using-revit-automation-api-part-i).
- Archicad: exportação nativa IFC por Save As ou Publisher, usando tradutores. Receber o IFC exportado é o caminho inicial mais simples; automação de arquivos nativos exige avaliar a API, a instalação e o licenciamento do Archicad. [Graphisoft](https://helpcenter.graphisoft.com/user-guide/137853/).
- DWG/DXF: AutoCAD comum não exporta IFC; Architecture e MEP oferecem exportação. Um desenho 2D não traz automaticamente materiais e semântica BIM. Pode-se manter extração direta de blocos, tabelas e medidas, com revisão, ou reconstruir/enriquecer um modelo BIM. [Autodesk Support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Can-AutoCAD-export-a-DWG-to-the-IFC-file-format.html).

Recomendação: começar pelo IFC exportado pelo cliente; considerar plugin local ou RVT em nuvem após medir demanda, tempo e custo. Quantitativos e especificação ainda dependem da qualidade do modelo e de revisão humana.

Referências das correções: [bulge em polilinhas](https://help.autodesk.com/cloudhelp/2018/ENU/OARXMAC-RefGuide/files/OREFMAC-AcDbPolyline__getBulgeAt_unsigned_int_double__const.html) e [unidade local de IfcQuantityArea](https://standards.buildingsmart.org/IFC/DEV/IFC4_3/HTML/lexical/IfcQuantityArea.html).
