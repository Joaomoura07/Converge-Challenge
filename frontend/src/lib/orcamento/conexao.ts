// Ligação com o Supabase para UM orçamento: assinatura filtrada do Realtime e leitura das duas tabelas.
// O cliente é injetado (interface mínima), então os testes usam um cliente falso.

import type { Evento } from "./armazem";
import type { ItemLinha, Orcamento } from "./tipos";

export type StatusCanal = "SUBSCRIBED" | "CHANNEL_ERROR" | "TIMED_OUT" | "CLOSED" | string;

export type Carga = { eventType: "INSERT" | "UPDATE" | "DELETE"; new: Record<string, unknown>; old: Record<string, unknown> };

export interface CanalMinimo {
  on(tipo: "postgres_changes", filtro: Record<string, unknown>, cb: (p: Carga) => void): CanalMinimo;
  subscribe(cb: (status: StatusCanal, erro?: unknown) => void): CanalMinimo;
}

export interface ClienteMinimo {
  channel(nome: string): CanalMinimo;
  removeChannel(canal: CanalMinimo): unknown;
  from(tabela: string): {
    select(colunas: string): {
      eq(
        coluna: string,
        valor: string,
      ): {
        order(coluna: string): PromiseLike<{ data: unknown; error: unknown }>;
        maybeSingle(): PromiseLike<{ data: unknown; error: unknown }>;
      };
    };
  };
}

export function traduzir(tabela: "orcamentos" | "orcamento_itens", p: Carga, orcamentoId: string): Evento | null {
  if (tabela === "orcamentos") {
    if (p.eventType === "DELETE") return { tabela, tipo: "DELETE" };
    return { tabela, tipo: p.eventType, linha: p.new as unknown as Orcamento };
  }
  if (p.eventType === "DELETE") {
    const id = (p.old as { id?: string }).id;
    const dono = (p.old as { orcamento_id?: string }).orcamento_id;
    // DELETE não respeita o filtro do canal: ignora linhas de outro orçamento quando a linha antiga os traz.
    if (!id || (dono && dono !== orcamentoId)) return null;
    return { tabela, tipo: "DELETE", id };
  }
  return { tabela, tipo: p.eventType, linha: p.new as unknown as ItemLinha };
}

/** Assina as duas tabelas, filtradas por orçamento. Devolve a função que remove a assinatura (limpeza ao desmontar). */
export function assinar(
  cliente: ClienteMinimo,
  orcamentoId: string,
  aoEvento: (e: Evento) => void,
  aoStatus: (s: StatusCanal) => void,
): () => void {
  const canal = cliente
    .channel(`orcamento:${orcamentoId}`)
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "orcamento_itens", filter: `orcamento_id=eq.${orcamentoId}` },
      (p) => {
        const ev = traduzir("orcamento_itens", p, orcamentoId);
        if (ev) aoEvento(ev);
      },
    )
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "orcamentos", filter: `id=eq.${orcamentoId}` },
      (p) => {
        const ev = traduzir("orcamentos", p, orcamentoId);
        if (ev) aoEvento(ev);
      },
    )
    .subscribe((status) => aoStatus(status));
  return () => {
    void cliente.removeChannel(canal);
  };
}

/** Lê o orçamento (pode ainda não existir: o POST está em curso) e os itens, na ordem da lista. */
export async function ler(
  cliente: ClienteMinimo,
  orcamentoId: string,
): Promise<{ orcamento: Orcamento | null; itens: ItemLinha[] }> {
  const [o, i] = await Promise.all([
    cliente.from("orcamentos").select("*").eq("id", orcamentoId).maybeSingle(),
    cliente.from("orcamento_itens").select("*").eq("orcamento_id", orcamentoId).order("linha"),
  ]);
  if (o.error) throw o.error;
  if (i.error) throw i.error;
  return { orcamento: (o.data as Orcamento | null) ?? null, itens: (i.data as ItemLinha[] | null) ?? [] };
}
