// Lista única de revisão. Todos os modos de entrada (manual, CSV, Excel, Revit, PDF)
// alimentam esta mesma lista. Cada linha tem ID estável; erros são derivados e indexados por ID.

import { aplicarCorrecao, camposTocados } from "./revisao/aplicar";
import type { CorrecaoSugerida } from "./revisao/tipos";
import {
  validarDescricao,
  validarQuantidade,
  validarUnidade,
  type Unidade,
} from "./validacao";

export type ModoEntrada = "manual" | "csv" | "excel" | "revit" | "pdf" | "dxf" | "ifc" | "skp";

export type Campo = "descricao" | "quantidade" | "unidade" | "categoria";

/** Complemento E2 aceito pelo arquiteto: a linha lembra por que existe. Só entra na conta depois do aceite. */
export type Sugerida = {
  sugestaoId: string;
  regra: string;
  motivo: string;
  /** linhas da lista que motivaram o complemento */
  origemLinhas: number[];
  /** estimativa de CONSUMO (da C); não é estimativa de preço (da B) */
  estimativaConsumo: boolean;
};

export type Linha = {
  id: string; // estável: nunca é o índice
  descricao: string;
  quantidade: string; // texto digitado; o número só sai da validação
  unidade: string;
  categoria: string;
  /** linha do arquivo importado; ausente nas linhas digitadas */
  linhaOrigem?: number;
  /** Rastreabilidade do arquivo preservada mesmo depois da revisão e do reenvio. */
  descricaoOriginal?: string;
  nivel?: string | null;
  extras?: Record<string, unknown>;
  /** presente só nas linhas criadas por um complemento aceito */
  sugerida?: Sugerida;
};

export type ErrosLinha = Partial<Record<"descricao" | "quantidade" | "unidade", string>>;

export type Decisao = "aceita" | "recusada";

export type EstadoLista = {
  modo: ModoEntrada;
  linhas: Linha[];
  /** campos já visitados (blur) ou revelados: "id:campo" */
  tocados: Record<string, true>;
  /** decisões sobre sugestões (id da sugestão → aceita/recusada): garantem que o aceite vale uma vez só */
  decisoes: Record<string, Decisao>;
};

export type Acao =
  | { tipo: "adicionar"; id: string }
  | { tipo: "editar"; id: string; campo: Campo; valor: string }
  | { tipo: "remover"; id: string }
  | { tipo: "tocar"; id: string; campo: Campo }
  | { tipo: "revelar_erros" }
  | { tipo: "alternar_modo"; modo: ModoEntrada }
  // Importadores (CSV na etapa 04; Excel, Revit e PDF nas seguintes) entram por aqui.
  | { tipo: "importar"; linhas: Linha[]; como: "acrescentar" | "substituir" }
  // Sugestões (etapa 06): só mudam a lista quando chegam por um clique do arquiteto, e cada id vale uma vez.
  | { tipo: "aceitar_correcao"; id: string; correcao: CorrecaoSugerida }
  | { tipo: "aceitar_complemento"; id: string; linha: Linha }
  | { tipo: "recusar_sugestao"; id: string }
  // Lista maior que o teto da pesquisa: o arquiteto escolhe manter só as primeiras N linhas (Caderno, "Manter só os N").
  | { tipo: "manter_primeiras"; quantidade: number };

export const estadoInicial: EstadoLista = { modo: "manual", linhas: [], tocados: {}, decisoes: {} };

export function linhaVazia(id: string): Linha {
  return { id, descricao: "", quantidade: "", unidade: "", categoria: "" };
}

export function chaveToque(id: string, campo: string): string {
  return `${id}:${campo}`;
}

export function reduzir(estado: EstadoLista, acao: Acao): EstadoLista {
  switch (acao.tipo) {
    case "adicionar":
      if (estado.linhas.some((l) => l.id === acao.id)) return estado;
      return { ...estado, linhas: [...estado.linhas, linhaVazia(acao.id)] };
    case "editar":
      return {
        ...estado,
        linhas: estado.linhas.map((l) =>
          l.id === acao.id ? { ...l, [acao.campo]: acao.valor } : l,
        ),
      };
    case "remover": {
      const tocados = { ...estado.tocados };
      for (const k of Object.keys(tocados)) if (k.startsWith(`${acao.id}:`)) delete tocados[k];
      // Remover um complemento aceito libera a sugestão para ser proposta de novo.
      const sugestaoId = estado.linhas.find((l) => l.id === acao.id)?.sugerida?.sugestaoId;
      const decisoes = { ...estado.decisoes };
      if (sugestaoId) delete decisoes[sugestaoId];
      return { ...estado, linhas: estado.linhas.filter((l) => l.id !== acao.id), tocados, decisoes };
    }
    case "tocar":
      return { ...estado, tocados: { ...estado.tocados, [chaveToque(acao.id, acao.campo)]: true } };
    case "revelar_erros": {
      const tocados = { ...estado.tocados };
      for (const l of estado.linhas)
        for (const c of ["descricao", "quantidade", "unidade"] as const)
          tocados[chaveToque(l.id, c)] = true;
      return { ...estado, tocados };
    }
    case "alternar_modo":
      // Só muda o modo: a lista e as edições ficam intactas.
      return { ...estado, modo: acao.modo };
    case "importar":
      return {
        ...estado,
        linhas: acao.como === "substituir" ? acao.linhas : [...estado.linhas, ...acao.linhas],
        decisoes: acao.como === "substituir" ? {} : estado.decisoes,
      };
    case "manter_primeiras": {
      const n = Math.max(0, Math.floor(acao.quantidade));
      if (estado.linhas.length <= n) return estado;
      const ficam = estado.linhas.slice(0, n);
      const ids = new Set(ficam.map((l) => l.id));
      const tocados = Object.fromEntries(Object.entries(estado.tocados).filter(([k]) => ids.has(k.split(":")[0])));
      // complemento aceito que saiu da lista libera a sugestão (mesma regra de "remover")
      const decisoes = { ...estado.decisoes };
      for (const l of estado.linhas.slice(n)) if (l.sugerida?.sugestaoId) delete decisoes[l.sugerida.sugestaoId];
      return { ...estado, linhas: ficam, tocados, decisoes };
    }
    case "aceitar_correcao": {
      if (estado.decisoes[acao.id]) return estado; // aceite repetido (ou já recusada): não reaplica
      const linhas = aplicarCorrecao(estado.linhas, acao.correcao);
      if (!linhas) return estado; // a lista mudou desde o cálculo: nada é alterado
      const tocados = { ...estado.tocados };
      for (const t of camposTocados(acao.correcao)) tocados[chaveToque(t.id, t.campo)] = true;
      return { ...estado, linhas, tocados, decisoes: { ...estado.decisoes, [acao.id]: "aceita" } };
    }
    case "aceitar_complemento":
      if (estado.decisoes[acao.id]) return estado;
      if (estado.linhas.some((l) => l.sugerida?.sugestaoId === acao.id)) return estado;
      return {
        ...estado,
        linhas: [...estado.linhas, { ...acao.linha, sugerida: { ...acao.linha.sugerida!, sugestaoId: acao.id } }],
        decisoes: { ...estado.decisoes, [acao.id]: "aceita" },
      };
    case "recusar_sugestao":
      if (estado.decisoes[acao.id]) return estado;
      return { ...estado, decisoes: { ...estado.decisoes, [acao.id]: "recusada" } };
  }
}

/** Erros por ID de linha. Linhas sem erro não aparecem no mapa. */
export function errosPorId(linhas: Linha[]): Record<string, ErrosLinha> {
  const mapa: Record<string, ErrosLinha> = {};
  for (const l of linhas) {
    const e: ErrosLinha = {};
    const d = validarDescricao(l.descricao);
    if (!d.ok) e.descricao = d.erro;
    const q = validarQuantidade(l.quantidade);
    if (!q.ok) e.quantidade = q.erro;
    const u = validarUnidade(l.unidade);
    if (!u.ok) e.unidade = u.erro;
    if (Object.keys(e).length > 0) mapa[l.id] = e;
  }
  return mapa;
}

export function contarErros(erros: Record<string, ErrosLinha>): number {
  return Object.values(erros).reduce((soma, e) => soma + Object.keys(e).length, 0);
}

/** Primeiro campo com erro, na ordem visual da lista. */
export function primeiroErro(
  linhas: Linha[],
  erros: Record<string, ErrosLinha>,
): { id: string; campo: "descricao" | "quantidade" | "unidade" } | null {
  for (const l of linhas) {
    const e = erros[l.id];
    if (!e) continue;
    for (const c of ["descricao", "quantidade", "unidade"] as const) if (e[c]) return { id: l.id, campo: c };
  }
  return null;
}

export type ItemValidado = {
  id: string;
  descricao: string;
  quantidade: number;
  unidade: Unidade;
  categoria: string | null;
};

/** Valores limpos para o envio (usado a partir da etapa 08). Devolve null se houver erro. */
export function itensValidados(linhas: Linha[]): ItemValidado[] | null {
  const itens: ItemValidado[] = [];
  for (const l of linhas) {
    const d = validarDescricao(l.descricao);
    const q = validarQuantidade(l.quantidade);
    const u = validarUnidade(l.unidade);
    if (!d.ok || !q.ok || !u.ok) return null;
    itens.push({
      id: l.id,
      descricao: d.valor,
      quantidade: q.valor,
      unidade: u.valor,
      categoria: l.categoria.trim() || null,
    });
  }
  return itens;
}
