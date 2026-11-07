// Leitor do TXT tabulado exportado pelo Revit (etapa 10; decisão D1: .txt aceito como texto delimitado por tabulação).
// Reaproveita o núcleo do CSV com a tabulação FORÇADA: a detecção automática erra em "12,50 m²" (vírgula decimal).
// O que é específico do Revit (linha de grupo "Nível: Térreo", subtotais, "Total geral" conferido pela soma,
// medidas em pés e polegadas) está em `mapearRegistros` e vale também para CSV e Excel com o mesmo desenho.

import { importarCsv } from "./csv";
import type { ResultadoImportacao } from "./tipos";

export function importarTxt({ nome, bytes }: { nome: string; bytes: Uint8Array }): ResultadoImportacao {
  const r = importarCsv({ nome, bytes, forcarDelimitador: "\t", formato: "txt" });
  if ("erro" in r && r.erro.codigo === "CABECALHO_NAO_ENCONTRADO") {
    return {
      erro: {
        ...r.erro,
        mensagem:
          "Este .txt não parece uma tabela do Revit (colunas separadas por tabulação, com descrição e quantidade). " +
          "Exporte a tabela do Revit de novo ou salve a lista como .csv.",
      },
    };
  }
  return r;
}
