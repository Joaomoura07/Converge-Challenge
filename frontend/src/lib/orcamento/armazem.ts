// Armazém puro do estado ao vivo de um orçamento (sem React e sem Supabase: é o que os testes exercitam).
//
// Problema: o Realtime e a carga inicial chegam em ordem imprevisível, eventos podem repetir e a conexão pode cair.
// Regras:
//  - cada linha tem um ID; vence a versão com `atualizado_em` mais novo (evento atrasado nunca desfaz um dado novo);
//  - um evento repetido não muda nada (mesmo `atualizado_em`);
//  - DELETE deixa uma lápide: uma leitura que começou antes da exclusão não ressuscita a linha;
//  - a leitura (inicial ou depois de reconectar) é "iniciada" antes e "concluída" depois: eventos que chegaram no
//    meio são preservados, e linhas ausentes da leitura que nenhum evento tocou são removidas.

import type { ItemLinha, Orcamento } from "./tipos";

export type Estado = {
  orcamento: Orcamento | null;
  itens: Record<string, ItemLinha>;
  /** ids excluídos por evento */
  lapides: Record<string, true>;
  /** ids tocados por evento desde que a leitura em curso começou; null = nenhuma leitura em curso */
  tocadosNaLeitura: Set<string> | null;
  carregado: boolean;
};

export const estadoVazio = (): Estado => ({
  orcamento: null,
  itens: {},
  lapides: {},
  tocadosNaLeitura: null,
  carregado: false,
});

const ms = (iso: string | null | undefined): number => {
  const t = iso ? Date.parse(iso) : NaN;
  return Number.isNaN(t) ? -Infinity : t;
};

/** true se `nova` deve substituir `atual` (mais nova; empate = mesma versão, não substitui). */
export const eMaisNova = (nova: { atualizado_em: string }, atual: { atualizado_em: string } | undefined | null): boolean =>
  !atual || ms(nova.atualizado_em) > ms(atual.atualizado_em);

export type Evento =
  | { tabela: "orcamentos"; tipo: "INSERT" | "UPDATE"; linha: Orcamento }
  | { tabela: "orcamento_itens"; tipo: "INSERT" | "UPDATE"; linha: ItemLinha }
  | { tabela: "orcamento_itens"; tipo: "DELETE"; id: string }
  | { tabela: "orcamentos"; tipo: "DELETE" };

export function aplicarEvento(e: Estado, ev: Evento): Estado {
  if (ev.tabela === "orcamentos") {
    if (ev.tipo === "DELETE") return { ...e, orcamento: null };
    return eMaisNova(ev.linha, e.orcamento) ? { ...e, orcamento: ev.linha } : e;
  }
  if (ev.tipo === "DELETE") {
    const itens = { ...e.itens };
    delete itens[ev.id];
    return { ...e, itens, lapides: { ...e.lapides, [ev.id]: true }, tocadosNaLeitura: tocar(e, ev.id) };
  }
  const id = ev.linha.id;
  const tocados = tocar(e, id);
  // Um INSERT/UPDATE posterior a uma exclusão (id reaproveitado é improvável) volta a valer.
  const lapides = e.lapides[id] ? semChave(e.lapides, id) : e.lapides;
  if (!eMaisNova(ev.linha, e.itens[id])) return tocados === e.tocadosNaLeitura && lapides === e.lapides ? e : { ...e, tocadosNaLeitura: tocados, lapides };
  return { ...e, itens: { ...e.itens, [id]: ev.linha }, lapides, tocadosNaLeitura: tocados };
}

function tocar(e: Estado, id: string): Set<string> | null {
  if (!e.tocadosNaLeitura) return null;
  const s = new Set(e.tocadosNaLeitura);
  s.add(id);
  return s;
}

function semChave<T extends Record<string, unknown>>(o: T, k: string): T {
  const c = { ...o };
  delete c[k];
  return c;
}

/** Marca o começo de uma leitura (carga inicial ou reconexão). Eventos daqui em diante são "do meio". */
export function iniciarLeitura(e: Estado): Estado {
  return { ...e, tocadosNaLeitura: new Set() };
}

/** Funde o resultado da leitura com o que os eventos já trouxeram. */
export function concluirLeitura(e: Estado, orcamento: Orcamento | null, itens: ItemLinha[]): Estado {
  const tocados = e.tocadosNaLeitura ?? new Set<string>();
  const resultado: Record<string, ItemLinha> = {};
  for (const lido of itens) {
    if (e.lapides[lido.id]) continue; // excluído por evento: a leitura é mais velha
    const local = e.itens[lido.id];
    resultado[lido.id] = local && !eMaisNova(lido, local) ? local : lido;
  }
  // Locais que a leitura não trouxe: ficam só se um evento os tocou durante a leitura (chegaram depois do SELECT).
  for (const [id, local] of Object.entries(e.itens)) {
    if (!(id in resultado) && tocados.has(id)) resultado[id] = local;
  }
  let o = e.orcamento;
  if (orcamento && eMaisNova(orcamento, e.orcamento)) o = orcamento;
  // Orçamento ainda não existe na leitura e nenhum evento o trouxe: segue como "aguardando".
  return { ...e, orcamento: o, itens: resultado, tocadosNaLeitura: null, carregado: true };
}

/** Itens na ordem da lista do arquiteto (por `linha`); desempate pelo id para ser determinístico. */
export function itensOrdenados(e: Estado): ItemLinha[] {
  return Object.values(e.itens).sort((a, b) => a.linha - b.linha || a.id.localeCompare(b.id));
}
