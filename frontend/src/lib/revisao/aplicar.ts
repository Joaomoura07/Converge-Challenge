// Aplicação das propostas na lista. Funções puras: devolvem uma lista nova ou null; a lista original nunca é alterada.

import type { Linha } from "../lista";
import type { ComplementoSugerido, CorrecaoSugerida, ErroRevisao, ItemParaRevisao } from "./tipos";

const mesmo = (a: string, b: string) => a.trim() === b.trim();

/** Linhas com conteúdo, no formato do revisor. A linha da lista é a do arquivo, senão a posição (1-based). */
export function paraItensRevisao(linhas: Linha[]): ItemParaRevisao[] {
  const itens: ItemParaRevisao[] = [];
  linhas.forEach((l, i) => {
    if (!l.descricao.trim()) return;
    itens.push({
      id: l.id,
      descricao: l.descricao,
      quantidade: l.quantidade,
      unidade: l.unidade,
      categoria: l.categoria,
      linhaOrigem: l.linhaOrigem ?? i + 1,
    });
  });
  return itens;
}

/** Identifica o conteúdo da lista: qualquer edição muda a versão e invalida o que foi calculado antes. */
export function versaoDaLista(linhas: Linha[]): string {
  return linhas.map((l) => [l.id, l.descricao, l.quantidade, l.unidade, l.categoria].join("␟")).join("␞");
}

/**
 * Aplica uma correção E1. Devolve null se alguma linha sumiu ou se o valor atual não é mais o que a regra viu
 * (a lista mudou depois do cálculo): nesse caso nada é alterado.
 */
export function aplicarCorrecao(linhas: Linha[], c: CorrecaoSugerida): Linha[] | null {
  const porId = new Map(linhas.map((l) => [l.id, l]));
  for (const a of c.alteracoes) {
    const l = a.item_id ? porId.get(a.item_id) : undefined;
    if (!l || !mesmo(l[a.campo], a.de)) return null;
  }
  for (const r of c.remover) if (!r.item_id || !porId.has(r.item_id)) return null;
  const sair = new Set(c.remover.map((r) => r.item_id));
  return linhas
    .filter((l) => !sair.has(l.id))
    .map((l) => {
      const mudancas = c.alteracoes.filter((a) => a.item_id === l.id);
      return mudancas.length ? { ...l, ...Object.fromEntries(mudancas.map((a) => [a.campo, a.para])) } : l;
    });
}

/** Campos alterados por uma correção, para a lista mostrar já validados. */
export function camposTocados(c: CorrecaoSugerida): { id: string; campo: "quantidade" | "unidade" }[] {
  return c.alteracoes.flatMap((a) => (a.item_id ? [{ id: a.item_id, campo: a.campo }] : []));
}

export function quantidadeParaTexto(n: number): string {
  return String(Number(n.toFixed(4))).replace(".", ",");
}

/** Linha nova para um complemento aceito: marcada como sugerida, com regra, motivo e linhas de origem. */
export function complementoParaLinha(c: ComplementoSugerido, id: string): Linha {
  return {
    id,
    descricao: c.descricao,
    quantidade: quantidadeParaTexto(c.quantidade),
    unidade: c.unidade,
    categoria: c.categoria,
    sugerida: {
      sugestaoId: c.id,
      regra: c.regra,
      motivo: c.motivo,
      origemLinhas: c.origem_linhas,
      estimativaConsumo: c.estimativa_consumo,
    },
  };
}

/**
 * "Aceitar todas as correções": simula a lista em sequência e devolve só as correções que ainda se aplicam.
 * Se duas correções se atropelam (mexem na mesma célula ou uma remove a linha da outra), a primeira vence e a
 * segunda NÃO entra: continua na tela para a pessoa decidir. Correção sem proposta automática também fica de fora.
 */
export function planejarAceiteTodas(linhas: Linha[], erros: ErroRevisao[]): { aplicar: ErroRevisao[]; restam: ErroRevisao[] } {
  let atual = linhas;
  const aplicar: ErroRevisao[] = [];
  const restam: ErroRevisao[] = [];
  for (const e of erros) {
    const depois = e.correcao ? aplicarCorrecao(atual, e.correcao) : null;
    if (depois) {
      atual = depois;
      aplicar.push(e);
    } else restam.push(e);
  }
  return { aplicar, restam };
}
