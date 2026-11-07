# Fatia A — plano de execução para Samuel e Claude Code

Atualizado em 07/11/2026 conforme `FATIAS-DO-TIME.md` enviado por Samuel. A cópia na raiz preserva o documento recebido. Documento de planejamento. O andamento verificado fica na seção 0 de `CONTEXTO-DO-PROJETO.md`.

As respostas posteriores de Enzo e João estão em `CONTRATOS-B-C.md`. Consulte os nomes exatos e as divergências antes da etapa 02 e das integrações. A reserva da pesquisa pertence à B. A entrega dos resultados calculados na hora pela C ainda precisa de acordo para atualizar o frontend.

## 1. Resultado esperado

Um arquiteto cria a obra com nome, CEP e orçamento do cliente em reais. Importa CSV, Excel, TXT do Revit ou PDF com texto, escolhe um dos três exemplos ou digita materiais. Revisa a tabela, aceita correções E1 e complementos E2 e envia. A API valida e grava os dados, chama B na mesma requisição e a tela acompanha as duas tabelas por Realtime.

O primeiro marco é um CSV com quantidade editada chegando ao agente real. Os outros formatos usam a mesma revisão e o mesmo envio.

### Confirmado por Samuel

- Samuel faz a interface e `POST /orcamentos`, com entrega até a noite de 07/11. Horário exato pendente.
- Samuel passa a ser dono do SQL único das quatro tabelas. João fornece os requisitos da C, implementa complementos, logística, viabilidade e exportação e cadastra os fornecedores.
- Enzo implementa `pesquisar_orcamento(id)` e `repesquisar_item(item_id)`. A chama a pesquisa na mesma requisição; B chama logística e viabilidade da C ao terminar.
- O frontend parte do Figma. Vercel, Docker e Featherless fazem parte da estrutura discutida.
- As pastas `tests/importacao/` e `docs/arquivos-teste/` serão criadas e commitadas pelo time. Responsável e horário da entrega pendentes.
- O cadastro manual integra a entrada de materiais. A interface segue a direção visual aprovada, com fundo papel, azul cobalto e tipografia editorial.

### Propostas deste plano, a confirmar na etapa 01

- Frontend em Next.js com TypeScript, em `frontend/` no mesmo repositório, caso o time ainda esteja escolhendo. Reaproveitar a tecnologia e a estrutura que já existirem quando a implementação começar.
- Leitura dos arquivos no navegador, enviando JSON revisado à API. Essa proposta reduz o envio de arquivos grandes ao backend.
- PDF com texto está no escopo confirmado. Excel `.xlsx` é a primeira variante proposta; confirmar suporte a `.xls`. PDFs escaneados recebem orientação de formato alternativo.
- Um arquivo por importação. Importar de novo oferece substituir ou acrescentar. Linhas repetidas permanecem separadas até decisão do usuário.
- Limites iniciais propostos de 10 MB por arquivo, 500 itens, 20 páginas por PDF e 2 MB de JSON por envio. Confirmar nas amostras e na hospedagem. Esses números ainda precisam de medição.

## 2. Como executar com o Claude Code

1. Ler `CLAUDE.md`, `AGENTS.md`, o estado atual no contexto e a etapa relevante deste plano.
2. Inspecionar o código antes de escolher arquivos ou bibliotecas. As estruturas abaixo são propostas.
   Selecionar as skills conforme os gatilhos do AGENTS.md e a tabela de uso seletivo do CLAUDE.md. Nas etapas de SQL e leitores de arquivos, carregar instruções especializadas quando houver integração efetiva com agente, LLM ou tracing. Para E1 com redação por LLM e para a ligação com B, consultar as skills correspondentes. Reutilizar conteúdo já presente no contexto e atualizar a leitura quando os arquivos mudarem.
3. Executar uma etapa por pedido. Dependências ausentes ficam registradas com responsável. E1 e E9 pertencem à A; A mostra E2 da C e oferece os encaixes de B/C. T1–T3 são opcionais. SINAPI, memória do escritório e ERP ficam no pitch.
4. Validar um caso de sucesso e uma falha relevante. Usar dados sintéticos e simulações identificadas quando as integrações estiverem pendentes.
5. Atualizar o contexto com arquivos alterados, comandos executados, resultados observados, pendências e próximo prompt.
6. Conferir o diff e preparar commits pequenos conforme as regras do projeto. Atualizar código compartilhado somente dentro da autorização dada por Samuel.

Para encerrar a Fatia A, E1, E9, aceite de E2, SQL consolidado, classificação compartilhada, persistência, execução na mesma requisição e hook Realtime precisam de comprovação real com os componentes B/C integrados.

## 3. Plano por ferramenta

| Ferramenta | Papel na Fatia A | Entrega concreta | Como verificar |
|---|---|---|---|
| Figma | Referência das telas de importação, cadastro e revisão | Reutilizar cores, tipografia, espaçamento e estados dos campos | Comparar tela implementada com a referência aprovada em desktop e celular |
| Next.js + TypeScript, proposto | Interface e estado da lista | Formulário, tabela editável e navegação para pesquisa | Construção de produção e fluxo no navegador |
| PapaParse | Ler CSV e TXT tabulado | Linhas, cabeçalhos, avisos e localização do erro | Acentos, separadores e números brasileiros nas amostras |
| SheetJS do CDN oficial | Ler Excel | Escolha de aba e conversão das células para a revisão | Arquivo válido, várias abas e célula com erro |
| PDF.js, proposto | Extrair texto de páginas de PDF no navegador | Texto por página e tentativa de reconstruir linhas do layout suportado | Comparar itens extraídos com as páginas da amostra |
| Validação TypeScript | Dar retorno imediato na tabela | Erro no campo e bloqueio de envio incompleto | Quantidade vazia, negativa, zero e unidade desconhecida |
| FastAPI + Pydantic existentes | Receber JSON e validar novamente no servidor | `POST /orcamentos`, `POST /revisao/sugestoes` e erros por campo | Envio direto pela API, inclusive contornando a tela |
| Cliente Supabase existente | Persistir orçamento e itens | SQL único da A e escrita consistente | Ler o registro gravado e provocar falha parcial |
| Regras Python da A | Classificar e revisar antes da busca | `classificar_item()` único e `revisar_itens()` com sugestões aceitas pelo usuário | Casos de E1 e falsos positivos |
| Supabase Realtime | Atualizar a página de resultado | `useOrcamento(id)` nas duas tabelas | Carga inicial, reconexão e eventos repetidos |
| Agente existente + Featherless | Redigir sugestões da A e pesquisar pela B | A mantém regras em Python e aguarda `pesquisar_orcamento(id)` na requisição | Redação preserva fatos e pesquisa recebe exatamente os dados revisados |
| Langfuse existente | Relacionar a execução do agente ao orçamento | ID do orçamento associado ao trace | Encontrar a execução e a falha de teste pelo mesmo ID |
| Docker Compose existente | Rodar a API localmente | API acessível na porta configurada e documentação de execução | `/health`, `/docs` e envio local |
| Vercel | Publicar o site e o backend conforme arquitetura do time | URLs e configuração de execução verificadas | Repetir o fluxo completo no link publicado |
| Ferramentas de teste do repositório | Automatizar regressões importantes | Testes de importação, API e caminho pelo navegador | Relatório com comandos, resultado e ambiente |

Next.js é uma proposta para a escolha que segue aberta. Fixar versões compatíveis e o arquivo de dependências ao implementar. [Documentação Next.js](https://nextjs.org/docs/app/getting-started/installation)

### Figma e interface

Referência registrada no projeto em [oito telas do Orça](https://www.figma.com/design/ne5wG1A5f5EahJaBfp8LkG?node-id=0-1&p=f). Antes de implementar, localizar os quadros de entrada e revisão. Se o código exportado já estiver disponível, avaliar o reaproveitamento.

A tabela mantém um identificador estável por linha. Excluir uma linha preserva a associação dos erros às demais. O cadastro manual e cada importador alimentam uma única lista de revisão. Os estados visuais são vazio, lendo arquivo, revisão, erro de leitura, enviando e envio aceito. A confirmação de envio apresenta o ID recebido e abre o acompanhamento combinado com o time.

### PapaParse — CSV e TXT do Revit

- CSV pode usar vírgula, ponto e vírgula ou tabulação. Respeitar campos entre aspas e conferir a amostra antes de fixar o separador.
- Verificar marcador de codificação quando presente. Tentar UTF-8 com detecção de erro e oferecer Windows-1252 para os CSVs correspondentes. TXT pode exigir outra codificação indicada pela amostra, incluindo UTF-16.
- Para a exportação tabulada do Revit, informar `delimiter: "\t"`. Outros arquivos `.txt`, como listas livres, exigem uma regra de leitura própria.
- Remover linhas em branco com segurança. Identificar cabeçalhos, grupos e totais pela estrutura observada, mantendo os números das linhas para revisão.
- Se colunas obrigatórias estiverem ausentes ou ambíguas, permitir ao usuário indicar qual coluna contém descrição, quantidade e unidade.
- Colunas adicionais seguem para `extras` dentro dos limites combinados.

PapaParse oferece configuração de separador e codificação para arquivos locais. [Documentação PapaParse](https://www.papaparse.com/docs)

### SheetJS — Excel

Obter a distribuição oficial e registrar sua versão no projeto. Se houver várias abas com dados, mostrar seus nomes para escolha. Identificar o cabeçalho e reutilizar o mapeamento e a revisão do CSV. Mesclagens, linhas de total, fórmulas sem valor calculado e células com erro precisam aparecer na revisão ou em aviso. Uma célula vazia permanece pendente, sem virar zero automaticamente. [Instalação SheetJS](https://docs.sheetjs.com/docs/getting-started/installation/nodejs/)

### PDF.js — PDF

A proposta é usar PDF.js e um worker compatível com a versão instalada. `getTextContent()` permite obter o conteúdo textual por página. Reconstruir linhas e colunas é trabalho adicional de implementação e depende do layout das amostras. Processar páginas dentro do limite, descartar cabeçalhos repetidos somente quando identificados e mostrar a origem de cada item para conferência. [API de texto do PDF.js](https://mozilla.github.io/pdf.js/api/draft/module-pdfjsLib-PDFPageProxy.html)

Texto ausente, PDF protegido, corrompido ou layout ambíguo produz mensagem específica e caminho para CSV ou cadastro manual. OCR para escaneados é uma decisão pendente de escopo. A extração proposta precisa passar por revisão humana antes do envio.

### Regras comuns de dados

- Descrição obrigatória com espaços externos removidos. Texto genérico como “tinta branca” pode seguir para o agente sinalizar falta de especificação.
- Quantidade obrigatória, positiva e finita. Recusar booleanos, infinito, valores ausentes e resultados de fórmula inválidos.
- Interpretar `12,50` como `12.5` e `1.234,50` como `1234.5` em uma origem brasileira confirmada. Valores ambíguos como `1,234` pedem conferência. Evitar substituição global de pontos e vírgulas.
- Normalizar aliases confirmados como `m²` para `m2`. Conservar unidades desconhecidas para correção. Conversões entre área, volume, massa e embalagens exigem dados específicos.
- CEP é texto, mantendo zero inicial. Proposta de oito dígitos após remover a máscara. Consulta de existência por ViaCEP ou BrasilAPI depende do acordo com a etapa de logística.
- Manter descrição original, linha ou página de origem e valores editados. O envio usa os valores revisados.
- Tamanho, páginas, quantidade de itens e campos têm limites explícitos. A API também limita e valida o JSON recebido.


### Revisão E1 e complementos E2

A função única `classificar_item()` pertence à A e decide definido ou pendente antes da busca. B reutiliza e confirma a classificação, e C lê o resultado. A classificação é informação de negócio distinta do estado inicial de processamento `buscando`. Combinar onde armazená-la sem substituir os estados oficiais dos itens.

`revisar_itens(itens)` aplica regras Python. Uma unidade de compra pode ser legítima mesmo quando incomum. Sugerir “3 latas de 18 L?” exige evidência de embalagem ou pergunta ao usuário. Uma quantidade desproporcional exige referência como área ou ambiente. Se essa referência faltar, sinalizar a necessidade de conferência. Duplicados com nomes diferentes e colunas trocadas produzem propostas rastreáveis, preservando o original. Se usado, o LLM recebe os achados calculados e redige o texto mantendo valores e ações definidos pelas regras.

`POST /revisao/sugestoes` combina `revisar_itens` da A e `sugerir_complementos` da C e retorna `{erros: [...], complementos: [...]}`. Quantidades de argamassa, rejunte e demais complementos vêm das regras da C com seus pressupostos. A renderiza os dois grupos na revisão.

Proposta de cada sugestão conter ID, IDs de linhas afetadas, motivo, campos propostos e identificação da versão da lista. Aceitar aplica somente aquela proposta, recalcula a revisão e invalida sugestões antigas. Aceitar novamente o mesmo ID é inócuo. Editar enquanto há uma requisição pendente invalida a resposta antiga. Dados estruturalmente inválidos bloqueiam o envio; avisos de plausibilidade permitem a decisão explícita do arquiteto.

### Três exemplos E9

O botão “Usar arquivo de exemplo” oferece três obras de `docs/arquivos-teste/`. Os arquivos passam pelo mesmo leitor, revisão e envio do upload. Escolher com o time exemplos sintéticos que demonstrem dois avisos de E1 e complementos de E2. Confirmar os nomes e a disponibilidade dos arquivos antes de marcar E9 como pronto.

### Página de resultado e useOrcamento(id)

A entrega o esqueleto da página e o hook, B entrega `ItemRow` e C entrega totais, viabilidade, frete, ganho e exportação. Definir propriedades e estados de carregamento juntos. Consultar `skills/07-orca-ui-fatia-a.md` quando estiver disponível para a cota tracejada e a hachura de carregamento.

O hook consulta e acompanha `orcamentos` e `orcamento_itens`, filtrando pelo orçamento. Fazer carga inicial e reconciliar após a assinatura ficar ativa para cobrir alterações durante a conexão. Mesclar por ID, evitar sobrescrita por eventos antigos, refazer a consulta ao reconectar e remover canais ao desmontar. Preparar RLS e publicação Realtime no SQL. A chave pública do Supabase exige as permissões de leitura acordadas; credenciais privilegiadas ficam no servidor.

Como o POST aguarda a pesquisa, a tela precisa conhecer o ID antes de sua resposta para mostrar dados ao vivo. Proposta a fechar na etapa 01: cliente gera um UUID aceito e validado pelo servidor, compartilhado com o hook e a chave de envio. Definir o campo no contrato com B/C e o escopo de acesso. Se essa proposta for recusada, fechar outra forma explícita de conhecer o ID durante a requisição. Esse ponto é dependência do fluxo ao vivo.


## 4. Contrato e arquivos a preparar

O contrato existente na seção 4 do contexto continua como proposta. A etapa 01 deve fechar os campos antes da integração. A API em Pydantic é a referência executável e gera o esquema que o frontend deve respeitar. [Modelos Pydantic](https://docs.pydantic.dev/latest/concepts/models/)

| Objeto | Combinado necessário |
|---|---|
| `obra` | Nome, CEP e orçamento do cliente em BRL; definir nome do campo, precisão monetária e obrigatoriedade no contrato |
| `origem` | Nome e formato do arquivo ou indicação de cadastro manual. Definir a origem de uma lista que mistura ambos |
| `itens` | Descrição, quantidade, unidade, origem da linha e campos adicionais aceitos |
| Revisão A/C | `POST /revisao/sugestoes` recebe a lista atual e retorna `erros` e `complementos`; definir IDs e versão para aceite seguro |
| Resultado B/C | `fontes` com loja, dominio, url, preco_embalagem, além de embalagem, qtd_embalagens, preco_emb_min/med/max, confianca e estimativa |
| Resposta de sucesso | `orcamento_id` e estado ao retornar de B/C na mesma requisição. Fechar código HTTP final com o time |
| Erro de validação | HTTP 422 com campo ou linha e mensagem que a tela consegue apresentar |
| Erro de infraestrutura | Resposta recuperável com referência de acompanhamento quando já houver orçamento salvo |
| Reenvio | Identificador estável da tentativa para evitar orçamento e execução duplicados |

Arquivos candidatos, conforme a estrutura confirmada na etapa 01

- `frontend/` para a tela, leitores de arquivo, regras de revisão e cliente da API.
- `src/main.py` para a rota, usando modelos em um módulo específico se o tamanho justificar.
- `src/database.py` para reaproveitar o cliente Supabase e concentrar a persistência.
- `src/config.py` para configuração do servidor. Segredos ficam no ambiente do servidor. A URL pública da API no frontend é configuração pública.
- `sql/` sob responsabilidade de Samuel para o arquivo único das quatro tabelas, restrições, funções, estados e Realtime. João fornece os dados das lojas.
- `tests/importacao/` e `docs/arquivos-teste/` conforme a publicação do time. Testes novos de API acompanham as regressões relevantes.


## 5. Gravação, reenvio e execução na mesma requisição

### Samuel — SQL único

A é dona do arquivo SQL único que consolida `orcamentos`, `orcamento_itens`, `cache_precos` e `fornecedores`. Reunir campos de B/C, tipos, chaves, estados, índices, permissões e publicação das duas tabelas de acompanhamento. Reaproveitar o histórico SQL existente. João cadastra fornecedores com domínio, CEP, frete base, frete por km e pedido mínimo.

Proposta de função no banco para salvar orçamento e itens em uma transação. Uma falha reverte a operação. A implementa e valida essa definição no SQL consolidado. [Funções no Supabase](https://supabase.com/docs/guides/database/functions)

Propor chave única e resumo do conteúdo validado. Reenvio equivalente recupera o mesmo orçamento e sua execução. Chave repetida com conteúdo diferente produz conflito. Uma restrição no banco protege pedidos simultâneos. A exclusão mútua do processamento precisa ser combinada com B para impedir pesquisa duplicada.

### A → B → C

`POST /orcamentos` valida `tests/importacao/contrato.py`, grava os itens com `status="buscando"` e chama `pesquisar_orcamento(orcamento_id)` na mesma requisição, aguardando sua conclusão. Usar chamada assíncrona se esse for o contrato implementado por B. A resposta final do POST ocorre após a função retornar; atualizações durante a pesquisa chegam por Realtime.

A classificação inicial vem de `classificar_item()` da A. B confirma durante a pesquisa. Os estados oficiais do item são `buscando`, `definido`, `pendente_especificacao`, `nao_encontrado` e `erro`. Fechar separadamente os estados gerais de `orcamentos`.

B entrega cache, pesquisa, conferência, repetição limitada, conversão em embalagens com perda, fontes, confiança, pergunta e `repesquisar_item(item_id)`. Ao final, B chama `calcular_logistica(id)` e `calcular_viabilidade(id)` da C. C grava resultados gerais em `orcamentos`. A exibe os componentes e seus dados pelo hook compartilhado.

### Falhas e hospedagem

O trabalho de B/C permanece dentro do ciclo da requisição. Tratar timeout, falha após salvar e desconexão do navegador como situações cujo resultado precisa ser consultado antes de repetir. Uma desconexão pode acontecer enquanto o servidor ainda executa. Registrar falha e identidade do orçamento quando possível, e combinar com B a recuperação de execução interrompida e a detecção de execução ainda ativa.

O time pede duração da função Vercel de pelo menos 60 segundos. Conferir o limite efetivo e medir o fluxo completo com o volume da demo. Se ele exceder o limite, registrar o bloqueio para decisão do time sobre duração ou carga. Confirmar a configuração na publicação. [Limites Vercel](https://vercel.com/docs/functions/limitations)

### Featherless e Langfuse

Reutilizar o cliente e o loop existentes. Para a redação do revisor, registrar os fatos calculados, a sugestão e eventual falha, mantendo as regras numéricas em Python. Uma tool exposta ao modelo segue `ToolArgs` e registro conforme as skills.

Coordenar com B uma árvore Langfuse por orçamento com um ramo por item. A correlaciona revisão, envio e falhas com os IDs correspondentes. Conferir a versão instalada do SDK. Uma falha de telemetria precisa ser registrada sem repetir uma operação de negócio já concluída.


## 6. Prompts por etapa

Cole um prompt por vez. Ao concluir, registre no contexto arquivos, verificações, bloqueios e próximo passo.

### 01 — Diagnóstico e contratos

```text
Use managing-orcamento-data para o diagnóstico dos contratos.

Leia FATIAS-DO-TIME.md e o código em modo de leitura. Localize contrato.py, amostras e skills/07-orca-ui-fatia-a.md. Feche exemplos de envio com orçamento do cliente, revisão com erros e complementos e resposta final. Combine com B e C campos do SQL, assinatura das funções e identificação do orçamento antes da resposta do POST. Registre pendências e prepare a etapa 02.
```

### 02 — SQL único e persistência

```text
Use managing-orcamento-data antes de editar SQL ou testes.

Como responsável pela Fatia A, consolide em um único arquivo SQL as quatro tabelas orcamentos, orcamento_itens, cache_precos e fornecedores, incluindo os campos pedidos por B e C. Reaproveite o histórico existente. Defina chaves, estados, RLS, publicação Realtime e gravação consistente. Teste migração em banco de teste, falha parcial e reenvio concorrente. João fornece os dados das lojas.
```

### 03 — Nova obra e cadastro manual

```text
Use building-orca-ui antes de implementar a tela.

Implemente a tela do Figma com nome, CEP e orçamento do cliente em reais. Inclua cadastro manual e tabela editável com IDs estáveis. Prepare áreas para avisos, complementos, exemplos e resultado. Valide valores e preserve edições ao alternar modos. Teste inclusão, edição, exclusão e orçamento monetário inválido.
```

### 04 — CSV e três arquivos de exemplo

```text
Use importing-materials e building-orca-ui para importação e revisão.

Implemente CSV com PapaParse e botão Usar arquivo de exemplo com três obras de docs/arquivos-teste. Os exemplos devem passar pelo mesmo leitor e revisor do upload. Use apenas amostras disponíveis e identificadas. Teste UTF-8, Windows-1252, separadores, decimal brasileiro, coluna ausente e troca de arquivo com lista já editada.
```

### 05 — Classificação única e revisor E1

```text
Use managing-orcamento-data para os contratos da revisão. Ao implementar redação por LLM, use integrating-featherless; ao alterar tools ou prompt do agente, use building-react-agents; para a instrumentação nova, use tracing-with-langfuse.

Consulte as skills aplicáveis e implemente classificar_item() e revisar_itens(itens) com regras Python compartilhadas. Cubra unidade suspeita, quantidade desproporcional quando houver referência, duplicados por nomes distintos e colunas trocadas. O LLM pode redigir a sugestão a partir dos fatos calculados. Teste casos positivos e falsos positivos e mantenha os dados originais até o aceite.
```

### 06 — Sugestões A/C e aceite na tabela

```text
Use managing-orcamento-data e building-orca-ui para o contrato de sugestões e o aceite.

Implemente POST /revisao/sugestoes reunindo erros de revisar_itens e complementos de sugerir_complementos da C. Combine IDs, revisao_id, motivo e alterações propostas. Renderize Aceitar por sugestão. Revalide ao editar, aceite uma vez e descarte respostas obsoletas. Teste rejeição, aceite repetido, retorno atrasado e C indisponível. Preserve os critérios de bloqueio de dados inválidos.
```

### 07 — Página de resultado e useOrcamento

```text
Use building-orca-ui e managing-orcamento-data para o hook e as permissões.

Crie o esqueleto de resultado e useOrcamento(id) para orcamentos e orcamento_itens. Use o contrato aprovado para conhecer o ID enquanto POST /orcamentos está em curso. Faça carga inicial, assinatura filtrada, reconciliação após conectar/reconectar e limpeza ao desmontar. Reserve encaixes para ItemRow da B e resultado da C. Teste eventos repetidos, atualização durante conexão e leitura RLS.
```

### 08 — POST /orcamentos e integração na mesma requisição

```text
Use managing-orcamento-data, building-react-agents e tracing-with-langfuse para integrar persistência e execução. Consulte integrating-featherless se alterar chamadas ou configuração do LLM.

Valide pelo contrato publicado, grave orçamento e itens com status buscando e invoque pesquisar_orcamento(id) da B, aguardando a conclusão na mesma requisição. Use a classificação única e os dados aceitos na revisão. Preserve identificação e estado de falha parcial para recuperação. Teste o fluxo real na Vercel, timeout, perda da resposta e reenvio sem duplicar execução. B chama logística e viabilidade da C.
```

### 09 — Excel

```text
Use importing-materials para o leitor Excel.

Implemente os formatos Excel aprovados usando SheetJS do CDN oficial e versão fixada. Reutilize mapeamento, classificação e revisão. Teste múltiplas abas, célula com erro, fórmula sem valor utilizável e arquivo corrompido. Preserve a origem de cada linha para indicar os avisos.
```

### 10 — TXT do Revit

```text
Use importing-materials para o TXT do Revit.

Leia a amostra de TXT do Revit em português, confirme codificação e force tabulação no PapaParse para a exportação tabulada. Trate cabeçalhos e totais conforme o arquivo. Teste acentos e 12,50 m² e confira a quantidade apresentada na revisão.
```

### 11 — PDF com texto

```text
Use importing-materials para o PDF textual.

Implemente extração de PDF com texto para os layouts das amostras. Se PDF.js for adotado, use worker compatível, limite de páginas e indicação de origem. Mostre extrações ambíguas para correção. Teste PDF textual, protegido, corrompido e escaneado com orientação amigável para cadastro manual ou CSV.
```

### 12 — Encaixe dos componentes B/C

```text
Use building-orca-ui e managing-orcamento-data para os encaixes de B/C.

Integre ItemRow da B e os componentes de resultado da C ao esqueleto e ao hook existentes. Teste preço com fonte, pergunta ao arquiteto e repesquisar_item pela B, complementos aceitos, frete, viabilidade, ganho e exportação da C. Confirme que cada função é chamada pela fatia responsável e use dados reais do fluxo com exemplos sintéticos.
```

### 13 — Bateria e regressões

```text
Use managing-orcamento-data e importing-materials para as regressões desses módulos; acrescente as skills das outras áreas alteradas.

Rode os 100 casos e as amostras quando publicados. Acrescente regressões de E1, classificação compartilhada, aceite, números brasileiros, Realtime e reenvio. Execute python -m scripts.check_setup, um caminho feliz e uma exceção. Registre resultados observados, falhas e bloqueios e repita os testes afetados pelas correções.
```

### 14 — Demo e entrega

```text
Use building-orca-ui para a validação da jornada e tracing-with-langfuse ao verificar os traces da demo.

Valide no link final os três exemplos e o roteiro: dois erros sinalizados, aceite das correções e complementos, envio, itens ao vivo, pergunta e nova pesquisa pela B, resultado e exportação pela C. Verifique RLS, configuração de duração da Vercel de pelo menos 60 s conforme o time e tempo real medido. Registre evidências e pendências de E1 a E11 para os respectivos responsáveis.
```

## 7. Matriz mínima de aceitação

| Caso | Resultado esperado |
|---|---|
| Revisor E1 detecta e propõe correção | Aplicação exige Aceitar; falso positivo preserva o item |
| Complemento de C aceito duas vezes | Uma inclusão e nova revisão |
| Sugestão retorna após edição | Resposta antiga descartada |
| Orçamento do cliente | Valor em reais chega à C para viabilidade |
| Três exemplos E9 | Mesmo fluxo de importação e revisão do upload |
| Realtime durante POST aberto | Resultado parcial aparece pelo ID acordado |
| Reconexão do hook | Estado completo recuperado sem duplicação |
| CSV com 12,50 alterado para 15 | Banco e agente recebem 15 |
| Cadastro manual seguido de importação | Regra de acrescentar ou substituir fica clara e é respeitada |
| CSV UTF-8 e Windows-1252 | Descrições com acentos preservadas |
| TXT tabulado com unidade na célula | Quantidade e unidade extraídas separadamente |
| Excel com abas e célula inválida | Aba escolhida e campo inválido sinalizado |
| PDF do layout aprovado | Itens coincidem com a amostra após revisão |
| Lista vazia, quantidade zero ou unidade inválida | Envio bloqueado na tela e rejeitado na API |
| Descrição genérica válida | Lista aceita e especificação encaminhada para análise do agente |
| Arquivo vazio, protegido, corrompido ou grande | Erro compreensível e lista anterior preservada |
| Resposta da API perdida após salvar | Reenvio equivalente recupera o mesmo orçamento |
| Duas requisições simultâneas equivalentes | Um orçamento e uma execução efetiva |
| Falha parcial de banco | Operação revertida, erro visível e agente aguardando dados válidos |
| Falha entre salvar e disparar | Orçamento localizável e retomada pelo mecanismo combinado |
| Chave repetida com conteúdo diferente | Conflito informado, sem sobrescrever orçamento anterior |
| Encerramento ou timeout na hospedagem | Estado recuperável e erro observável |

## 8. Atualização da memória e ponto de retomada

O plano atualizado tem 14 etapas. Samuel coordena o banco e a entrada; B e C desenvolvem seus contratos em paralelo. Samuel pode adiantar importadores enquanto aguarda uma integração, registrando a mudança de ordem. Confirmar a hora de entrega e reservar a última hora para validação no link final. Mudanças no alcance de formatos devem ser combinadas com Samuel.

Ao encerrar uma etapa, atualizar a seção de estado no contexto com data, etapa, arquivos alterados, comandos e resultado observado, integração real ou simulada, bloqueios com responsável e próximo prompt exato. O plano descreve o trabalho previsto. A conclusão de cada etapa depende dessa evidência registrada.
