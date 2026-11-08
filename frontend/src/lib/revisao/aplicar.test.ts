import { describe, expect, it } from "vitest";
import type { Linha } from "../lista";
import {
  aplicarCorrecao,
  complementoParaLinha,
  numeroNaTabela,
  numerosNaTabela,
  paraItensRevisao,
  quantidadeParaTexto,
  versaoDaLista,
} from "./aplicar";
import type { ComplementoSugerido, CorrecaoSugerida } from "./tipos";

const L = (id: string, descricao: string, quantidade: string, unidade: string, extra: Partial<Linha> = {}): Linha => ({
  id, descricao, quantidade, unidade, categoria: "", ...extra,
});

const lista = (): Linha[] => [
  L("a", "Cimento Votoran", "180", "sc", { linhaOrigem: 12 }),
  L("b", "Tinta branca", "50", "m2"),
  L("c", "Tinta Suvinil branca", "50", "m2"),
];

const alterarUnidade: CorrecaoSugerida = {
  acao: "alterar", remover: [],
  alteracoes: [{ item_id: "a", linha: 12, campo: "unidade", de: "sc", para: "un" }],
};

describe("aplicarCorrecao", () => {
  it("altera só o campo proposto e não mexe na lista original", () => {
    const base = lista();
    const copia = structuredClone(base);
    const nova = aplicarCorrecao(base, alterarUnidade)!;
    expect(nova.find((l) => l.id === "a")!.unidade).toBe("un");
    expect(nova.find((l) => l.id === "a")!.quantidade).toBe("180");
    expect(base).toEqual(copia);
    expect(nova[1]).toBe(base[1]); // linhas não tocadas são as mesmas
  });

  it("remove linhas por ID, não por posição nem por número de linha", () => {
    const c: CorrecaoSugerida = { acao: "remover", alteracoes: [], remover: [{ item_id: "b", linha: 2 }] };
    expect(aplicarCorrecao(lista(), c)!.map((l) => l.id)).toEqual(["a", "c"]);
  });

  it("mesclar soma na mantida e remove a outra", () => {
    const c: CorrecaoSugerida = {
      acao: "mesclar",
      alteracoes: [{ item_id: "b", linha: 2, campo: "quantidade", de: "50", para: "100" }],
      remover: [{ item_id: "c", linha: 3 }],
    };
    const nova = aplicarCorrecao(lista(), c)!;
    expect(nova.map((l) => [l.id, l.quantidade])).toEqual([["a", "180"], ["b", "100"]]);
  });

  it("recusa aplicar se o valor mudou depois do cálculo", () => {
    const editada = lista().map((l) => (l.id === "a" ? { ...l, unidade: "kg" } : l));
    expect(aplicarCorrecao(editada, alterarUnidade)).toBeNull();
  });

  it("recusa aplicar se a linha foi removida ou não tem id", () => {
    expect(aplicarCorrecao(lista().filter((l) => l.id !== "a"), alterarUnidade)).toBeNull();
    const semId: CorrecaoSugerida = { ...alterarUnidade, alteracoes: [{ ...alterarUnidade.alteracoes[0], item_id: null }] };
    expect(aplicarCorrecao(lista(), semId)).toBeNull();
  });

  it("colunas trocadas: altera quantidade e unidade da mesma linha com os valores originais", () => {
    const base = [L("x", "Coral Rende Muito", "", "4,20")];
    const c: CorrecaoSugerida = {
      acao: "alterar", remover: [],
      alteracoes: [
        { item_id: "x", linha: 2, campo: "quantidade", de: "", para: "4,20" },
        { item_id: "x", linha: 2, campo: "unidade", de: "4,20", para: "m2" },
      ],
    };
    expect(aplicarCorrecao(base, c)).toEqual([L("x", "Coral Rende Muito", "4,20", "m2")]);
  });
});

describe("paraItensRevisao e versaoDaLista", () => {
  it("usa a linha do arquivo, senão a posição, e ignora linhas sem descrição", () => {
    const itens = paraItensRevisao([L("a", "A", "1", "un", { linhaOrigem: 7 }), L("b", "  ", "1", "un"), L("c", "C", "1", "un")]);
    expect(itens.map((i) => [i.id, i.linhaOrigem])).toEqual([["a", 7], ["c", 3]]);
  });

  it("qualquer edição muda a versão; a mesma lista dá a mesma versão", () => {
    const v = versaoDaLista(lista());
    expect(versaoDaLista(lista())).toBe(v);
    for (const campo of ["descricao", "quantidade", "unidade", "categoria"] as const) {
      const editada = lista();
      editada[1] = { ...editada[1], [campo]: editada[1][campo] + "x" };
      expect(versaoDaLista(editada)).not.toBe(v);
    }
    expect(versaoDaLista(lista().slice(1))).not.toBe(v);
  });
});

describe("complementoParaLinha", () => {
  const comp: ComplementoSugerido = {
    id: "k1", regra: "porcelanato", descricao: "Argamassa colante AC-III 20 kg (saco)", quantidade: 15, unidade: "un",
    categoria: "Revestimentos e argamassas", motivo: "Para 48 m² costumam faltar argamassa.", origem_linhas: [1],
    origem_item_ids: ["p"], estimativa_consumo: true,
  };

  it("vira linha marcada como sugerida, com regra, motivo, origem e estimativa de consumo", () => {
    const l = complementoParaLinha(comp, "novo");
    expect(l).toMatchObject({ id: "novo", descricao: comp.descricao, quantidade: "15", unidade: "un", categoria: comp.categoria });
    expect(l.sugerida).toEqual({
      sugestaoId: "k1", regra: "porcelanato", motivo: comp.motivo, origemLinhas: [1], estimativaConsumo: true,
    });
  });

  it("quantidade decimal sai com vírgula", () => {
    expect(quantidadeParaTexto(2.5)).toBe("2,5");
    expect(quantidadeParaTexto(3)).toBe("3");
  });
});

describe("numeroNaTabela", () => {
  it("traduz a linha do arquivo (CSV conta o cabeçalho) para o número da coluna # (medido em 08/11: 'linha 6' no 5º item)", () => {
    const csv = [2, 3, 4, 5, 6].map((n, i) => L(`l${i}`, `item ${i}`, "1", "un", { linhaOrigem: n }));
    expect(numeroNaTabela(csv, 6)).toBe(5);
    expect(numerosNaTabela(csv, [2, 6])).toEqual([1, 5]);
  });
  it("linha digitada usa a posição; complemento aceito sem linhaOrigem não rouba a linha do arquivo", () => {
    const misto = [L("a", "x", "1", "un", { linhaOrigem: 2 }), L("b", "y", "1", "un"), L("c", "z", "1", "un", { linhaOrigem: 3 })];
    expect(numeroNaTabela(misto, 3)).toBe(3);
    expect(numeroNaTabela(misto, 2)).toBe(1);
  });
  it("linha que saiu da tabela mantém o número original", () => {
    expect(numeroNaTabela([L("a", "x", "1", "un", { linhaOrigem: 2 })], 9)).toBe(9);
  });
});
