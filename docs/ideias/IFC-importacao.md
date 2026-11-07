# Ideia guardada: importar o modelo IFC (BIM) — para depois

**Status:** em espera (decidido em 07/11). Não começar antes de fechar a pesquisa de preço (fatia B, etapas 6–9).

## O que é IFC
Formato aberto do BIM (ISO 16739), exportado por Revit, ArchiCAD e SketchUp Pro. Diferente de um PDF de planta,
guarda **objetos com dados**: Obra ▸ Edifício ▸ Pavimento ▸ Ambiente (`IfcSpace`) ▸ pisos (`IfcSlab`/`IfcCovering`),
paredes (`IfcWall`), louças (`IfcSanitaryTerminal`), portas e janelas (`IfcDoor`/`IfcWindow`), com área, quantidade e material.

## Arquitetura decidida (por que não ler no servidor)
Um IFC real do Revit costuma ter **20 a 200 MB**, e a Vercel só aceita **4,5 MB** por envio. Ler no servidor não funciona para arquivo de verdade. A saída:

1. **O navegador lê o IFC com `web-ifc`** (WebAssembly, ~25 MB no npm). O arquivo nem sai do computador do arquiteto (é rápido e não expõe o projeto dele).
2. O navegador manda ao backend **só a lista extraída**, alguns KB de JSON.
3. A lista cai **na mesma tela de revisão do CSV/XLSX**. O IFC vira só mais um formato de entrada, e o resto (preço, frete, viabilidade) não muda nada.

Extra de demo: a mesma biblioteca (`@thatopen/components`) mostra o modelo 3D; dá para acender cada item no 3D quando o preço chega.

## O que vem do modelo e o que o arquiteto completa
O IFC **não tem uma "lista de materiais" pronta**: a lista é **derivada dos elementos da arquitetura**.

| Vem do modelo (o básico) | O arquiteto detalha (o que o modelo quase nunca traz) |
|---|---|
| Ambientes e suas áreas (`IfcSpace`) | Qual porcelanato, qual tinta, qual linha de metais |
| Área de piso e de parede por ambiente | Cor, acabamento, marca |
| Contagem de louças, portas e janelas (com medidas) | Itens que não são modelados (tomadas, luminárias, às vezes) |
| Material, quando o escritório modela com nome real | — |

Fluxo: puxar o básico → itens sem especificação entram como `pendente_especificacao` com a pergunta ao arquiteto
(já existe na fatia B) → complementos técnicos (argamassa, rejunte, selador) por regra, sem LLM.

## Riscos
- Quantidades prontas só se exportado com **"quantidades base"** marcado no Revit. Sem isso: área dos ambientes,
  parede = perímetro × pé-direito, contagem de louças/portas.
- Material costuma vir genérico ("Default", "Concreto").
- Esforço: versão enxuta (pisos, paredes, louças e portas de um arquivo controlado) ≈ 4–6 h de front-end; precisa de dono.

## Já verificado (07/11)
- `ifcopenshell` 0.9.0.post1 tem pacote para Python 3.14 (Windows e Linux), ~43–55 MB → bom para explorar arquivos localmente.
- `web-ifc` 0.0.78 no npm, ~25 MB.

## Para retomar
1. Baixar 2–3 IFC públicos (repositório *buildingSMART Sample-Test-Files*, ex.: "Duplex") e, com `ifcopenshell` local,
   ver o que vem de verdade (ambientes, áreas, materiais, louças). ~30 min. Decide se a ideia se sustenta.
2. Se sim: leitura no navegador com `web-ifc`, gerando o mesmo formato do importador CSV.
3. Plano B: demonstrar com `ifcopenshell` local; a planilha do Revit continua sendo o caminho principal.
4. Melhor arquivo de demo: um projeto próprio exportado do Revit com "quantidades base".
