import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { create } from "openskp";
import * as pdfjsLegacy from "pdfjs-dist/legacy/build/pdf.mjs";
import { describe, expect, it } from "vitest";
import { montarCorpo } from "../envio/corpo";
import { reduzir, estadoInicial } from "../lista";
import { lerArquivo } from "./arquivo";
import { importacaoParaLinhas } from "./paraLinhas";
import { ehErro, type Importacao } from "./tipos";
import type { PdfjsMinimo } from "./pdf";

const DIR = join(__dirname, "../../../../tests/importacao/fixtures/fluxo-curto");
const pdfjs = pdfjsLegacy as unknown as PdfjsMinimo;
const obra = { nome: "Teste sintético de importação", cep: "51020000", orcamentoCliente: 10000 };
const orcamentoId = "11111111-1111-4111-8111-111111111111";
async function ler(nome: string, bytes: Uint8Array = new Uint8Array(readFileSync(join(DIR, nome)))): Promise<Importacao> {
  const r = await lerArquivo({ nome, bytes, pdfjs });
  if (ehErro(r)) throw new Error(r.erro.mensagem);
  expect(r.itens.length).toBeLessThanOrEqual(10);
  return r;
}
const linhasDe = (r: Importacao) => { let id = 0; return importacaoParaLinhas(r, () => `item-${++id}`); };

describe("PDF, DXF, IFC e SKP: lotes de até 10 itens", () => {
  it("PDF reúne fragmentos da mesma célula sem perder material nem quantidade", async () => {
    const r = await ler("quadro-fragmentado.pdf");
    expect(r.itens).toMatchObject([
      { descricao: "Porcelanato", quantidade: 12.5, unidade: "m2", nivel: "Sala" },
      { descricao: "Tinta", quantidade: 20, unidade: "m2" },
    ]);
  });
  it("PDF mantém um material sem quantidade como linha pendente, sem juntá-lo ao anterior", async () => {
    const r = await ler("tabela-quantidade-ausente.pdf");
    expect(r.itens).toMatchObject([
      { descricao: "Cimento CP II", quantidade: 2 },
      { descricao: "Areia lavada", quantidade: null, unidade: "m3" },
      { descricao: "Rejunte branco", quantidade: 3 },
    ]);
    expect(montarCorpo({ orcamentoId, obra, linhas: linhasDe(r), modo: "pdf" })).toBeNull();
  });
  it("DXF mede arcos de polilinhas: semicírculo com raio 1 tem comprimento pi e área pi/2", async () => {
    const r = await ler("curvas.dxf");
    expect(r.itens).toMatchObject([{ quantidade: 3.14, unidade: "m" }, { quantidade: 1.57, unidade: "m2" }]);
  });
  it("IFC respeita a unidade explícita da quantidade, diferente da unidade do projeto", async () => {
    expect((await ler("unidade-local.ifc")).itens).toMatchObject([{ quantidade: 12.5, unidade: "m2" }]);
  });
  it.each(["0.", "-2.", "1.E999"])("IFC deixa quantidade %s pendente", async valor => {
    const conteudo = readFileSync(join(DIR, "unidade-local.ifc"), "utf8").replace("12500000.", valor);
    const r = await ler("invalido.ifc", new TextEncoder().encode(conteudo));
    expect(r.itens[0].quantidade).toBeNull();
    expect(r.avisos.some(a => a.codigo === "QUANTIDADE_AUSENTE")).toBe(true);
  });
  it("IFC converte quantidade em pés quadrados sem afetar a unidade do projeto", async () => {
    const conteudo = readFileSync(join(DIR, "unidade-local.ifc"), "utf8")
      .replace("#2=IFCSIUNIT(*,.AREAUNIT.,.MILLI.,.SQUARE_METRE.);", "#2=IFCCONVERSIONBASEDUNIT($,.AREAUNIT.,'square foot',#4);\n#4=IFCMEASUREWITHUNIT(IFCAREAMEASURE(0.09290304),#1);")
      .replace("12500000.", "100.");
    expect((await ler("pes.ifc", new TextEncoder().encode(conteudo))).itens[0].quantidade).toBe(9.29);
  });
  it.each(["#999", "#3"])("IFC não inventa a conversão de unidade inválida %s", async ref => {
    const conteudo = readFileSync(join(DIR, "unidade-local.ifc"), "utf8").replace("'NetArea',$,#2", `'NetArea',$,${ref}`);
    expect((await ler("unidade-invalida.ifc", new TextEncoder().encode(conteudo))).itens[0].quantidade).toBeNull();
  });
  it("IFC respeita também a unidade local da propriedade de área", async () => {
    const conteudo = readFileSync(join(DIR, "unidade-local.ifc"), "utf8")
      .replace("IFCQUANTITYAREA('NetArea',$,#2,12500000.,$)", "IFCPROPERTYSINGLEVALUE('NetArea',$,IFCAREAMEASURE(12500000.),#2)")
      .replace("IFCELEMENTQUANTITY('qto',$,'Qto_SlabBaseQuantities',$,$,(#11))", "IFCPROPERTYSET('qto',$,'Dados',$,(#11))");
    expect((await ler("propriedade.ifc", new TextEncoder().encode(conteudo))).itens[0].quantidade).toBe(12.5);
  });
  it("DXF respeita arcos no sentido horário e círculos com dois vértices", async () => {
    const conteudo = readFileSync(join(DIR, "curvas.dxf"), "utf8").replaceAll("\r\n", "\n").replaceAll("42\n1\n", "42\n-1\n");
    expect((await ler("horario.dxf", new TextEncoder().encode(conteudo))).itens.map(i => i.quantidade)).toEqual([3.14, 1.57]);
    const circulo = conteudo.replace("90\n3\n70\n1", "90\n2\n70\n1").replace("10\n2\n20\n0\n10\n0\n20\n0\n0\nENDSEC", "10\n2\n20\n0\n42\n-1\n0\nENDSEC");
    expect((await ler("circulo.dxf", new TextEncoder().encode(circulo))).itens[1].quantidade).toBe(3.14);
  });
  it.each(["dxf", "ifc"])(".%s recusa mais de 20 MB antes de decodificar", async ext => {
    expect(await lerArquivo({ nome: `grande.${ext}`, bytes: new Uint8Array(20 * 1024 * 1024 + 1) })).toMatchObject({ erro: { codigo: "ARQUIVO_GRANDE_DEMAIS" } });
  });
  it("PDF com página ilegível devolve erro, sem aceitar um documento parcial", async () => {
    const motor: PdfjsMinimo = { getDocument: () => ({ promise: Promise.resolve({ numPages: 1, getPage: async () => { throw new Error("página corrompida"); } }) }) };
    expect(await lerArquivo({ nome: "pagina.pdf", bytes: new TextEncoder().encode("%PDF-1.7"), pdfjs: motor })).toMatchObject({ erro: { codigo: "ARQUIVO_CORROMPIDO" } });
  });
  it("SKP conta portas, mas cobertura precisa de medida revisada", async () => {
    const m = create();
    const porta = m.addComponentDefinition("Porta de madeira", d => d.addFace([[0,0,0],[30,0,0],[30,0,80],[0,0,80]]));
    const cobertura = m.addComponentDefinition("Cobertura cerâmica", d => d.addFace([[0,0,0],[100,0,0],[100,100,0],[0,100,0]]));
    m.addInstance(porta); m.addInstance(porta, { translation: [40,0,0] }); m.addInstance(cobertura);
    const bytes = m.toBytes();
    if (process.env.UPDATE_FLOW_FIXTURES) writeFileSync(join(DIR, "componentes.skp"), bytes);
    const r = await ler("componentes.skp", bytes);
    expect(r.itens).toMatchObject([{ quantidade: 2, unidade: "un" }, { quantidade: null, unidade: null }]);
  });
  it.each(["quadro-fragmentado.pdf", "curvas.dxf", "unidade-local.ifc", "componentes.skp"])(
    "%s: edição chega ao POST com origem preservada; erro não apaga lista", async nome => {
      const r = await ler(nome);
      const linhas = linhasDe(r);
      // A revisão humana define especificação/unidade e a quantidade, inclusive as pendências.
      let lista = reduzir(estadoInicial, { tipo: "importar", linhas, como: "substituir" });
      for (const l of linhas) {
        lista = reduzir(lista, { tipo: "editar", id: l.id, campo: "quantidade", valor: l.unidade === "un" ? "3" : "7,5" });
        lista = reduzir(lista, { tipo: "editar", id: l.id, campo: "unidade", valor: l.unidade || "m2" });
      }
      const antes = JSON.stringify(lista);
      expect(ehErro(await lerArquivo({ nome, bytes: new Uint8Array([1,2,3]), pdfjs }))).toBe(true);
      expect(JSON.stringify(lista)).toBe(antes);
      const corpo = montarCorpo({ orcamentoId, obra, linhas: lista.linhas, modo: r.origem.formato });
      expect(corpo?.itens.every(i => i.quantidade === (i.unidade === "un" ? 3 : 7.5))).toBe(true);
      expect(corpo?.itens[0]).toMatchObject({ descricao_original: r.itens[0].descricao, nivel: r.itens[0].nivel, extras: r.itens[0].extras });
      // Usado também pelo teste de integração da API (nenhuma chamada à internet).
      if (process.env.UPDATE_FLOW_FIXTURES) writeFileSync(join(DIR, `${r.origem.formato}-envio.json`), JSON.stringify(corpo, null, 2));
      else expect(corpo).toEqual(JSON.parse(readFileSync(join(DIR, `${r.origem.formato}-envio.json`), "utf8")));
    },
  );
});
