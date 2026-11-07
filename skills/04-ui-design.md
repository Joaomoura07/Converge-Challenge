---
name: designing-orcamentista-ui
description: Identidade visual e padrões de interface do Orçamentista (site na Vercel), cobrindo papéis de cor e tipografia, telas de upload, revisão editável e resultado ao vivo, status Definido/Pendente de especificação, a "cota de preço", carregamento em linguagem de prancha, textos em português, acessibilidade e o modo demo para projetor. Use ao criar ou alterar qualquer tela, componente, estilo, texto de interface ou animação do front-end.
---

# Design do Orçamentista

Público: **arquitetos** (cultura visual de prancha, desenho técnico e materiais) e, no Demo Day, **jurados olhando um projetor**. A tela tem um único trabalho: **transformar uma lista de materiais em decisão de compra, com clareza visível a 3 metros de distância**.

## 1. Ideia central: a prancha técnica
A interface se inspira na **prancha de arquitetura**: fundo claro e limpo, texto escuro, linhas finas de desenho técnico e **uma** cor de destaque para ação. As cores exatas são do time (ver seção 2); a linguagem de prancha é o que dá identidade.

**O elemento memorável é um só: a "cota de preço".** A faixa mín–médio–máx de cada item é desenhada como uma **linha de cota** de desenho técnico: traço fino, marcas nas pontas e o valor médio escrito sobre a linha. Todo o resto é discreto.

```
 R$ 289 ├────────────●──────────┤ R$ 412
                 médio R$ 341
```

## 2. Tokens

### Cor: papéis, não valores fixos
**As cores não estão definidas aqui.** O time escolhe os valores e coloca **num único lugar** (ex.: `:root` em `globals.css`). Todo componente usa **só os papéis abaixo**, nunca um hex direto. Assim, trocar a paleta inteira é mudar um arquivo.

| Papel (variável CSS) | Para que serve |
|---|---|
| `--cor-fundo` | Fundo das telas |
| `--cor-superficie` | Painéis, tabela e drop zone (levemente diferente do fundo) |
| `--cor-texto` | Texto principal e traço da cota de preço |
| `--cor-texto-2` | Texto secundário, unidades, legendas |
| `--cor-linha` | Bordas, divisórias da tabela, linhas tracejadas e hachura do carregamento |
| `--cor-acao` | Ação principal, links, foco, ponto médio da cota (a **única** cor de destaque) |
| `--cor-definido` | Status Definido |
| `--cor-pendente` | Status Pendente de especificação |
| `--cor-erro` | Erro / Não encontrado |

**Regras ao escolher os valores:**
- Contraste mínimo AA (4,5:1) entre `--cor-texto`/`--cor-texto-2` e `--cor-fundo`. Testar num contraste checker antes de fechar.
- `--cor-definido`, `--cor-pendente` e `--cor-erro` precisam ser distinguíveis entre si **também por quem tem daltonismo**. Por isso status **nunca só por cor**: sempre cor + ícone + texto ("Definido", "Pendente de especificação", "Não encontrado").
- Se a cor de pendente for clara (âmbar/amarelo), usar só em ícone/borda ou com texto escuro por cima.
- Evitar as paletas de "interface gerada por IA" (seção 7).
- Testar no projetor ou com o brilho da tela no mínimo: cores muito próximas somem.

### Tipografia (sugestão; o time pode trocar)
- Sugestão: **Archivo** (Google Fonts), usando as larguras como hierarquia:
  - **Archivo Expanded**, peso 600: títulos e total do orçamento;
  - **Archivo**, peso 400/500: texto e botões;
  - **Archivo Narrow**: células densas da tabela.
- Qualquer que seja a fonte: números com **algarismos tabulares** (`font-variant-numeric: tabular-nums`) para os preços alinharem.
- Escala: 14 / 16 / 20 / 28 / 40 px. Linha de texto com no máximo ~75 caracteres.
- **Não** usar fonte monoespaçada para dados nem CAIXA ALTA em rótulos.

### Forma e espaço
- Bordas de **1 px** em `--cor-linha`. Raio pequeno e com hierarquia: **2 px** em campos e tabela, **8 px** só em painéis e no drop zone.
- **Sem sombras decorativas.** A separação vem de linha e espaço (grade de 8 px).
- Alinhamento à esquerda; números alinhados à direita.

## 3. Telas

### 3.1 Nova obra (upload)
```
┌───────────────────────────────────────────────┐
│ Nova obra                                     │
│ Nome da obra [____________]   CEP [_____-___] │
│ Orçamento do cliente  R$ [__________]         │
│ ┌───────────────────────────────────────────┐ │
│ │  Solte aqui a lista de materiais          │ │
│ │  CSV, Excel, TXT do Revit ou PDF          │ │
│ │  [Escolher arquivo]  [Usar exemplo]       │ │
│ └───────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```
- O CEP é validado na hora (formato + ViaCEP), mostrando bairro e cidade abaixo do campo.
- Drop zone com borda tracejada (lembra área de recorte da prancha). Estado de "arrastando" muda a borda para `--cor-acao`.
- "Usar exemplo" carrega uma obra pronta: **os jurados não têm arquivo do Revit na mão**.

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
- Erros apontados e itens esquecidos aparecem na própria linha, com o botão "Aceitar".
- Barra inferior fixa com o resumo e a ação principal. **A ação mantém o mesmo nome em todo o fluxo**: "Enviar para a IA" → aviso "Enviado para a IA".

### 3.3 Resultado ao vivo
```
┌──────────────────────────────────────┬────────────────────────┐
│ ▣ Suvinil Toque de Seda Branco Neve  │ Total estimado         │
│   180 m² → 2 latas 18 L              │ R$ 18.420              │
│   R$ 289 ├──────●───────┤ R$ 412     │ Cabe no orçamento      │
│ ▣ Porcelanato Portobello 90x90       │ Melhor compra          │
│   …                                  │ Loja única: Casa X     │
│ ⚠ Tinta acrílica fosca branca        │ Frete R$ 180           │
│   Qual marca e litragem?             │ Economia R$ 95 vs.     │
│   [Responder]                        │ dividir em 3 lojas     │
└──────────────────────────────────────┴────────────────────────┘
```
- Cada item tem miniatura 56×56 da imagem buscada, com borda fina em `--cor-linha`.
- **Pendentes ficam juntos no fim da lista**, com a pergunta do agente e o botão "Responder".
- O painel da direita fica fixo (sticky). No celular, ele vira um resumo no topo.

## 4. Carregamento e movimento: linguagem de prancha
**Enquanto o item é pesquisado, ele aparece como desenho ainda não definido:**
- **A cota de preço aparece tracejada.** No desenho técnico, linha tracejada é "linha oculta": o que ainda não está à vista.
- **O quadro da imagem aparece com hachura em 45°.** É o padrão de material em corte.
- Ambos em `--cor-linha`.

**Quando o dado chega (via Supabase Realtime)**, há um único momento de animação:
- o tracejado se fecha numa linha contínua, da esquerda para a direita (300 ms), e os valores aparecem;
- a hachura dá lugar à foto;
- a linha recebe um destaque leve em `--cor-acao` (≈ 8% de opacidade) que some em 1,2 s.

É a resposta a um evento do sistema, não decoração.
- Nada de fade/slide em seções, hover animado em todo cartão ou spinners decorativos.
- `prefers-reduced-motion`: sem animação, só a troca de estado.

## 5. Texto da interface (PT-BR)
- Frases curtas, sem CAIXA ALTA e sem "→" em botões. Verbo de ação no botão: "Enviar para a IA", "Responder", "Baixar plano de compra".
- Fale como arquiteto: "obra", "quantitativo", "especificação", "embalagem", "frete". Não use "payload", "job" ou "registro".
- Erro diz o que houve e o que fazer: "Não consegui ler a planilha: a coluna de quantidade está vazia. Confira a coluna C e envie de novo."
- Estado vazio convida à ação: "Nenhuma obra ainda. Solte a primeira lista de materiais aqui."
- Moeda sempre `R$ 1.234,56`; quantidades com a unidade (`180 m²`, `2 latas 18 L`).

## 6. Qualidade mínima (sempre)
- Responsivo até 360 px de largura.
- Foco visível em `--cor-acao` (2 px). Tabela inteira navegável por teclado.
- Imagens com `alt` = nome do produto.
- **Modo demo** (`?demo=1`): fonte base 18 px, cotas mais grossas e painel de totais maior, porque o projetor apaga detalhes finos.

## 7. Não faça (são os sinais de "interface gerada por IA")
- Fundo creme com destaque terracota; fundo preto com destaque verde-ácido.
- Tudo em cartões iguais com a mesma sombra cinza e gradientes de enfeite.
- Rótulos em CAIXA ALTA espaçada acima de cada título; textos com "A · B · C"; números 01/02/03 sem que exista uma sequência real.
- Uma palavra do título em outra cor ou em itálico.
- Fonte monoespaçada para números pequenos.
- Cor escrita direto no componente (hex) em vez do papel da seção 2.

## 8. Implementação sugerida
- Tailwind CSS apontando para os papéis (`@theme` ou `theme.extend.colors` com `var(--cor-...)`).
- Componentes: `DropZone`, `ReviewTable`, `StatusBadge`, `PriceDimension` (a cota), `ItemRow`, `SummaryPanel`, `LogisticsCard`.
- A cota é um SVG simples: linha + 2 ticks + ponto médio, com estado `carregando` (tracejada) e `pronto` (contínua). Largura proporcional à faixa de preço do próprio item.
- Antes de concluir uma tela: tirar print em 1440 px e em 390 px e conferir contra as seções 6 e 7.
