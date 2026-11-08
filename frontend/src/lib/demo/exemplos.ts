// Arquivos de exemplo da página /demo: 2 por formato, para o jurado baixar e arrastar para dentro como um arquiteto
// faria. Todos são obras sintéticas do acervo (docs/arquivos-teste e tests/importacao/fixtures/modelos), curtos
// (3 a 13 itens) para a pesquisa terminar rápido. Os .xlsx foram gerados com o SheetJS a partir de 2 CSV do acervo.
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
];

export const EXEMPLOS_DEMO: ExemploDemo[] = [
  { arquivo: "teste_1.csv", modo: "csv", obra: "Pintura de fachada, Madalena" },
  { arquivo: "teste_2.csv", modo: "csv", obra: "Banheiro social, Casa Forte (SketchUp)" },
  { arquivo: "teste_1.xlsx", modo: "excel", obra: "Escritório corporativo, Ilha do Leite" },
  { arquivo: "teste_2.xlsx", modo: "excel", obra: "Restaurante, Recife Antigo" },
  { arquivo: "teste_1.txt", modo: "revit", obra: "Louças e metais, apto Boa Viagem" },
  { arquivo: "teste_2.txt", modo: "revit", obra: "Elétrica, casa térrea em Aldeia" },
  { arquivo: "teste_1.pdf", modo: "pdf", obra: "Pedido de cotação, fachada Madalena" },
  { arquivo: "teste_2.pdf", modo: "pdf", obra: "Quadro de acabamentos, escritório" },
  { arquivo: "teste_1.dxf", modo: "dxf", obra: "Planta baixa simples (cm)" },
  { arquivo: "teste_2.dxf", modo: "dxf", obra: "Planta exportada do AutoCAD" },
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
