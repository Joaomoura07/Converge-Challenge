// Ponto único de leitura de arquivos: escolhe o leitor pela extensão. Uploads e exemplos passam por aqui.
// A etapa 11 acrescenta o PDF com texto.

import { importarCsv } from "./csv";
import { importarExcel, type AbaInfo } from "./excel";
import { importarTxt } from "./txt";
import type { ErroImportacao, Importacao, ResultadoImportacao } from "./tipos";

export type ResultadoArquivo = ResultadoImportacao & { abas?: AbaInfo[] };

const erro = (codigo: ErroImportacao["erro"]["codigo"], mensagem: string): ErroImportacao => ({ erro: { codigo, mensagem } });

export function lerArquivo({ nome, bytes, aba }: { nome: string; bytes: Uint8Array; aba?: string | null }): ResultadoArquivo {
  const ext = nome.toLowerCase().match(/\.([a-z0-9]+)$/)?.[1] ?? "";
  if (ext === "csv") return importarCsv({ nome, bytes });
  if (["xlsx", "xls", "xlsm", "ods"].includes(ext)) return importarExcel({ nome, bytes, aba });
  if (ext === "txt") return importarTxt({ nome, bytes }); // tabela tabulada do Revit
  if (ext === "pdf") return erro("FORMATO_NAO_SUPORTADO", "PDF com texto entra na etapa 11. Por ora, use .csv, .xlsx ou .txt do Revit.");
  return erro("FORMATO_NAO_SUPORTADO", `Formato .${ext || "desconhecido"} não suportado. Use .csv, .xlsx, .xls ou .txt do Revit.`);
}

/** Abas que a pessoa poderia escolher: visíveis e com dados. */
export function abasEscolhaveis(r: ResultadoArquivo): AbaInfo[] {
  return (r as { abas?: AbaInfo[] }).abas?.filter((a) => !a.oculta && a.temDados) ?? [];
}

export type { Importacao };
