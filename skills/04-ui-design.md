---
name: designing-orcamentista-ui
description: Identidade visual e padrões de interface do Orçamentista (site na Vercel), cobrindo tokens de cor e tipografia, telas de upload, revisão editável e resultado ao vivo, status Definido/Pendente de especificação, a "cota de preço", textos em português, acessibilidade e o modo demo para projetor. Use ao criar ou alterar qualquer tela, componente, estilo, texto de interface ou animação do front-end.
---

# Design do Orçamentista

Público: **arquitetos** (cultura visual de prancha, desenho técnico e materiais) e, no Demo Day, **jurados olhando um projetor**. A tela tem um único trabalho: **transformar uma lista de materiais em decisão de compra, com clareza visível a 3 metros de distância**.

## 1. Ideia central: a prancha técnica
A interface se inspira na **prancha de arquitetura**: fundo frio de papel vegetal, tinta grafite, linhas finas de desenho técnico e uma cor de destaque tirada do **azulejo português**, presente nas fachadas do Recife e no próprio produto (revestimentos).

**O elemento memorável é um só: a "cota de preço".** A faixa mín–médio–máx de cada item é desenhada como uma **linha de cota** de desenho técnico: traço fino, marcas nas pontas e o valor médio escrito sobre a linha. Todo o resto é discreto.

```
 R$ 289 ├────────────●──────────┤ R$ 412
                 médio R$ 341
```

## 2. Tokens

### Cor (variáveis CSS; sem outras cores no projeto)
| Token | Hex | Uso |
|---|---|---|
| `--papel` | `#F2F4F3` | Fundo (frio, papel vegetal; **não** usar creme) |
| `--grafite` | `#1D2226` | Texto principal e traço das cotas |
| `--linha` | `#C5CCCF` | Bordas e divisórias da tabela |
| `--nanquim-claro` | `#5F6A72` | Texto secundário, unidades |
| `--azulejo` | `#1F4E8C` | Ação principal, links, foco, ponto médio da cota |
| `--definido` | `#2F7D6B` | Status Definido (verde azinhavre) |
| `--pendente` | `#B7791F` | Status Pendente de especificação (âmbar) |
| `--erro` | `#B23A2E` | Erro / não encontrado (óxido de ferro) |

- Status **nunca só por cor**: sempre cor + ícone + texto ("Definido", "Pendente de especificação", "Não encontrado").
- Contraste mínimo AA (4,5:1) para texto. O âmbar só aparece em ícone/borda ou com texto escuro.

### Tipografia
- **Archivo** (Google Fonts) para tudo, usando as larguras como hierarquia:
  - **Archivo Expanded**, peso 600: títulos de tela e o total do orçamento;
  - **Archivo**, peso 400/500: texto e botões;
  - **Archivo Narrow**: células densas da tabela.
- Números sempre com **algarismos tabulares** (`font-variant-numeric: tabular-nums`), para os preços alinharem.
- Escala: 14 / 16 / 20 / 28 / 40 px. Linha de texto com no máximo ~75 caracteres.
- **Não** usar fonte monoespaçada para dados nem CAIXA ALTA em rótulos.

### Forma e espaço
- Bordas de **1 px** na cor `--linha`. Raio pequeno e com hierarquia: **2 px** em campos e tabela, **8 px** só em painéis e no drop zone.
- **Sem sombras decorativas.** A separação vem de linha e espaço (grade de 8 px).
- Alinhamento à esquerda; números alinhados à direita.

## 3. Telas

### 3.1 Nova obra (upload)
```
┌───────────────────────────────────────────────┐
│ Nova obra                                     │
│ Nome da obra [____________]   CEP [_____-___] │
│ ┌───────────────────────────────────────────┐ │
│ │  Solte aqui a lista de materiais          │ │
│ │  CSV, Excel, TXT do Revit ou PDF          │ │
│ │  [Escolher arquivo]                       │ │
│ └───────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```
- O CEP é validado na hora (formato + ViaCEP), mostrando bairro e cidade abaixo do campo.
- Drop zone com borda tracejada (lembra área de recorte da prancha). Estado de "arrastando" muda a borda para `--azulejo`.

### 3.2 Revisão (tabela editável)
```
 Revise os itens antes de enviar            42 itens, 6 pendentes
 ┌──┬───────────────────────────────┬──────┬────┬──────────┬──────────────┐
 │ ⚠│ Tinta acrílica fosca branca    │  180 │ m² │ Pintura  │ Falta marca  │
 │ ✓│ Suvinil Toque de Seda Br. Neve │  180 │ m² │ Pintura  │              │
 └──┴───────────────────────────────┴──────┴────┴──────────┴──────────────┘
                                 [Enviar 42 itens para a IA]
```
- Parece planilha: célula editável com clique duplo ou Enter, Tab avança, Esc cancela.
- Itens genéricos já chegam marcados como **Pendente de especificação**, com o motivo ("Falta marca", "Falta quantidade").
- Barra inferior fixa com o resumo e a ação principal. **A ação mantém o mesmo nome em todo o fluxo**: "Enviar para a IA" → aviso "Enviado para a IA".

### 3.3 Resultado ao vivo
```
┌──────────────────────────────────────┬────────────────────────┐
│ ▣ Suvinil Toque de Seda Branco Neve  │ Total estimado         │
│   180 m² → 2 latas 18 L              │ R$ 18.420              │
│   R$ 289 ├──────●───────┤ R$ 412     │                        │
│ ▣ Porcelanato Portobello 90x90       │ Melhor compra          │
│   …                                  │ Loja única: Casa X     │
│ ⚠ Tinta acrílica fosca branca        │ Frete R$ 180           │
│   Pendente de especificação          │ Economia R$ 95 vs.     │
│   [Especificar]                      │ dividir em 3 lojas     │
└──────────────────────────────────────┴────────────────────────┘
```
- Cada item tem miniatura 56×56 da imagem buscada (com fundo `--papel` e borda fina; sem imagem → ícone do material).
- **Pendentes ficam juntos no fim da lista**, com o botão "Especificar", que abre o campo para o arquiteto completar.
- O painel da direita fica fixo (sticky). No celular, ele vira um resumo no topo.

## 4. Movimento
- **Um momento só:** quando um item chega via Supabase Realtime, ele entra no lugar com destaque `--azulejo` a 8% que some em 1,2 s, e a cota de preço "se desenha" da esquerda para a direita (300 ms). É a resposta a um evento do sistema, não decoração.
- Nada de fade/slide em seções, hover animado em todo cartão ou spinners decorativos. Enquanto espera, cada linha mostra um esqueleto com as cotas tracejadas.
- `prefers-reduced-motion`: sem animação, só a troca de estado.

## 5. Texto da interface (PT-BR)
- Frases curtas, sem CAIXA ALTA e sem "→" em botões. Verbo de ação no botão: "Enviar para a IA", "Especificar", "Baixar estudo de viabilidade".
- Fale como arquiteto: "obra", "quantitativo", "especificação", "embalagem", "frete". Não use "payload", "job" ou "registro".
- Erro diz o que houve e o que fazer: "Não consegui ler a planilha: a coluna de quantidade está vazia. Confira a coluna C e envie de novo."
- Estado vazio convida à ação: "Nenhuma obra ainda. Solte a primeira lista de materiais aqui."
- Moeda sempre `R$ 1.234,56`; quantidades com a unidade (`180 m²`, `2 latas 18 L`).

## 6. Qualidade mínima (sempre)
- Responsivo até 360 px de largura.
- Foco visível em `--azulejo` (2 px). Tabela inteira navegável por teclado.
- Imagens com `alt` = nome do produto.
- **Modo demo** (`?demo=1`): fonte base 18 px, cotas mais grossas e painel de totais maior, porque o projetor apaga detalhes finos.

## 7. Não faça (são os sinais de "interface gerada por IA")
- Fundo creme com destaque terracota; fundo preto com destaque verde-ácido.
- Tudo em cartões iguais com a mesma sombra cinza e gradientes de enfeite.
- Rótulos em CAIXA ALTA espaçada acima de cada título; textos com "A · B · C"; números 01/02/03 sem que exista uma sequência real.
- Uma palavra do título em outra cor ou em itálico.
- Fonte monoespaçada para números pequenos.

## 8. Implementação sugerida
- Tailwind CSS com os tokens acima em `:root` (via `@theme` ou `theme.extend.colors` apontando para as variáveis).
- Componentes: `DropZone`, `ReviewTable`, `StatusBadge`, `PriceDimension` (a cota), `ItemRow`, `SummaryPanel`, `LogisticsCard`.
- A cota é um SVG simples: linha + 2 ticks + ponto médio. Largura proporcional à faixa de preço do próprio item.
- Antes de concluir uma tela: tirar print em 1440 px e em 390 px e conferir contra as seções 6 e 7.
