import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import * as pdfjsLegacy from "pdfjs-dist/legacy/build/pdf.mjs";
import { lerArquivo } from "@/lib/importar/arquivo";
import { importacaoParaLinhas } from "@/lib/importar/paraLinhas";
import { ehErro, type Importacao } from "@/lib/importar/tipos";
import { contarErros, errosPorId } from "@/lib/lista";
import { EXEMPLOS_DEMO, FORMATOS_DEMO, modoPeloArquivo } from "./exemplos";

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

  it.each(EXEMPLOS_DEMO)("$arquivo é lido pelo leitor real do site, curto e sem erro", async (ex) => {
    const bytes = new Uint8Array(readFileSync(join(PUBLICO, ex.arquivo)));
    const r = await lerArquivo({ nome: ex.arquivo, bytes, aba: null, pdfjs: pdfjsLegacy as never });
    expect(ehErro(r), JSON.stringify(r).slice(0, 200)).toBe(false);
    const imp = r as Importacao;
    expect(imp.itens.length).toBeGreaterThanOrEqual(3);
    expect(imp.itens.length).toBeLessThanOrEqual(15);   // curto: a pesquisa termina rápido na demo
    expect(modoPeloArquivo(ex.arquivo)).toBe(ex.modo);
    // nenhum campo que trave o envio, exceto DXF (a planta traz medidas, não o nome do material: o jurado descreve)
    const erros = contarErros(errosPorId(importacaoParaLinhas(imp, novoId)));
    if (ex.modo !== "dxf") expect(erros).toBe(0);
  });

  it("a aba acompanha a extensão do arquivo solto", () => {
    expect(modoPeloArquivo("Lista FINAL.XLSX")).toBe("excel");
    expect(modoPeloArquivo("tabela.txt")).toBe("revit");
    expect(modoPeloArquivo("modelo.ifc")).toBe("ifc");
    expect(modoPeloArquivo("foto.png")).toBeNull();
  });
});
