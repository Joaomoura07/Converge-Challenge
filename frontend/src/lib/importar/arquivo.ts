// Ponto único de leitura de arquivos: escolhe o leitor pela extensão. Uploads e exemplos passam por aqui.

import { importarCsv } from "./csv";
import { importarExcel, type AbaInfo } from "./excel";
import { importarPdf, type PdfjsMinimo } from "./pdf";
import { importarTxt } from "./txt";
import type { ErroImportacao, Importacao, ResultadoImportacao } from "./tipos";

export type ResultadoArquivo = ResultadoImportacao & { abas?: AbaInfo[] };

const erro = (codigo: ErroImportacao["erro"]["codigo"], mensagem: string): ErroImportacao => ({ erro: { codigo, mensagem } });

export async function lerArquivo({
  nome,
  bytes,
  aba,
  pdfjs,
}: {
  nome: string;
  bytes: Uint8Array;
  aba?: string | null;
  /** PDF.js já carregado (testes); na tela ele é carregado sob demanda, só quando o arquivo é PDF. */
  pdfjs?: PdfjsMinimo;
}): Promise<ResultadoArquivo> {
  const ext = nome.toLowerCase().match(/\.([a-z0-9]+)$/)?.[1] ?? "";
  if (ext === "csv") return importarCsv({ nome, bytes });
  if (["xlsx", "xls", "xlsm", "ods"].includes(ext)) return importarExcel({ nome, bytes, aba });
  if (ext === "txt") return importarTxt({ nome, bytes }); // tabela tabulada do Revit
  if (ext === "pdf") {
    const motor = pdfjs ?? (await (await import("./pdfNavegador")).carregarPdfjs());
    return importarPdf({ nome, bytes, pdfjs: motor });
  }
  return erro("FORMATO_NAO_SUPORTADO", `Formato .${ext || "desconhecido"} não suportado. Use .csv, .xlsx, .xls, .txt do Revit ou .pdf com texto.`);
}

/** Abas que a pessoa poderia escolher: visíveis e com dados. */
export function abasEscolhaveis(r: ResultadoArquivo): AbaInfo[] {
  return (r as { abas?: AbaInfo[] }).abas?.filter((a) => !a.oculta && a.temDados) ?? [];
}

export type { Importacao };
