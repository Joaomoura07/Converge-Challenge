// Arquivos de quem NÃO conhece o "formato certo" (teste "como leigo", 08/11): planilha sem cabeçalho, lista numa
// coluna só, quantidade com a embalagem na mesma célula, nomes de coluna esquisitos, unidade por extenso, lista do
// WhatsApp. Antes, metade virava erro ou item sem quantidade. Cada caso diz o que o arquiteto deve ver na tabela.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { lerArquivo } from "./arquivo";
import { lerLinhaLivre } from "./textoLivre";
import { importarTxt } from "./txt";
import type { Importacao } from "./tipos";

const ler = async (texto: string, nome = "lista.csv") => {
  const r = await lerArquivo({ nome, bytes: new TextEncoder().encode(texto) });
  if ("erro" in r) throw new Error(`não deveria falhar: ${r.erro.mensagem}`);
  return r as Importacao;
};
const resumo = (r: Importacao) => r.itens.map((i) => [i.descricao, i.quantidade, i.unidade]);

describe("planilha montada à mão", () => {
  it("sem cabeçalho: colunas deduzidas pelo conteúdo, com aviso", async () => {
    const r = await ler("Cimento CP II;10;sacos\nAreia média;2;m3\nTijolo 8 furos;500;un\n");
    expect(resumo(r)).toEqual([["Cimento CP II", 10, "saco"], ["Areia média", 2, "m3"], ["Tijolo 8 furos", 500, "un"]]);
    expect(r.avisos.map((a) => a.codigo)).toContain("SEM_CABECALHO");
  });

  it("sem cabeçalho e com a numeração na 1ª coluna: a numeração não vira quantidade", async () => {
    const r = await ler("1;Cimento;10;sc\n2;Areia;2;m3\n3;Tinta branca;3;lata\n");
    expect(resumo(r)).toEqual([["Cimento", 10, "sc"], ["Areia", 2, "m3"], ["Tinta branca", 3, "lata"]]);
  });

  it("quantidade com a embalagem na mesma célula: '10 sacos' vira 10 un com a embalagem na descrição", async () => {
    const r = await ler("Material;Quantidade\nCimento;10 sacos\nAreia;2 m³\nTinta acrílica branca;3 latas\nPiso;30m²\n");
    expect(resumo(r)).toEqual([
      ["Cimento (saco)", 10, "un"], ["Areia", 2, "m3"], ["Tinta acrílica branca (lata)", 3, "un"], ["Piso", 30, "m2"],
    ]);
  });

  it("coluna 'Item' com a numeração e 'O que' com o material: a descrição é o material", async () => {
    const r = await ler("Item;O que;Qtde.;Und.;Obs\n1;Cimento;10;sc;\n2;Areia;2;m3;média\n");
    expect(resumo(r)).toEqual([["Cimento", 10, "sc"], ["Areia", 2, "m3"]]);
  });

  it("unidade por extenso, no plural e milheiro", async () => {
    const r = await ler("Descrição;Quantidade;Unidade\nPiso;30;metro quadrado\nCimento;10;sacos\nTijolo;2;milheiro\nAreia;3;metros cúbicos\n");
    expect(resumo(r)).toEqual([["Piso", 30, "m2"], ["Cimento", 10, "saco"], ["Tijolo", 2000, "un"], ["Areia", 3, "m3"]]);
  });

  it("total em reais numa coluna de preço não gera 'total divergente' falso", async () => {
    const r = await ler("Orçamento obra do João\n\nDescrição;Qtd;Un;Preço;Total\nCimento;10;sc;35,00;350,00\nTotal;;;;350,00\n");
    expect(r.avisos.map((a) => a.codigo)).not.toContain("TOTAL_DIVERGENTE");
  });

  it("colunas sem nenhum texto continuam recusadas (TC-054), com orientação para o leigo", async () => {
    const r = await lerArquivo({ nome: "x.csv", bytes: new TextEncoder().encode("Foo;Bar;Baz\n1;2;3\n") });
    expect("erro" in r && r.erro.codigo).toBe("CABECALHO_NAO_ENCONTRADO");
    expect("erro" in r && r.erro.mensagem).toMatch(/nome do material.*quantidade/);
  });
});

describe("lista em texto, um material por linha", () => {
  it("CSV de uma coluna só vira lista", async () => {
    const r = await ler("10 sacos de cimento\n2 m³ de areia\n500 tijolos\ntinta branca 18 litros\nporcelanato 60x60 - 30 m2\n");
    expect(resumo(r)).toEqual([
      ["cimento (saco)", 10, "un"], ["areia", 2, "m3"], ["tijolos", 500, "un"], ["tinta branca", 18, "l"], ["porcelanato 60x60", 30, "m2"],
    ]);
    expect(r.avisos.map((a) => a.codigo)).toContain("LISTA_TEXTO");
  });

  it("só os nomes, com o título da coluna: o título não vira item e as quantidades ficam para preencher", async () => {
    const r = await ler("Materiais\nCimento\nAreia\nTinta branca\n");
    expect(resumo(r)).toEqual([["Cimento", null, null], ["Areia", null, null], ["Tinta branca", null, null]]);
  });

  it.each([
    ["- 15 sacos 20 kg Argamassa colante AC-III", "Argamassa colante AC-III (saco 20 kg)", 15, "un"],
    ["- 3 lt 18 L Selador acrílico", "Selador acrílico (lata 18 L)", 3, "un"],
    ["- 33 caixas 1,62 m² Porcelanato cinza 90x90", "Porcelanato cinza 90x90 (caixa 1,62 m²)", 33, "un"],
    ["- 2,80 m² Bancada em quartzo", "Bancada em quartzo", 2.8, "m2"],
    ["- 5 Soleira em granito", "Soleira em granito", 5, "un"],
    ["- 4 Caixa sifonada 150 mm", "Caixa sifonada 150 mm", 4, "un"],
    ["2 milheiros de tijolo", "tijolo", 2000, "un"],
    ["Cimento (10 sc)", "Cimento (saco)", 10, "un"],
    ["[07/11/2026 10:21] Ana: 6 rolos Fita crepe", "Fita crepe (rolo)", 6, "un"],
  ])("%s", (linha, descricao, quantidade, unidade) => {
    expect(lerLinhaLivre(linha)).toMatchObject({ descricao, quantidade, unidade });
  });

  it("conversa e endereço ficam de fora", () => {
    for (const l of ["Oi, preciso de:", "Obra: Av. Boa Viagem, 2850", "Quantidades já com a perda 👍", "Bom dia!"]) {
      expect(lerLinhaLivre(l)).toBeNull();
    }
  });
});

describe("listas do WhatsApp reais do acervo (docs/arquivos-teste)", () => {
  const RAIZ = join(__dirname, "../../../../docs/arquivos-teste");
  const listas = readdirSync(RAIZ)
    .filter((d) => /^\d\d-/.test(d))
    .flatMap((obra) => readdirSync(join(RAIZ, obra)).filter((n) => /WhatsApp\)\.txt$/.test(n)).map((n) => join(RAIZ, obra, n)));

  it("todas viram lista com categoria, sem título, endereço ou recado como item", () => {
    expect(listas.length).toBeGreaterThan(3);
    for (const caminho of listas) {
      const r = importarTxt({ nome: "lista.txt", bytes: new Uint8Array(readFileSync(caminho)) });
      if ("erro" in r) throw new Error(`${caminho}: ${r.erro.mensagem}`);
      expect(r.itens.length).toBeGreaterThan(5);
      for (const i of r.itens) {
        expect(i.descricao ?? "").not.toMatch(/^(lista de compras|obra:|qualquer d[uú]vida)|^²/i);
      }
      // quase todos com quantidade (a lista do WhatsApp sempre traz a quantidade)
      expect(r.itens.filter((i) => i.quantidade !== null).length / r.itens.length).toBeGreaterThan(0.9);
    }
  });

  it("a do Apartamento Boa Viagem dá os mesmos 47 materiais da planilha da obra", () => {
    const apto = listas.find((c) => c.includes("01-apto-boa-viagem"));
    const r = importarTxt({ nome: "lista.txt", bytes: new Uint8Array(readFileSync(apto as string)) });
    if ("erro" in r) throw new Error(r.erro.mensagem);
    expect(r.itens).toHaveLength(47);
    expect(r.itens[0]).toMatchObject({ categoria: "Pintura", descricao: "Selador acrílico pigmentado Coral (lata 18 L)", quantidade: 1, unidade: "un" });
  });
});
