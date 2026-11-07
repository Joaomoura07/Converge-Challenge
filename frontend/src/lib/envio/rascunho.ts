// Rascunho da lista guardado na aba (sessionStorage) no instante do envio. Serve para "Voltar e corrigir":
// se o servidor recusar o pedido, a pessoa volta ao caderno com a lista como estava, sem perder as edições.
// Tudo é tolerante a falha: sem sessionStorage (modo privado, bloqueio) o caderno só abre vazio.

import type { Linha } from "../lista";
import type { Obra } from "@/components/NovaObra";

const CHAVE = "orca:rascunho";

export type Rascunho = {
  obra: Obra;
  orcamentoId: string;
  modo: string;
  linhas: Linha[];
  /** o último pedido enviado com este código: se o conteúdo mudar depois, o próximo envio ganha código novo */
  ultimoEnvio: { orcamentoId: string; conteudo: string } | null;
};

export function salvarRascunho(r: Rascunho, storage: Pick<Storage, "setItem"> | null = seguro()): boolean {
  try {
    storage?.setItem(CHAVE, JSON.stringify(r));
    return Boolean(storage);
  } catch {
    return false;
  }
}

export function lerRascunho(id: string, storage: Pick<Storage, "getItem"> | null = seguro()): Rascunho | null {
  try {
    const bruto = storage?.getItem(CHAVE);
    if (!bruto) return null;
    const r = JSON.parse(bruto) as Rascunho;
    if (!r || r.orcamentoId !== id || !Array.isArray(r.linhas) || !r.obra) return null;
    return r;
  } catch {
    return null;
  }
}

function seguro(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}
