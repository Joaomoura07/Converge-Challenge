import { describe, expect, it } from "vitest";
import {
  contarErros,
  errosPorId,
  estadoInicial,
  itensValidados,
  primeiroErro,
  reduzir,
  type Acao,
  type EstadoLista,
} from "./lista";

const rodar = (acoes: Acao[], base: EstadoLista = estadoInicial) => acoes.reduce(reduzir, base);

const preencher = (id: string, d: string, q: string, u: string): Acao[] => [
  { tipo: "editar", id, campo: "descricao", valor: d },
  { tipo: "editar", id, campo: "quantidade", valor: q },
  { tipo: "editar", id, campo: "unidade", valor: u },
];

describe("lista de revisão", () => {
  it("começa vazia, no modo manual", () => {
    expect(estadoInicial.linhas).toEqual([]);
    expect(estadoInicial.modo).toBe("manual");
  });

  it("inclui linhas com ID próprio e ignora ID repetido", () => {
    const e = rodar([
      { tipo: "adicionar", id: "a" },
      { tipo: "adicionar", id: "b" },
      { tipo: "adicionar", id: "a" },
    ]);
    expect(e.linhas.map((l) => l.id)).toEqual(["a", "b"]);
  });

  it("edita só a linha certa", () => {
    const e = rodar([
      { tipo: "adicionar", id: "a" },
      { tipo: "adicionar", id: "b" },
      ...preencher("b", "Cimento", "10", "kg"),
    ]);
    expect(e.linhas[0].descricao).toBe("");
    expect(e.linhas[1]).toMatchObject({ descricao: "Cimento", quantidade: "10", unidade: "kg" });
  });

  it("exclui linha com erro sem mexer nos erros das outras", () => {
    const e = rodar([
      { tipo: "adicionar", id: "a" },
      { tipo: "adicionar", id: "b" },
      { tipo: "adicionar", id: "c" },
      ...preencher("a", "Tinta", "0", "l"),
      ...preencher("b", "Areia", "2", "m3"),
      ...preencher("c", "Fio", "abc", "m"),
    ]);
    const antes = errosPorId(e.linhas);
    expect(Object.keys(antes).sort()).toEqual(["a", "c"]);
    const depois = errosPorId(reduzir(e, { tipo: "remover", id: "b" }).linhas);
    expect(depois).toEqual(antes);
    const semA = errosPorId(reduzir(e, { tipo: "remover", id: "a" }).linhas);
    expect(Object.keys(semA)).toEqual(["c"]);
    expect(semA.c.quantidade).toBe(antes.c.quantidade);
  });

  it("remover limpa os toques da linha removida", () => {
    const e = rodar([
      { tipo: "adicionar", id: "a" },
      { tipo: "tocar", id: "a", campo: "descricao" },
      { tipo: "remover", id: "a" },
    ]);
    expect(e.tocados).toEqual({});
  });

  it("alternar modo preserva as edições", () => {
    const antes = rodar([{ tipo: "adicionar", id: "a" }, ...preencher("a", "Piso", "12,5", "m²")]);
    const depois = rodar(
      [
        { tipo: "alternar_modo", modo: "csv" },
        { tipo: "alternar_modo", modo: "pdf" },
        { tipo: "alternar_modo", modo: "manual" },
      ],
      antes,
    );
    expect(depois.linhas).toEqual(antes.linhas);
    expect(depois.tocados).toEqual(antes.tocados);
    expect(depois.modo).toBe("manual");
  });

  it("importador futuro acrescenta ou substitui na mesma lista", () => {
    const base = rodar([{ tipo: "adicionar", id: "a" }]);
    const nova = [{ id: "x", descricao: "d", quantidade: "1", unidade: "un", categoria: "" }];
    const somar = reduzir(base, { tipo: "importar", linhas: nova, como: "acrescentar" });
    const trocar = reduzir(base, { tipo: "importar", linhas: nova, como: "substituir" });
    expect(somar.linhas.map((l) => l.id)).toEqual(["a", "x"]);
    expect(trocar.linhas.map((l) => l.id)).toEqual(["x"]);
  });

  it("revelar_erros marca todos os campos e primeiroErro segue a ordem da lista", () => {
    const e = rodar([
      { tipo: "adicionar", id: "a" },
      { tipo: "adicionar", id: "b" },
      ...preencher("a", "Ok", "1", "un"),
      { tipo: "revelar_erros" },
    ]);
    const erros = errosPorId(e.linhas);
    expect(primeiroErro(e.linhas, erros)).toEqual({ id: "b", campo: "descricao" });
    expect(contarErros(erros)).toBe(3);
    expect(Object.keys(e.tocados)).toHaveLength(6);
  });

  it("itensValidados converte vírgula, m² e categoria opcional", () => {
    const e = rodar([
      { tipo: "adicionar", id: "a" },
      ...preencher("a", " Porcelanato 60x60 ", "12,5", "m²"),
      { tipo: "editar", id: "a", campo: "categoria", valor: "  " },
    ]);
    expect(itensValidados(e.linhas)).toEqual([
      { id: "a", descricao: "Porcelanato 60x60", quantidade: 12.5, unidade: "m2", categoria: null },
    ]);
    expect(itensValidados(rodar([{ tipo: "adicionar", id: "z" }]).linhas)).toBeNull();
  });
});
