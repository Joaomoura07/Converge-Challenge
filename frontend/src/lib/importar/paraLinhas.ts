// Converte o contrato da importação (Importacao) nas linhas da lista única de revisão.
// Todo importador passa por aqui: o texto fica editável e a linha de origem é preservada.

import type { Linha } from "../lista";
import type { Importacao } from "./tipos";

/** 12.5 → "12,5". O número só volta a ser número quando a lista é validada. */
export function quantidadeParaTexto(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return "";
  return String(n).replace(".", ",");
}

export function importacaoParaLinhas(imp: Importacao, novoId: () => string): Linha[] {
  return imp.itens.map((it) => ({
    id: novoId(),
    descricao: it.descricao ?? "",
    quantidade: quantidadeParaTexto(it.quantidade),
    unidade: it.unidade ?? "",
    categoria: it.categoria ?? "",
    linhaOrigem: it.linha,
    descricaoOriginal: it.descricao ?? "",
    nivel: it.nivel,
    extras: it.extras,
  }));
}

/** Avisos agrupados para a tela: o que o arquiteto precisa conferir. */
export function resumoAvisos(imp: Importacao): { total: number; linhas: string[] } {
  return {
    total: imp.avisos.length,
    linhas: imp.avisos.map((a) => (a.linha !== null ? `Linha ${a.linha}: ${a.mensagem}` : a.mensagem)),
  };
}
