// IFC em escala: o leitor pega TODAS as quantidades de cada tipo quando o arquivo cresce?
// Os totais esperados vêm do GERADOR (sabemos quanto colocamos no arquivo), não do leitor.
// A seção "tipos e medidas que antes eram ignorados" cobre lacunas reais achadas no IFC do ArchiCAD de 12 MB e já corrigidas.
import { describe, expect, it } from "vitest";
import { importarIfc } from "./ifc";
import { ehErro, type Importacao } from "./tipos";

type Q = { tipo: "AREA" | "LENGTH" | "VOLUME" | "COUNT" | "WEIGHT"; nome: string; valor: number };
type El = { classe: string; nome: string; pav: number; q?: Q[]; complexa?: boolean };

/** Monta um IFC4 mínimo, válido para o leitor, com os elementos dados. */
function gerar(els: El[], opts: { pavimentos?: number; unidades?: string } = {}): Uint8Array {
  const pavs = opts.pavimentos ?? 3;
  const L: string[] = [];
  let id = 100;
  const novo = () => id++;
  L.push(opts.unidades ?? "#1=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);\n#2=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);");
  const pavIds: number[] = [];
  for (let p = 0; p < pavs; p++) {
    const pid = novo();
    pavIds.push(pid);
    L.push(`#${pid}=IFCBUILDINGSTOREY('P${p}',$,'Pav ${p + 1}',$,$,$,$,$,.ELEMENT.,${p * 3}.);`);
  }
  const porPav: number[][] = pavIds.map(() => []);
  for (const e of els) {
    const eid = novo();
    L.push(`#${eid}=${e.classe}('G${eid}',$,'${e.nome}',$,$,$,$,$);`);
    porPav[e.pav % pavs].push(eid);
    if (e.q?.length) {
      const qids = e.q.map((q) => {
        const qid = novo();
        L.push(`#${qid}=IFCQUANTITY${q.tipo}('${q.nome}',$,$,${q.valor.toFixed(4)},$);`);
        return qid;
      });
      let lista = qids;
      if (e.complexa) {
        const cid = novo();
        L.push(`#${cid}=IFCPHYSICALCOMPLEXQUANTITY('Component 1',$,(${qids.map((x) => "#" + x).join(",")}),'',$,$);`);
        lista = [cid];
      }
      const pset = novo();
      L.push(`#${pset}=IFCELEMENTQUANTITY('Q${pset}',$,'Qto',$,$,(${lista.map((x) => "#" + x).join(",")}));`);
      L.push(`#${novo()}=IFCRELDEFINESBYPROPERTIES('R${id}',$,$,$,(#${eid}),#${pset});`);
    }
  }
  pavIds.forEach((pid, p) => {
    if (porPav[p].length) L.push(`#${novo()}=IFCRELCONTAINEDINSPATIALSTRUCTURE('C${p}',$,$,$,(${porPav[p].map((x) => "#" + x).join(",")}),#${pid});`);
  });
  const txt = `ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n${L.join("\n")}\nENDSEC;\nEND-ISO-10303-21;\n`;
  return new TextEncoder().encode(txt);
}

const ler = (b: Uint8Array): Importacao => {
  const r = importarIfc({ nome: "gerado.ifc", bytes: b });
  if (ehErro(r)) throw new Error(`${r.erro.codigo}: ${r.erro.mensagem}`);
  return r;
};
/** Soma (quantidade) dos itens cuja origem é a classe dada. */
const mesma = (c: string, alvo: string) => c === alvo || (alvo === "IFCWALL" && c === "IFCWALLSTANDARDCASE");
const somaClasse = (r: Importacao, classe: string) =>
  r.itens.filter((i) => mesma((i.extras.origem_ifc as { classe: string }).classe, classe)).reduce((s, i) => s + (i.quantidade ?? 0), 0);
const elementosClasse = (r: Importacao, classe: string) =>
  r.itens.filter((i) => mesma((i.extras.origem_ifc as { classe: string }).classe, classe)).reduce((s, i) => s + (i.extras.origem_ifc as { elementos: number }).elementos, 0);
const arred = (n: number) => Math.round(n * 100) / 100;

describe("IFC em escala: nenhum elemento e nenhuma quantidade se perde", () => {
  for (const N of [1, 50, 5_000, 15_000]) {
    it(`${N} de cada tipo, em 3 pavimentos: totais exatos`, () => {
      const els: El[] = [];
      for (let i = 0; i < N; i++) {
        els.push({ classe: "IFCDOOR", nome: "Porta 80", pav: i });
        els.push({ classe: "IFCWINDOW", nome: "Janela 120", pav: i });
        els.push({ classe: "IFCWALLSTANDARDCASE", nome: "Parede 15", pav: i, q: [{ tipo: "AREA", nome: "NetSideArea", valor: 3.5 }] });
        els.push({ classe: "IFCSPACE", nome: `Amb ${i}`, pav: i, q: [{ tipo: "AREA", nome: "NetFloorArea", valor: 10.25 }] });
        els.push({ classe: "IFCSLAB", nome: "Laje", pav: i, q: [{ tipo: "AREA", nome: "NetArea", valor: 2 }] });
        els.push({ classe: "IFCRAILING", nome: "Guarda-corpo", pav: i, q: [{ tipo: "LENGTH", nome: "Length", valor: 1.5 }] });
        els.push({ classe: "IFCSANITARYTERMINAL", nome: "Vaso", pav: i });
        els.push({ classe: "IFCLIGHTFIXTURE", nome: "Plafon", pav: i });
      }
      const t0 = Date.now();
      const r = ler(gerar(els));
      expect(Date.now() - t0).toBeLessThan(60_000);
      // contagens (un): cada elemento aparece uma vez em algum grupo
      expect(somaClasse(r, "IFCDOOR")).toBe(N);
      expect(somaClasse(r, "IFCWINDOW")).toBe(N);
      expect(somaClasse(r, "IFCSANITARYTERMINAL")).toBe(N);
      expect(somaClasse(r, "IFCLIGHTFIXTURE")).toBe(N);
      // medidas: somam o que foi declarado
      expect(arred(somaClasse(r, "IFCWALL"))).toBe(arred(3.5 * N));
      expect(arred(somaClasse(r, "IFCSPACE"))).toBe(arred(10.25 * N));
      expect(arred(somaClasse(r, "IFCSLAB"))).toBe(arred(2 * N));
      expect(arred(somaClasse(r, "IFCRAILING"))).toBe(arred(1.5 * N));
      // nenhum elemento ficou de fora dos grupos
      for (const c of ["IFCDOOR", "IFCWINDOW", "IFCWALL", "IFCSPACE", "IFCSLAB", "IFCRAILING"]) expect(elementosClasse(r, c)).toBe(N);
      // sem aviso de quantidade ausente: todas as medidas foram lidas
      expect(r.avisos).toEqual([]);
      // 3 pavimentos x (porta, janela, parede, laje, guarda-corpo, vaso, plafon) + 1 espaço por nome
      expect(new Set(r.itens.map((i) => i.nivel))).toEqual(new Set(["Pav 1", "Pav 2", "Pav 3"].slice(0, Math.min(N, 3))));
    }, 120_000);
  }

  it("nomes únicos por elemento (como o Revit exporta): 20 mil grupos, nada some", () => {
    const els: El[] = Array.from({ length: 20_000 }, (_, i) => ({
      classe: "IFCWALL", nome: `Parede básica:Genérica 200mm:${100000 + i}`, pav: 0, q: [{ tipo: "AREA" as const, nome: "NetSideArea", valor: 1 }],
    }));
    const r = ler(gerar(els));
    expect(r.itens).toHaveLength(20_000);
    expect(arred(somaClasse(r, "IFCWALL"))).toBe(20_000);
  }, 120_000);

  it("arquivo de milhões de linhas de geometria misturadas não confunde as entidades de interesse", () => {
    const els: El[] = [{ classe: "IFCDOOR", nome: "Porta 90", pav: 0 }];
    const base = new TextDecoder().decode(gerar(els));
    const lixo = Array.from({ length: 300_000 }, (_, i) => `#${900000 + i}=IFCCARTESIANPOINT((${i}.,${i}.,0.));`).join("\n");
    const b = new TextEncoder().encode(base.replace("DATA;", `DATA;\n${lixo}`));
    const t0 = Date.now();
    const r = ler(b);
    expect(Date.now() - t0).toBeLessThan(30_000);
    expect(somaClasse(r, "IFCDOOR")).toBe(1);
  }, 60_000);
});

describe("IFC: quantidades por tipo de medida e de unidade", () => {
  it("área em milímetros declarados: comprimento em mm vira metros, área em m² não é escalada", () => {
    const unidades = "#1=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);\n#2=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);";
    const r = ler(gerar([
      { classe: "IFCRAILING", nome: "Guarda-corpo", pav: 0, q: [{ tipo: "LENGTH", nome: "Length", valor: 4200 }] },
      { classe: "IFCSLAB", nome: "Laje", pav: 0, q: [{ tipo: "AREA", nome: "NetArea", valor: 25 }] },
    ], { unidades }));
    expect(somaClasse(r, "IFCRAILING")).toBe(4.2);
    expect(somaClasse(r, "IFCSLAB")).toBe(25);
  });

  it("parede sem NetSideArea usa GrossSideArea; sem nenhuma, entra pendente com aviso", () => {
    const r = ler(gerar([
      { classe: "IFCWALL", nome: "Só bruta", pav: 0, q: [{ tipo: "AREA", nome: "GrossSideArea", valor: 12 }] },
      { classe: "IFCWALL", nome: "Sem medida", pav: 0 },
    ]));
    expect(r.itens.find((i) => i.descricao?.startsWith("Só bruta"))?.quantidade).toBe(12);
    expect(r.itens.find((i) => i.descricao?.startsWith("Sem medida"))?.quantidade).toBeNull();
    expect(r.avisos.some((a) => a.codigo === "QUANTIDADE_AUSENTE")).toBe(true);
  });

  it("grupo misto: soma o que foi declarado e avisa que a soma pode estar baixa", () => {
    const r = ler(gerar([
      { classe: "IFCWALL", nome: "Parede", pav: 0, q: [{ tipo: "AREA", nome: "NetSideArea", valor: 10 }] },
      { classe: "IFCWALL", nome: "Parede", pav: 0 },
    ]));
    expect(r.itens[0].quantidade).toBe(10);
    expect(r.avisos[0].mensagem).toContain("1 de 2");
  });
});

describe("IFC: tipos e medidas que antes eram ignorados (ArchiCAD, volume, pés, estrutura)", () => {
  it("quantidade dentro de IfcPhysicalComplexQuantity (ArchiCAD) deveria ser lida", () => {
    const r = ler(gerar([
      { classe: "IFCWALLSTANDARDCASE", nome: "Parede ArchiCAD", pav: 0, complexa: true, q: [{ tipo: "AREA", nome: "Projected Component/Skin Area", valor: 6.7 }] },
    ]));
    expect(r.itens[0].quantidade).not.toBeNull();
  });

  it("vigas (IfcBeam) com volume declarado deveriam virar item em m3", () => {
    const r = ler(gerar([{ classe: "IFCBEAM", nome: "Viga V1", pav: 0, q: [{ tipo: "VOLUME", nome: "NetVolume", valor: 0.8 }] }]));
    expect(r.itens).toHaveLength(1);
    expect(r.itens[0]).toMatchObject({ quantidade: 0.8, unidade: "m3" });
  });

  it("pilares (IfcColumn) deveriam virar item", () => {
    const r = ler(gerar([{ classe: "IFCCOLUMN", nome: "Pilar P1", pav: 0, q: [{ tipo: "VOLUME", nome: "NetVolume", valor: 0.4 }] }]));
    expect(r.itens).toHaveLength(1);
  });

  it("escadas (IfcStair, IfcStairFlight) e rampas (IfcRamp) deveriam virar item", () => {
    const r = ler(gerar([
      { classe: "IFCSTAIRFLIGHT", nome: "Lance", pav: 0 },
      { classe: "IFCRAMP", nome: "Rampa", pav: 0 },
    ]));
    expect(r.itens.length).toBe(2);
  });

  it("elementos genéricos (IfcBuildingElementProxy) deveriam ser contados", () => {
    const r = ler(gerar([{ classe: "IFCBUILDINGELEMENTPROXY", nome: "Elemento genérico", pav: 0 }]));
    expect(r.itens).toHaveLength(1);
  });

  it("comprimento em pés (IfcConversionBasedUnit) deveria ser convertido para metros", () => {
    const unidades = [
      "#1=IFCDIMENSIONALEXPONENTS(1,0,0,0,0,0,0);",
      "#3=IFCMEASUREWITHUNIT(IFCLENGTHMEASURE(0.3048),#4);",
      "#4=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);",
      "#5=IFCCONVERSIONBASEDUNIT(#1,.LENGTHUNIT.,'FOOT',#3);",
      "#2=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);",
    ].join("\n");
    const r = ler(gerar([{ classe: "IFCRAILING", nome: "Guarda-corpo", pav: 0, q: [{ tipo: "LENGTH", nome: "Length", valor: 10 }] }], { unidades }));
    expect(arred(r.itens[0].quantidade ?? 0)).toBe(3.05);
  });

  it("parede só com 'Length' e 'Height' declarados (sem área) deveria ter área calculada ou aviso específico", () => {
    const r = ler(gerar([
      { classe: "IFCWALL", nome: "Parede sem área", pav: 0, q: [{ tipo: "LENGTH", nome: "Length", valor: 5 }, { tipo: "LENGTH", nome: "Height", valor: 2.8 }] },
    ]));
    expect(r.itens[0].quantidade).toBe(14);
  });
});

describe("IFC corrompido não trava o navegador", () => {
  it.each([
    ["enum sem ponto final", "#9=IFCCONVERSIONBASEDUNIT(#1,.LENGTHUNIT,'FOOT',#3);"],
    ["binário sem aspas de fechamento", "#9=IFCPROPERTYSINGLEVALUE(\"ABC"],
    ["texto sem aspas de fechamento", "#9=IFCDOOR('G',$,'Porta sem fim,$);"],
    ["parênteses desbalanceados", "#9=IFCDOOR(((('G',$,'P';"],
  ])("%s: termina rápido, com resultado ou erro", (_n, linha) => {
    const txt = ["ISO-10303-21;", "HEADER;", "FILE_SCHEMA(('IFC4'));", "ENDSEC;", "DATA;", "#1=IFCDOOR('G1',$,'Porta 80',$,$,$,$,$);", linha, "ENDSEC;", "END-ISO-10303-21;", ""].join("\n");
    const t0 = Date.now();
    const r = importarIfc({ nome: "c.ifc", bytes: new TextEncoder().encode(txt) });
    expect(Date.now() - t0).toBeLessThan(2000);
    expect(r).toBeDefined();
  });
});

describe("IFC: camadas do ArchiCAD e volumes", () => {
  it("parede com 2 camadas: área = maior camada (não soma), e avisa uma vez", () => {
    const a = (v: number): Q => ({ tipo: "AREA", nome: "Projected Component/Skin Area", valor: v });
    const r = ler(gerar([
      { classe: "IFCWALLSTANDARDCASE", nome: "Parede A", pav: 0, complexa: true, q: [a(10), a(9.5)] },
    ]));
    expect(r.itens[0].quantidade).toBe(10);
    expect(r.avisos.filter((x) => x.linha === null)).toHaveLength(1);
  });
  it("viga com 2 componentes: volumes somam", () => {
    const v = (x: number): Q => ({ tipo: "VOLUME", nome: "Skin/Component Volume", valor: x });
    const r = ler(gerar([{ classe: "IFCBEAM", nome: "Viga", pav: 0, complexa: true, q: [v(0.5), v(0.25)] }]));
    expect(r.itens[0]).toMatchObject({ quantidade: 0.75, unidade: "m3" });
  });
  it("lance de escada só com volume vira m3; rampa com área vira m2", () => {
    const r = ler(gerar([
      { classe: "IFCSTAIRFLIGHT", nome: "Lance", pav: 0, q: [{ tipo: "VOLUME", nome: "NetVolume", valor: 1.2 }] },
      { classe: "IFCRAMP", nome: "Rampa", pav: 0, q: [{ tipo: "AREA", nome: "NetArea", valor: 6 }] },
    ]));
    expect(r.itens.map((i) => [i.quantidade, i.unidade])).toEqual([[1.2, "m3"], [6, "m2"]]);
  });
  it("mesmo nome, uma com área e outra só com volume: viram grupos separados, nenhum perde a medida", () => {
    const r = ler(gerar([
      { classe: "IFCSTAIRFLIGHT", nome: "Lance", pav: 0, q: [{ tipo: "AREA", nome: "NetArea", valor: 4 }] },
      { classe: "IFCSTAIRFLIGHT", nome: "Lance", pav: 0, q: [{ tipo: "VOLUME", nome: "NetVolume", valor: 0.9 }] },
    ]));
    expect(r.itens.map((i) => [i.quantidade, i.unidade]).sort()).toEqual([[0.9, "m3"], [4, "m2"]].sort());
  });
});
