# BIM, formatos e extração de dados de projetos

## O que é BIM e onde cada software entra?

### Takeaway

BIM (Building Information Modeling, Modelagem da Informação da Construção) é um processo de produzir e gerenciar informações da edificação com modelos de dados. Imagine uma maquete conectada a registros de objetos: uma porta pode ter geometria, identificação, largura, altura, material, tipo e relação com pavimento ou parede. A tabela de portas consulta as instâncias colocadas no modelo. A definição de um tipo pode ser reutilizada por várias instâncias.

### Cited Findings

- BIM envolve geometria, propriedades e relações entre elementos, além de coordenação entre disciplinas. Revit é um programa voltado a esse processo, e Archicad também produz modelos com tabelas de elementos, componentes e superfícies. [Autodesk sobre BIM](https://www.autodesk.com/eu/solutions/bim), [Tabela interativa do Archicad](https://help.graphisoft.com/AC/29/INT/_AC29_Help/055_InteractiveSchedule/055_InteractiveSchedule-1.htm).
- AutoCAD pode produzir plantas, cortes e detalhes cotados, inclusive detalhes específicos. Em DWG 2D, a porta pode ser desenho de linhas ou bloco reutilizado com atributos. O AutoCAD Architecture possui objetos de parede, porta e janela e gera tabelas. A distinção de capacidade depende de como o arquivo foi produzido. [Atributos de blocos](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-BA68DD22-A3CD-4538-90A9-6101C33BC963.htm), [Objetos arquitetônicos do AutoCAD](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Architecture/files/GUID-508C88DB-2CB7-4D0C-A60D-8D4CCC7CC5A6.htm), [Tabelas AutoCAD Architecture](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-Architecture/files/GUID-77F8B132-6A45-483B-AB92-AD3BD5D47660.htm).
- SketchUp agrupa geometria em componentes reutilizáveis. Pode adicionar atributos e classificar componentes (incluindo classes IFC). Um modelo conceitual com uma face texturizada pode servir à comunicação visual e ainda omitir a especificação de compra. [Componentes do SketchUp](https://help.sketchup.com/en/sketchup/components), [Classificação de objetos](https://help.sketchup.com/en/sketchup/classifying-objects-sketchup).

### Inferences

- O trabalho pode combinar CAD para desenho/detalhamento, SketchUp para estudos 3D e visualização, Revit ou Archicad para modelagem BIM e documentação. Os usos se sobrepõem. A diferença para o Orça é ter informação identificável, medida confiável, unidade, escopo e rastreabilidade.
- No exemplo de uma porta 80 × 210 cm, a geometria fornece a medida, a classe indica porta, o modelo pode trazer “madeira branca” e a oferta da loja define marca, código, embalagem e condições comerciais. Nem o modelo nem o formato garantem todos esses dados. Várias instâncias do mesmo tipo não equivalem a vários tipos.

### Gaps

- As documentações confirmam capacidades. Elas não permitem afirmar que SketchUp e Archicad predominam entre arquitetos de um segmento brasileiro nem que AutoCAD seja raro. A prioridade de formato deve ser validada com amostras e entrevistas do público real.

## Posso exportar IFC de qualquer RVT e DXF de qualquer DWG?

### Takeaway

Em geral, um RVT válido que abre em Revit compatível pode ser exportado a IFC, e um DWG válido que abre em AutoCAD compatível pode ser salvo como DXF. A capacidade de produzir o arquivo e a utilidade do seu conteúdo para orçar são duas verificações separadas. Confirme versão, acesso ao documento quando remoto e dependências.

### Cited Findings

- IFC é padrão aberto de intercâmbio BIM mantido pela buildingSMART. Descreve classes, propriedades, quantidades e relações, em várias versões e recortes de uso. O suporte do leitor precisa corresponder ao que foi exportado. [IFC na buildingSMART](https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/?lang=en), [Escopo oficial IFC](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/content/scope.htm).
- Revit não abre RVT de versão posterior. Opções IFC controlam fase, vista, categorias, modelos vinculados, propriedades e quantitativos base. A Autodesk descreve a opção de armazenar GUIDs nos elementos, útil como candidato de correspondência entre revisões. A estabilidade precisa ser testada e a correspondência ambígua vai para revisão. [Compatibilidade do RVT](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Convertion-or-downgrade-of-file-into-older-former-version-of-Revit.html), [Configurações de exportação IFC do Revit](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-DocumentPresent/files/GUID-E029E3AD-1639-4446-A935-C9796BC34C95.htm).
- Archicad usa tradutores para definir o mapeamento de classes e os campos e quantitativos exportados. SketchUp exporta IFC em configurações suportadas e alerta que algumas entidades podem ficar de fora. [Exportação Archicad](https://helpcenter.graphisoft.com/user-guide/137853/), [Dados do Archicad para IFC](https://helpcenter.graphisoft.com/user-guide/137886/), [IFC no SketchUp](https://help.sketchup.com/en/importing-and-exporting-ifc-files).
- DWG é formato nativo de desenho do AutoCAD e tem versões. DXF é um formato de intercâmbio de desenho. No AutoCAD, usar Salvar como e selecionar DXF. Objetos específicos de outros produtos podem aparecer como objetos proxy ou imagens, dependendo do objeto e da ferramenta que abre o arquivo. Referências externas podem ser dependências separadas. [Salvar DXF](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-5EA0F1DC-EA92-4ADB-9BDF-C352DF3AFC5F.htm), [Compatibilidade DWG](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-Customization/files/GUID-D029509F-A2A0-4A7E-BDD5-FE95E7235C5C.htm), [Opções para objetos proxy no DXF](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-0FC24222-2C6A-4068-8ECF-DB7DDCEE6656.htm), [eTransmit e dependências](https://help.autodesk.com/cloudhelp/2025/ENU/AutoCAD-DidYouKnow/files/GUID-DD451786-5D5A-42A5-92D5-943CE9D66016.htm).

### Inferences

- Arquivo válido e até visualmente completo pode omitir acabamento, fabricante ou um pavimento vinculado. Conferir quantidade extraída com tabela gabarito da mesma fase/escopo. Comparar área líquida/bruta e unidade para evitar divergências legítimas.
- Para DXF, usar blocos e atributos quando disponíveis e legenda para códigos como P01. Confirmar unidade com dimensão conhecida e distinguir model space de pranchas/cortes repetidos. Área depende de contorno verificável. Linhas soltas sem convenções exigem interpretação assistida; não prometer qualquer DWG ou DXF.

### Gaps

- Esta pesquisa não executou exportação real, não validou um perfil IFC ou um conjunto de versões DXF e não mediu cobertura de importação em arquivos do público.

## O agente pode receber especificações sem IFC ou DXF?

### Takeaway

Sim. É possível exportar só os dados em tabela ou ler o formato original com uma integração. A tabela é o caminho simples para orçar uma lista. A integração nativa reduz a etapa manual de exportação e pode preservar campos que uma exportação padrão não incluiu, com maior custo de implementação.

### Cited Findings

- Revit exporta tabelas em texto delimitado, incluindo opção de tabulação. Para processar RVT diretamente, um add-in usa a API do Revit local ou a Revit Automation API roda o add-in na nuvem. A API pode consultar instâncias por categoria, identificadores e parâmetros; para materiais suportados, pode consultar área. [Exportar tabela do Revit](https://help.autodesk.com/cloudhelp/2022/ENU/Revit-DocumentPresent/files/GUID-B2CCAC4F-1D38-4D5D-B4D1-95619D1B7EBE.htm), [Autodesk Automation](https://aps.autodesk.com/automation-apis), [Filtrar elementos na API](https://help.autodesk.com/cloudhelp/2024/ENU/Revit-API/files/Revit_API_Developers_Guide/Basic_Interaction_with_Revit_Elements/Revit_API_Revit_API_Developers_Guide_Basic_Interaction_with_Revit_Elements_Filtering_html.html), [Área do material na API](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/02417c40-bcc4-f04c-9897-cf47737e8739.htm).
- SketchUp Generate Report exporta CSV de atributos de componentes, com filtros, agrupamento e unidades. Para SKP direto, Trimble oferece SDK de leitura/escrita de arquivos, cujo acesso é solicitado. Alternativamente, extensão Ruby roda no SketchUp aberto e lê entidades, dicionários de atributos e IDs persistentes quando disponíveis. [Gerar relatório CSV no SketchUp](https://help.sketchup.com/pt-br/sketchup/generating-attribute-report), [Portal SDK do SketchUp](https://developer.sketchup.com/), [Entidades e atributos na API Ruby](https://ruby.sketchup.com/Sketchup/Entity.html).
- AutoCAD tem extração de blocos e atributos para CSV, TXT ou XLSX, sem precisar DXF. A Autodesk também oferece automação para DWG. [Extração de dados do AutoCAD](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-BA68DD22-A3CD-4538-90A9-6101C33BC963.htm), [Autodesk Automation](https://aps.autodesk.com/automation-apis).
- Para IFC, IfcOpenShell em Python consulta propriedades, quantitativos e relações. Para DXF, ezdxf lê entidades e blocos; não faz interpretação de construção e não é conversor DWG nativo. [IfcOpenShell](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/element/index.html), [ezdxf](https://ezdxf.readthedocs.io/en/stable/introduction.html).

### Inferences

- Os leitores convergem para a mesma ficha de item: categoria, quantidade e unidade, especificações, origem e lacunas. Programas de leitura e regras medem e preservam evidências. O agente recebe a ficha estruturada, formula perguntas e consulta ofertas. Se houver informações em um memorial separado, a associação por código deve ter fonte e ser revisável.
- Para testar valor em pouco tempo, Revit TXT e SketchUp CSV aproveitam a revisão tabular existente. Se a promessa da demonstração é fazer o levantamento direto do modelo, use IFC de um modelo com elementos e quantitativos, e compare com tabela oficial do projeto. Para fase posterior, RVT direto e SKP direto podem ter leitores próprios convergindo na mesma ficha. Confirmar condições do SDK e do serviço de execução antes de escolher.
- A ausência de marca não é sempre um bloqueio: pode procurar alternativas quando as características indispensáveis estão confirmadas. Uma ambiguidade que altera compatibilidade, quantidade ou preço exige revisão. Exemplo: 48 m² de piso identificados e ambiente indefinido. Perguntar o ambiente ou classe de uso antes de indicar produto, manter os 48 m² na revisão, registrar a resposta e liberar só a linha afetada.

### Gaps

- Integração, licença/termos de distribuição e suporte de versões do SDK ainda precisam ser avaliados no cenário real do Orça. Nenhum pipeline foi executado nesta pesquisa.
