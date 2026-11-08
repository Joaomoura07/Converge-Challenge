// Matriz de casos por formato, pelo ponto único de leitura (lerArquivo): CSV, Excel, TXT do Revit, PDF com texto,
// DXF, DWG, IFC e SKP. Cada formato tem: um caso válido com resultado esperado, recusas que NÃO devem criar itens,
// extensão trocada e as propriedades que valem para qualquer leitor (determinismo, entrada intacta, contrato dos itens).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { create, type Point3 } from "openskp";
import { describe, expect, it } from "vitest";
import * as pdfjsLegacy from "pdfjs-dist/legacy/build/pdf.mjs";
import { importacaoParaLinhas } from "./paraLinhas";
import { lerArquivo, type ResultadoArquivo } from "./arquivo";
import type { PdfjsMinimo } from "./pdf";
import { ehErro, type Importacao } from "./tipos";
import { UNIDADES } from "../validacao";

const RAIZ = join(__dirname, "../../../..");
const FIX = join(RAIZ, "tests/importacao/fixtures");
const MODELOS = join(FIX, "modelos");
const pdfjs = pdfjsLegacy as unknown as PdfjsMinimo;
const bytesDe = (c: string) => new Uint8Array(readFileSync(c));
const texto = (s: string) => new TextEncoder().encode(s);
const ler = (nome: string, bytes: Uint8Array) => lerArquivo({ nome, bytes, pdfjs });
const ok = (r: ResultadoArquivo): Importacao => {
  if (ehErro(r)) throw new Error(`${r.erro.codigo}: ${r.erro.mensagem}`);
  return r;
};
const codigo = (r: ResultadoArquivo) => (ehErro(r) ? r.erro.codigo : null);

// ---------------------------------------------------------------- CSV
describe("CSV", () => {
  it("válido: TC-001 confere item a item com o esperado", async () => {
    const esp = JSON.parse(readFileSync(join(FIX, "TC-001.esperado.json"), "utf8"));
    const r = ok(await ler("TC-001.csv", bytesDe(join(FIX, "TC-001.csv"))));
    expect(r.origem.formato).toBe("csv");
    expect(r.itens.map((i) => [i.linha, i.descricao, i.quantidade, i.unidade])).toEqual(
      esp.itens.map((i: any) => [i.linha, i.descricao, i.quantidade, i.unidade]),
    );
  });
  it("recusa: vazio e PNG renomeado para .csv", async () => {
    expect(ehErro(await ler("a.csv", new Uint8Array()))).toBe(true);
    expect(ehErro(await ler("a.csv", new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0x0d])))).toBe(true);
  });
  it("números brasileiros: 1.234,50 e 12,5 viram 1234.5 e 12.5", async () => {
    const r = ok(await ler("n.csv", texto("Descrição;Quantidade;Unidade\nTinta Suvinil Toque de Seda;1.234,50;l\nCimento CP II;12,5;kg\n")));
    expect(r.itens.map((i) => i.quantidade)).toEqual([1234.5, 12.5]);
  });
});

// ---------------------------------------------------------------- Excel
describe("Excel (xlsx, xls, xlsm, ods)", () => {
  for (const [arq, formato] of [["TC-002.xlsx", "xlsx"], ["TC-004.xls", "xls"], ["TC-005.xlsm", "xlsm"]] as const) {
    it(`válido: ${arq} confere a quantidade de itens com o esperado`, async () => {
      const esp = JSON.parse(readFileSync(join(FIX, arq.replace(/\.[a-z]+$/, ".esperado.json")), "utf8"));
      const r = ok(await ler(arq, bytesDe(join(FIX, arq))));
      expect(r.origem.formato).toBe(formato);
      expect(r.itens).toHaveLength(esp.itens.length);
    });
  }
  it(".ods é recusado com orientação", async () => {
    expect(codigo(await ler("TC-006.ods", bytesDe(join(FIX, "TC-006.ods"))))).toBe("FORMATO_NAO_SUPORTADO");
  });
  it("recusa: planilha vazia, zip truncado e binário com extensão .xls", async () => {
    expect(ehErro(await ler("a.xlsx", new Uint8Array()))).toBe(true);
    const orig = bytesDe(join(FIX, "TC-002.xlsx"));
    expect(ehErro(await ler("a.xlsx", orig.slice(0, Math.floor(orig.length / 3))))).toBe(true);
    expect(ehErro(await ler("a.xls", new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9])))).toBe(true);
  });
});

// ---------------------------------------------------------------- TXT do Revit
describe("TXT tabulado do Revit", () => {
  it("válido: TC-003 confere com o esperado", async () => {
    const esp = JSON.parse(readFileSync(join(FIX, "TC-003.esperado.json"), "utf8"));
    const r = ok(await ler("TC-003.txt", bytesDe(join(FIX, "TC-003.txt"))));
    expect(r.origem.formato).toBe("txt");
    expect(r.itens).toHaveLength(esp.itens.length);
  });
  it("recusa: arquivo vazio", async () => {
    expect(ehErro(await ler("a.txt", new Uint8Array()))).toBe(true);
  });
});

// ---------------------------------------------------------------- PDF
describe("PDF com texto", () => {
  const quadro = join(RAIZ, "docs/arquivos-teste/01-apto-boa-viagem/PR-08 Quadro de acabamentos - Reforma Apartamento Boa Viagem.pdf");
  it.skipIf(!existsSync(quadro))("válido: quadro de acabamentos devolve itens com medida positiva", async () => {
    const r = ok(await ler("quadro.pdf", bytesDe(quadro)));
    expect(r.origem.formato).toBe("pdf");
    expect(r.itens.length).toBeGreaterThan(5);
    expect(r.itens.every((i) => i.quantidade !== null && i.quantidade > 0)).toBe(true);
  });
  it("recusa: vazio e texto com extensão .pdf", async () => {
    expect(ehErro(await ler("a.pdf", new Uint8Array()))).toBe(true);
    expect(ehErro(await ler("a.pdf", texto("isto não é um pdf")))).toBe(true);
  });
  it.skipIf(!existsSync(quadro))("recusa: PDF truncado", async () => {
    expect(ehErro(await ler("a.pdf", bytesDe(quadro).slice(0, 400)))).toBe(true);
  });
});

// ---------------------------------------------------------------- DXF e DWG
describe("DXF e DWG", () => {
  const dxf = (n: string) => bytesDe(join(MODELOS, "casos", n));
  it("válido: apartamento em metros, 9 linhas, tudo conferido", async () => {
    const r = ok(await ler("dxf-01-apto-metros.dxf", dxf("dxf-01-apto-metros.dxf")));
    expect(r.itens.map((i) => [i.descricao, i.quantidade, i.unidade])).toEqual([
      ["Porta", 3, "un"], ["Janela", 2, "un"], ["Ponto elétrico", 6, "un"],
      ["Piso (área)", 20, "m2"], ["Piso (área)", 10.5, "m2"], ["Piso (área)", 5, "m2"],
      ["Parede (comprimento)", 17, "m"], ["Forro (área)", 12, "m2"], ["MOBILIARIO_X (área)", 1, "m2"],
    ]);
  });
  it("sem $INSUNITS: medida pendente e a linha da tela fica com quantidade vazia", async () => {
    const r = ok(await ler("planta-sem-unidade.dxf", bytesDe(join(MODELOS, "planta-sem-unidade.dxf"))));
    expect(r.itens.find((i) => i.descricao === "Piso (área)")!.quantidade).toBeNull();
    const linhas = importacaoParaLinhas(r, () => "x");
    expect(linhas.find((l) => l.descricao === "Piso (área)")!.quantidade).toBe("");
  });
  it("recusa: truncado, vazio e IFC com extensão .dxf", async () => {
    expect(codigo(await ler("a.dxf", dxf("dxf-06-truncado.dxf")))).toBe("ARQUIVO_CORROMPIDO");
    expect(codigo(await ler("a.dxf", new Uint8Array()))).toBe("ARQUIVO_VAZIO");
    expect(ehErro(await ler("a.dxf", bytesDe(join(MODELOS, "ifc/ifc-01-apto-minimo.ifc"))))).toBe(true);
  });
  it("DWG (binário AC10xx) é recusado e orienta salvar como DXF", async () => {
    const r = await ler("planta.dwg", new Uint8Array([0x41, 0x43, 0x31, 0x30, 0x33, 0x32, 0, 0, 0, 0]));
    expect(codigo(r)).toBe("FORMATO_NAO_SUPORTADO");
    expect(ehErro(r) && r.erro.mensagem).toContain("DXF");
  });
});

// ---------------------------------------------------------------- IFC
describe("IFC", () => {
  const ipe = join(RAIZ, "docs/arquivos-teste/casa-ipe-120m2.ifc");
  it.skipIf(!existsSync(ipe))("Casa Ipê (12 × 10 m): 105,48 m² de piso útil, laje e cobertura de 120 m², 7 portas e 7 janelas", async () => {
    const r = ok(await ler("casa-ipe-120m2.ifc", bytesDe(ipe)));
    const pisos = r.itens.filter((i) => /^Piso /.test(i.descricao ?? ""));
    expect(pisos).toHaveLength(7);
    expect(Math.round(pisos.reduce((s, i) => s + (i.quantidade ?? 0), 0) * 100) / 100).toBe(105.48);
    expect(r.itens.find((i) => /^Laje de piso/.test(i.descricao ?? ""))).toMatchObject({ quantidade: 120, unidade: "m2" });
    expect(r.itens.find((i) => /^Cobertura/.test(i.descricao ?? ""))).toMatchObject({ quantidade: 120, unidade: "m2" });
    const soma = (re: RegExp) => r.itens.filter((i) => re.test(i.descricao ?? "")).reduce((s, i) => s + (i.quantidade ?? 0), 0);
    expect(soma(/^Porta /)).toBe(7);
    expect(soma(/^Janela /)).toBe(7);
    expect(r.avisos).toEqual([]);
  });
  const real = join(RAIZ, "1807_EP_AR_v18.ifc");
  it.skipIf(!existsSync(real))("IFC real de 12 MB (Revit): lê em poucos segundos e não quebra", async () => {
    const t0 = Date.now();
    const r = ok(await ler("1807_EP_AR_v18.ifc", bytesDe(real)));
    expect(Date.now() - t0).toBeLessThan(30_000);
    expect(r.itens.length).toBeGreaterThan(50);
    expect(r.itens.every((i) => i.quantidade === null || i.quantidade > 0)).toBe(true);
    // contagem independente feita direto no texto do arquivo (maior camada de pele por elemento; volume somado)
    const soma = (classe: string, un: string) =>
      r.itens.filter((i) => (i.extras.origem_ifc as { classe: string }).classe === classe && i.unidade === un).reduce((s, i) => s + (i.quantidade ?? 0), 0);
    const paredes = r.itens.filter((i) => (i.extras.origem_ifc as { classe: string }).classe === "IFCWALLSTANDARDCASE");
    expect(paredes.every((i) => i.quantidade !== null)).toBe(true);
    expect(soma("IFCWALLSTANDARDCASE", "m2")).toBeGreaterThan(7500);
    expect(soma("IFCWALLSTANDARDCASE", "m2")).toBeLessThan(7600);
    expect(Math.round(soma("IFCBEAM", "m3") * 100) / 100).toBe(1.18);
    expect(Math.round(soma("IFCCOLUMN", "m3") * 100) / 100).toBe(1.49);
    expect(soma("IFCDOOR", "un")).toBe(211);
    expect(soma("IFCWINDOW", "un")).toBe(297);
  }, 60_000);
  it("recusa: vazio, texto qualquer, IFC truncado e IFCZIP", async () => {
    expect(ehErro(await ler("a.ifc", new Uint8Array()))).toBe(true);
    expect(ehErro(await ler("a.ifc", texto("não sou ifc")))).toBe(true);
    const orig = bytesDe(join(MODELOS, "ifc/ifc-01-apto-minimo.ifc"));
    expect(ehErro(await ler("a.ifc", orig.slice(0, 300)))).toBe(true);
    expect(codigo(await ler("a.ifczip", orig))).toBe("FORMATO_NAO_SUPORTADO");
  });
});

// ---------------------------------------------------------------- SKP
describe("SketchUp (SKP)", () => {
  const face: Point3[] = [[0, 0, 0], [32, 0, 0], [32, 0, 80], [0, 0, 80]];
  it("válido: 3 portas e 2 janelas colocadas; definição não inserida não conta", async () => {
    const m = create();
    const porta = m.addComponentDefinition("Porta de madeira", (d) => d.addFace(face));
    const janela = m.addComponentDefinition("Janela de alumínio", (d) => d.addFace(face));
    m.addComponentDefinition("Vaso sanitário não inserido", (d) => d.addFace(face));
    m.addGroup((g) => {
      for (let k = 0; k < 3; k++) g.addInstance(porta, { translation: [k * 40, 0, 0] });
      for (let k = 0; k < 2; k++) g.addInstance(janela, { translation: [k * 40, 50, 0] });
    }, { name: "Térreo" });
    const r = ok(await ler("obra.skp", m.toBytes()));
    const por = Object.fromEntries(r.itens.map((i) => [i.descricao, i.quantidade]));
    expect(por["Porta de madeira"]).toBe(3);
    expect(por["Janela de alumínio"]).toBe(2);
    expect(por["Vaso sanitário não inserido"]).toBeUndefined();
  });
  it("recusa: cabeçalho inválido, vazio e acima de 20 MB", async () => {
    expect(codigo(await ler("a.skp", new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8])))).toBe("FORMATO_INVALIDO");
    expect(ehErro(await ler("a.skp", new Uint8Array()))).toBe(true);
    expect(ehErro(await ler("a.skp", new Uint8Array(21 * 1024 * 1024)))).toBe(true);
  });
});

// ---------------------------------------------------------------- despacho e propriedades gerais
describe("despacho por extensão", () => {
  it.each(["lista.docx", "foto.jpg", "foto.png", "dados.json", "dados.xml", "pagina.html", "notas.md", "semextensao", "arquivo.zip"])(
    "%s é recusado como formato não suportado, citando os aceitos",
    async (nome) => {
      const r = await ler(nome, texto("qualquer coisa"));
      expect(codigo(r)).toBe("FORMATO_NAO_SUPORTADO");
      expect(ehErro(r) && r.erro.mensagem).toMatch(/\.csv.*\.dxf.*\.ifc.*\.skp/);
    },
  );
  it("a extensão não diferencia maiúsculas: .DXF, .CSV e .IFC chegam ao leitor certo", async () => {
    expect(ok(await ler("X.DXF", bytesDe(join(MODELOS, "casos/dxf-03-milimetros.dxf")))).origem.formato).toBe("dxf");
    expect(ok(await ler("X.CSV", texto("Descrição;Quantidade;Unidade\nTinta;2;l\n"))).origem.formato).toBe("csv");
    expect(ok(await ler("X.IFC", bytesDe(join(MODELOS, "ifc/ifc-01-apto-minimo.ifc")))).origem.formato).toBe("ifc");
  });
});

describe("propriedades que valem para qualquer leitor", () => {
  const validos: [string, () => Uint8Array][] = [
    ["TC-001.csv", () => bytesDe(join(FIX, "TC-001.csv"))],
    ["TC-002.xlsx", () => bytesDe(join(FIX, "TC-002.xlsx"))],
    ["TC-003.txt", () => bytesDe(join(FIX, "TC-003.txt"))],
    ["dxf-01.dxf", () => bytesDe(join(MODELOS, "casos/dxf-01-apto-metros.dxf"))],
    ["dxf-02.dxf", () => bytesDe(join(MODELOS, "casos/dxf-02-pes.dxf"))],
    ["ifc-01.ifc", () => bytesDe(join(MODELOS, "ifc/ifc-01-apto-minimo.ifc"))],
    ["ifc-02.ifc", () => bytesDe(join(MODELOS, "ifc/ifc-02-casa-mm-material.ifc"))],
  ];
  for (const [nome, mk] of validos) {
    describe(nome, () => {
      it("é determinístico: duas leituras dão o mesmo resultado", async () => {
        expect(JSON.stringify(await ler(nome, mk()))).toBe(JSON.stringify(await ler(nome, mk())));
      });
      it("não altera os bytes de entrada", async () => {
        const b = mk();
        const copia = b.slice();
        await ler(nome, b);
        expect(Buffer.from(b).equals(Buffer.from(copia))).toBe(true);
      });
      it("contrato dos itens: linha única > 0, descrição, unidade oficial ou vazia, quantidade positiva ou pendente", async () => {
        const r = ok(await ler(nome, mk()));
        expect(r.itens.length).toBeGreaterThan(0);
        const linhas = r.itens.map((i) => i.linha);
        expect(new Set(linhas).size).toBe(linhas.length);
        for (const i of r.itens) {
          expect(i.linha).toBeGreaterThan(0);
          expect((i.descricao ?? "").trim().length).toBeGreaterThan(0);
          if (i.unidade) expect([...UNIDADES, "ft-in"]).toContain(i.unidade);
          if (i.quantidade !== null) expect(i.quantidade).toBeGreaterThan(0);
        }
      });
      it("vira linhas editáveis: mesmo número de itens, ids estáveis e quantidade como texto", async () => {
        const r = ok(await ler(nome, mk()));
        let n = 0;
        const linhas = importacaoParaLinhas(r, () => `id-${n++}`);
        expect(linhas).toHaveLength(r.itens.length);
        expect(linhas.every((l) => typeof l.quantidade === "string")).toBe(true);
        expect(linhas[0].id).toBe("id-0");
      });
    });
  }
});
