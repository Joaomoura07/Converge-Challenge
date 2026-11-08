// "Aceitar tudo": só aplica o que cabe, em sequência, e nunca duas vezes.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { estadoInicial, reduzir, type Linha } from "../lista";
import { complementoParaLinha, planejarAceiteTodas } from "./aplicar";
import type { ErroRevisao } from "./tipos";

const L = (id: string, descricao: string, quantidade: string, unidade: string): Linha => ({ id, descricao, quantidade, unidade, categoria: "" });
const erro = (id: string, correcao: ErroRevisao["correcao"]): ErroRevisao =>
  ({ id, regra: "unidade", linhas: [1], item_ids: [], campo: "unidade", valor_atual: "", correcao, motivo: "", fatos: {}, texto: "", redacao: "fixa" }) as unknown as ErroRevisao;
const alterar = (item_id: string, de: string, para: string, campo: "unidade" | "quantidade" = "unidade") =>
  ({ acao: "alterar" as const, remover: [], alteracoes: [{ item_id, linha: 1, campo, de, para }] });

describe("planejarAceiteTodas", () => {
  const linhas = [L("a", "Cimento", "180", "sc"), L("b", "Tijolo", "9500", "br"), L("c", "Areia", "5", "m3")];

  it("aplica todas as correções independentes", () => {
    const r = planejarAceiteTodas(linhas, [erro("e1", alterar("a", "sc", "un")), erro("e2", alterar("b", "br", "un"))]);
    expect(r.aplicar.map((e) => e.id)).toEqual(["e1", "e2"]);
    expect(r.restam).toEqual([]);
  });

  it("a segunda correção que mexe na mesma célula não entra", () => {
    const r = planejarAceiteTodas(linhas, [erro("e1", alterar("a", "sc", "un")), erro("e2", alterar("a", "sc", "kg"))]);
    expect(r.aplicar.map((e) => e.id)).toEqual(["e1"]);
    expect(r.restam.map((e) => e.id)).toEqual(["e2"]);
  });

  it("não aplica correção de linha removida por outra", () => {
    const remover = { acao: "remover" as const, alteracoes: [], remover: [{ item_id: "a", linha: 1 }] };
    const r = planejarAceiteTodas(linhas, [erro("e1", remover), erro("e2", alterar("a", "sc", "un"))]);
    expect(r.aplicar.map((e) => e.id)).toEqual(["e1"]);
    expect(r.restam.map((e) => e.id)).toEqual(["e2"]);
  });

  it("erro sem proposta automática fica de fora", () => {
    const r = planejarAceiteTodas(linhas, [erro("e1", null), erro("e2", alterar("b", "br", "un"))]);
    expect(r.aplicar.map((e) => e.id)).toEqual(["e2"]);
    expect(r.restam.map((e) => e.id)).toEqual(["e1"]);
  });

  it("valor que já mudou na lista não é sobrescrito", () => {
    const r = planejarAceiteTodas(linhas, [erro("e1", alterar("a", "m2", "un"))]);
    expect(r.aplicar).toEqual([]);
  });
});

describe("aceitar tudo no reducer, com a Casa Térrea real", () => {
  const fx = JSON.parse(readFileSync("src/lib/revisao/fixtures/casa-terrea.json", "utf8"));
  const itens = fx.entrada.itens ?? fx.entrada;
  const base = { ...estadoInicial, linhas: itens.map((i: Record<string, string>, k: number) => L(i.id ?? "x" + k, i.descricao, String(i.quantidade ?? ""), i.unidade ?? "")) };

  it("aplica as 4 correções e todos os complementos uma vez só", () => {
    const erros = fx.resposta.erros as ErroRevisao[];
    const comps = fx.resposta.complementos;
    const { aplicar } = planejarAceiteTodas(base.linhas, erros);
    let e = base;
    for (const x of aplicar) e = reduzir(e, { tipo: "aceitar_correcao", id: x.id, correcao: x.correcao! });
    for (const c of comps) e = reduzir(e, { tipo: "aceitar_complemento", id: c.id, linha: complementoParaLinha(c, "n-" + c.id) });
    const segunda = aplicar.reduce((s, x) => reduzir(s, { tipo: "aceitar_correcao", id: x.id, correcao: x.correcao! }), e);
    expect(segunda).toBe(e); // repetir o "aceitar tudo" não muda nada
    expect(e.linhas.length).toBe(base.linhas.length + comps.length);
    expect(aplicar.length).toBe(erros.filter((x) => x.correcao).length);
  });
});
