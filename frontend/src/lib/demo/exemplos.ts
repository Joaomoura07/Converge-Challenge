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
  { modo: "ifc", rotulo: "Modelo IFC (BIM)" },
  { modo: "skp", rotulo: "SketchUp (SKP)" },
];

export const EXEMPLOS_DEMO: ExemploDemo[] = [
  { arquivo: "teste_1.csv", modo: "csv", obra: "Pintura de fachada, Madalena" },
  { arquivo: "teste_2.csv", modo: "csv", obra: "Banheiro social, Casa Forte (SketchUp)" },
  { arquivo: "teste_1.xlsx", modo: "excel", obra: "Escritório corporativo, Ilha do Leite" },
  { arquivo: "teste_2.xlsx", modo: "excel", obra: "Restaurante, Recife Antigo" },
  // Tabela agregada (louças por contagem). A de louças do apto Boa Viagem listava as mesmas peças em 2 banheiros e
  // o revisor apontava 5 "duplicados" falsos (a lista do site não guarda o ambiente): trocada em 08/11.
  { arquivo: "teste_1.txt", modo: "revit", obra: "Louças e metais, casa térrea em Aldeia" },
  { arquivo: "teste_2.txt", modo: "revit", obra: "Elétrica, casa térrea em Aldeia" },
  { arquivo: "teste_1.pdf", modo: "pdf", obra: "Pedido de cotação, fachada Madalena" },
  { arquivo: "teste_2.pdf", modo: "pdf", obra: "Quadro de acabamentos, escritório" },
  { arquivo: "teste_1.dxf", modo: "dxf", obra: "Planta baixa simples (cm)" },
  { arquivo: "teste_2.dxf", modo: "dxf", obra: "Planta exportada do AutoCAD" },
  { arquivo: "teste_1.ifc", modo: "ifc", obra: "Apartamento mínimo (IFC4)" },
  { arquivo: "teste_2.ifc", modo: "ifc", obra: "Casa com materiais (IFC4, mm)" },
  { arquivo: "teste_1.skp", modo: "skp", obra: "Banheiro social (SketchUp)" },
  { arquivo: "teste_2.skp", modo: "skp", obra: "Escritório, Ilha do Leite (SketchUp)" },
];

/** Um MODELO por formato: o arquivo-padrão que mostra ao usuário como montar a lista para enviar ao sistema.
 *  Aparece destacado, antes dos testes. CSV, Excel, TXT e PDF trazem uma lista genérica de 5 materiais; o DXF é a planta simples do teste_1. */
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
