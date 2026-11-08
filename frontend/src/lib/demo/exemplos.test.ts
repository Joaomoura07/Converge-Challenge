import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import * as pdfjsLegacy from "pdfjs-dist/legacy/build/pdf.mjs";
import { lerArquivo } from "@/lib/importar/arquivo";
import { importacaoParaLinhas } from "@/lib/importar/paraLinhas";
import { ehErro, type Importacao } from "@/lib/importar/tipos";
import { contarErros, errosPorId } from "@/lib/lista";
import { EXEMPLOS_DEMO, MODELOS_DEMO, FORMATOS_DEMO, modoPeloArquivo } from "./exemplos";

const PUBLICO = join(__dirname, "../../../public/exemplos/demo");
let n = 0;
const novoId = () => `id-${++n}`;

describe("exemplos para baixar na /demo", () => {
  it("2 arquivos por formato, com nomes teste_1 e teste_2", () => {
    for (const f of FORMATOS_DEMO) {
      const doFormato = EXEMPLOS_DEMO.filter((e) => e.modo === f.modo).map((e) => e.arquivo.split(".")[0]);
      expect(doFormato, f.rotulo).toEqual(["teste_1", "teste_2"]);
    }
  });

  it("1 MODELO por formato", () => {
    for (const f of FORMATOS_DEMO) {
      expect(MODELOS_DEMO.filter((m) => m.modo === f.modo).map((m) => m.arquivo.split(".")[0]), f.rotulo).toEqual(["MODELO"]);
    }
  });

  it.each([...MODELOS_DEMO, ...EXEMPLOS_DEMO])("$arquivo é lido pelo site com pendências apenas quando documentadas", async (ex) => {
    const bytes = new Uint8Array(readFileSync(join(PUBLICO, ex.arquivo)));
    const r = await lerArquivo({ nome: ex.arquivo, bytes, aba: null, pdfjs: pdfjsLegacy as never });
    expect(ehErro(r), JSON.stringify(r).slice(0, 200)).toBe(false);
    const imp = r as Importacao;
    expect(imp.itens.length).toBeGreaterThanOrEqual(3);
    expect(imp.itens.length).toBeLessThanOrEqual(10);
    expect(modoPeloArquivo(ex.arquivo)).toBe(ex.modo);
    // nenhum campo que trave o envio, exceto DXF (a planta traz medidas, não o nome do material: o jurado descreve)
    const erros = contarErros(errosPorId(importacaoParaLinhas(imp, novoId)));
    if (ex.arquivo === "teste_2.skp") {
      expect(imp.itens.filter(i => i.quantidade == null)).toHaveLength(1);
      expect(erros).toBeGreaterThan(0); // área precisa ser informada pelo arquiteto
    } else if (ex.modo !== "dxf") expect(erros).toBe(0);
  });

  it("a aba acompanha a extensão do arquivo solto", () => {
    expect(modoPeloArquivo("Lista FINAL.XLSX")).toBe("excel");
    expect(modoPeloArquivo("tabela.txt")).toBe("revit");
    expect(modoPeloArquivo("modelo.ifc")).toBe("ifc");
    expect(modoPeloArquivo("foto.png")).toBeNull();
  });

  // Os itens que o leitor do site tira de cada teste ficam numa fixture que o backend usa para garantir, com as regras
  // REAIS do revisor e dos complementos, os dois percursos: pesquisa específica e revisão
  // (tests/test_exemplos_demo.py). Mudou um arquivo de exemplo? Rode com ATUALIZAR_FIXTURE_DEMO=1.
  it("a fixture dos itens dos testes está em dia com os arquivos", async () => {
    const atual: Record<string, unknown> = {};
    for (const ex of EXEMPLOS_DEMO) {
      const bytes = new Uint8Array(readFileSync(join(PUBLICO, ex.arquivo)));
      const r = (await lerArquivo({ nome: ex.arquivo, bytes, aba: null, pdfjs: pdfjsLegacy as never })) as Importacao;
      atual[ex.arquivo] = r.itens.map((i) => ({ descricao: i.descricao, quantidade: i.quantidade, unidade: i.unidade, categoria: i.categoria }));
    }
    const caminho = join(__dirname, "fixtures/itens-exemplos.json");
    if (process.env.ATUALIZAR_FIXTURE_DEMO === "1") writeFileSync(caminho, JSON.stringify(atual, null, 1) + "\n");
    expect(existsSync(caminho), "rode com ATUALIZAR_FIXTURE_DEMO=1").toBe(true);
    expect(JSON.parse(readFileSync(caminho, "utf-8"))).toEqual(JSON.parse(JSON.stringify(atual)));
  });

  it("preserva os quantitativos descritos no roteiro, sem confundir saco com kg nem instância com área", () => {
    const itens = JSON.parse(readFileSync(join(__dirname, "fixtures/itens-exemplos.json"), "utf8"));
    const quantidades = (nome: string) => itens[nome].map((i: { quantidade: number | null }) => i.quantidade);
    for (const ext of ["csv", "xlsx", "txt", "pdf"]) {
      expect(quantidades(`teste_1.${ext}`)).toEqual([6, 4, 8, 40, 18]);
    }
    for (const ext of ["ifc", "skp"]) {
      expect(quantidades(`teste_1.${ext}`)).toEqual([6, 4, 8, 2, 1]);
      expect(itens[`teste_1.${ext}`].every((i: { unidade: string }) => i.unidade === "un")).toBe(true);
    }
    expect(quantidades("teste_1.dxf")).toEqual([4, 8, 1]);
    expect(quantidades("teste_2.dxf")).toEqual([18, 18, 2, 4]);
    expect(quantidades("teste_2.ifc")).toEqual([18, 4, 30, 4, 2]);
    expect(quantidades("teste_2.skp")).toEqual([null, 6, 4, 8, 1]);
  });
});
