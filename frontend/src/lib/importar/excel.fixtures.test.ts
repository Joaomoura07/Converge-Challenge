// Roda o leitor de Excel contra os casos de planilha de tests/importacao (xlsx, xls, xlsm, ods e TC-007).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { comparar, FIX, manifest } from "./comparar-fixtures";
import { importarExcel, tamanhoDescompactado } from "./excel";

const EXT = /\.(xlsx|xls|xlsm|ods)$/i;

const casos = manifest.casos.filter(
  (c) => c.tipo === "parse" && c.variantes.every((v) => EXT.test(v.entrada) && !v.entrada.startsWith("grandes/")),
);

describe("fixtures de planilha de tests/importacao", () => {
  it("encontrou os casos de planilha do acervo", () => {
    expect(casos.map((c) => c.id)).toContain("TC-002");
    expect(casos.length).toBeGreaterThanOrEqual(18);
  });

  for (const caso of casos) {
    for (const v of caso.variantes) {
      it(`${caso.id} [${caso.prioridade}] ${caso.titulo}`, () => {
        const caminho = join(FIX, v.entrada);
        expect(existsSync(caminho)).toBe(true);
        const bytes = new Uint8Array(readFileSync(caminho));
        const obt = importarExcel({ nome: v.entrada.split("/").pop()!, bytes });
        const esp = JSON.parse(readFileSync(join(FIX, v.esperado!), "utf8"));
        expect(comparar(esp, obt)).toEqual([]);
      });
    }
  }
});

describe("casos próprios do leitor de Excel", () => {
  const ler = (arq: string) => new Uint8Array(readFileSync(join(FIX, arq)));

  it("lista as abas e marca as ocultas (TC-072) e as vazias (TC-073)", () => {
    const r = importarExcel({ nome: "TC-072.xlsx", bytes: ler("TC-072.xlsx") });
    if ("erro" in r) throw new Error("não deveria falhar");
    const abas = "abas" in r ? r.abas : [];
    expect(abas.some((a) => a.oculta)).toBe(true);
    expect(abas.find((a) => a.nome === r.origem.aba)?.oculta).toBe(false);
    const r2 = importarExcel({ nome: "TC-073.xlsx", bytes: ler("TC-073.xlsx") });
    if ("erro" in r2) throw new Error("não deveria falhar");
    expect(("abas" in r2 ? r2.abas : []).some((a) => !a.temDados)).toBe(true);
  });

  it("a pessoa pode trocar de aba (TC-071) e a lista muda", () => {
    const bytes = ler("TC-071.xlsx");
    const padrao = importarExcel({ nome: "TC-071.xlsx", bytes });
    if ("erro" in padrao || !("abas" in padrao)) throw new Error("não deveria falhar");
    const outra = padrao.abas.find((a) => a.nome !== padrao.origem.aba && a.temDados && !a.oculta);
    expect(outra).toBeDefined();
    const trocada = importarExcel({ nome: "TC-071.xlsx", bytes, aba: outra!.nome });
    if ("erro" in trocada) throw new Error("não deveria falhar");
    expect(trocada.origem.aba).toBe(outra!.nome);
    expect(trocada.itens[0].descricao).not.toBe(padrao.itens[0].descricao);
  });

  it("aba inexistente cai na aba padrão", () => {
    const r = importarExcel({ nome: "TC-071.xlsx", bytes: ler("TC-071.xlsx"), aba: "não existe" });
    expect("erro" in r).toBe(false);
  });

  it("a linha de cada item é a linha da planilha (origem preservada para os avisos)", () => {
    const r = importarExcel({ nome: "TC-077.xlsx", bytes: ler("TC-077.xlsx") });
    if ("erro" in r) throw new Error("não deveria falhar");
    expect(r.avisos.filter((a) => a.codigo === "ERRO_FORMULA").map((a) => a.linha)).toEqual([2, 3]);
    expect(r.itens.map((i) => i.linha)).toEqual([2, 3, 4]);
  });

  it("extensão desconhecida e arquivo vazio são recusados", () => {
    expect("erro" in importarExcel({ nome: "x.pdf", bytes: new Uint8Array([1]) })).toBe(true);
    const vazio = importarExcel({ nome: "x.xlsx", bytes: new Uint8Array(0) });
    expect("erro" in vazio && vazio.erro.codigo).toBe("ARQUIVO_VAZIO");
  });

  it("binário que não é planilha nem texto é recusado sem lixo", () => {
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]);
    const r = importarExcel({ nome: "foto.xlsx", bytes: png });
    expect("erro" in r && r.erro.codigo).toBe("FORMATO_INVALIDO");
  });

  it("bomba de descompressão é detectada sem descompactar (TC-092)", () => {
    const t = tamanhoDescompactado(ler("TC-092.xlsx"));
    expect(t && t.total).toBeGreaterThan(128 * 1024 * 1024);
    const r = importarExcel({ nome: "TC-092.xlsx", bytes: ler("TC-092.xlsx") });
    expect("erro" in r && r.erro.codigo).toBe("ARQUIVO_GRANDE_DEMAIS");
  });

  it("macro do .xlsm não é executada: só os dados são lidos (TC-005)", () => {
    const r = importarExcel({ nome: "TC-005.xlsm", bytes: ler("TC-005.xlsm") });
    if ("erro" in r) throw new Error("não deveria falhar");
    expect(r.origem.formato).toBe("xlsm");
    expect(r.itens).toHaveLength(5);
  });

  it("planilha com 50 linhas formatada até o fim da grade lê só as 50, rápido (TC-083)", () => {
    const t0 = performance.now();
    const r = importarExcel({ nome: "TC-083.xlsx", bytes: ler("TC-083.xlsx") });
    expect(performance.now() - t0).toBeLessThan(2000);
    if ("erro" in r) throw new Error("não deveria falhar");
    expect(r.itens).toHaveLength(50);
  });
});
