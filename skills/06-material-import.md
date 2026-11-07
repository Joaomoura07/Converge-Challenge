---
name: importing-materials
description: Importa listas de materiais CSV, Excel, TXT tabulado do Revit e PDF com texto para a revisão da Fatia A. Use ao implementar ou corrigir leitores, codificação, mapeamento de colunas, números brasileiros, unidades ou os testes de importação.
---

# Importação de materiais

Confira as amostras disponíveis e o contrato de entrada antes de implementar. Todos os leitores alimentam a mesma representação de revisão. Preserve texto original, valores revisados e linha ou página de origem.

## Por formato

- CSV com PapaParse respeita campos entre aspas e o separador observado. Verifique marcador de codificação e UTF-8; trate Windows-1252 nas amostras correspondentes.
- No TXT tabulado do Revit em português, force tabulação. Confira codificação, cabeçalhos, grupos e totais na amostra. Outros TXT exigem identificação do formato.
- Excel usa SheetJS distribuído pelo CDN oficial com versão fixada. Ofereça seleção de aba quando necessário. Células com erro e fórmulas sem resultado utilizável ficam sinalizadas para correção.
- PDF com texto exige reconstruir linhas conforme o layout observado. Se usar PDF.js, alinhe a versão do worker. PDF escaneado, protegido ou ilegível recebe orientação para CSV ou entrada manual.

## Revisão compartilhada

- Mapeie descrição, quantidade e unidade. Colunas ausentes ou ambíguas exigem escolha do usuário. Preserve extras dentro dos limites acordados.
- Quantidade deve ser positiva e finita. Uma célula vazia permanece pendente. Recuse booleanos e resultados de fórmula inválidos.
- Em origem brasileira confirmada, interprete 12,50 como 12.5 e 1.234,50 como 1234.5. Valores ambíguos como 1,234 pedem conferência. Evite substituição indiscriminada de pontuação.
- Normalize aliases de unidade conhecidos. Conversões entre área, massa, volume e embalagem dependem de informação adicional. B calcula as embalagens para compra.
- Os três arquivos de exemplo usam o mesmo leitor e revisão que os uploads. Apenas o aceite explícito aplica correções ou complementos sugeridos.
- Limite arquivo, páginas e linhas conforme o contrato. Preserve a lista anterior se a importação falhar.

## Verificação

Use `tests/importacao/` e `docs/arquivos-teste/` quando disponíveis. Registre arquivos aceitos, recusas esperadas e falhas reais. Para cada leitor alterado, teste um exemplo válido e uma falha relevante. Confira pelo navegador se a edição de um valor importado aparece no JSON enviado à API.
