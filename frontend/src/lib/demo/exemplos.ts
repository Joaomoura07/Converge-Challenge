// Arquivos de exemplo da página /demo: 2 por formato, para o jurado baixar e arrastar para dentro como um arquiteto
// faria. São casos sintéticos de 3 a 5 itens, gerados por scripts/gerar_demo_jurados.py e gerar_demo_skp.mjs.
// Teste 1: materiais especificados. Teste 2: revisão, complementos e dados que precisam do arquiteto.
// Os resultados de pesquisa dependem das fontes disponíveis; os exemplos não contêm preços prontos.
// Para acrescentar um formato (ex.: IFC), basta incluir aqui e pôr os arquivos em public/exemplos/demo/.

import type { ModoEntrada } from "@/lib/lista";

export type FormatoDemo = { modo: Exclude<ModoEntrada, "manual">; rotulo: string };
export type ExemploDemo = { arquivo: string; modo: FormatoDemo["modo"]; obra: string };

export const PASTA_DEMO = "/exemplos/demo";

export const FORMATOS_DEMO: FormatoDemo[] = [
  { modo: "csv", rotulo: "CSV" },
  { modo: "excel", rotulo: "Excel" },
  { modo: "revit", rotulo: "TXT do Revit" },
  { modo: "pdf", rotulo: "PDF com texto" },
  { modo: "dxf", rotulo: "Planta DXF" },
  { modo: "ifc", rotulo: "Modelo IFC (BIM)" },
  { modo: "skp", rotulo: "SketchUp (SKP)" },
];

export const EXEMPLOS_DEMO: ExemploDemo[] = [
  ...FORMATOS_DEMO.flatMap(({ modo }) => {
    const ext = modo === "excel" ? "xlsx" : modo === "revit" ? "txt" : modo;
    return [
      { arquivo: `teste_1.${ext}`, modo, obra: "Pesquisa de materiais especificados — Boa Viagem" },
      { arquivo: `teste_2.${ext}`, modo, obra: "Revisão e especificação de uma reforma — Casa Forte" },
    ];
  }),
];

/** Um MODELO por formato: o arquivo-padrão que mostra ao usuário como montar a lista para enviar ao sistema.
 *  Tabelas e IFC têm cinco materiais genéricos; DXF mostra áreas/contagens e SKP mostra componentes de compra. */
export const MODELOS_DEMO: ExemploDemo[] = [
  { arquivo: "MODELO.csv", modo: "csv", obra: "Modelo de lista em CSV" },
  { arquivo: "MODELO.xlsx", modo: "excel", obra: "Modelo de lista em Excel" },
  { arquivo: "MODELO.txt", modo: "revit", obra: "Modelo de tabela exportada do Revit" },
  { arquivo: "MODELO.pdf", modo: "pdf", obra: "Modelo de lista em PDF com texto" },
  { arquivo: "MODELO.dxf", modo: "dxf", obra: "Modelo de planta DXF" },
  { arquivo: "MODELO.ifc", modo: "ifc", obra: "Modelo de projeto BIM em IFC" },
  { arquivo: "MODELO.skp", modo: "skp", obra: "Modelo de projeto SketchUp" },
];

const MODO_POR_EXTENSAO: Record<string, FormatoDemo["modo"]> = {
  csv: "csv", xlsx: "excel", xls: "excel", xlsm: "excel", txt: "revit", pdf: "pdf", dxf: "dxf", dwg: "dxf",
  ifc: "ifc", ifczip: "ifc", skp: "skp",
};

/** Aba que corresponde ao arquivo (o leitor já escolhe pela extensão; a aba só acompanha para o texto de ajuda). */
export function modoPeloArquivo(nome: string): FormatoDemo["modo"] | null {
  const ext = nome.toLowerCase().split(".").pop() ?? "";
  return MODO_POR_EXTENSAO[ext] ?? null;
}
