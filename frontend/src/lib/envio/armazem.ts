"use client";

// Estado dos envios em andamento, FORA dos componentes: a tela vai de /nova para /obra/[id] logo ao enviar, e o POST
// (que também faz a pesquisa) continua aberto enquanto a pessoa acompanha o resultado ao vivo.

import { useSyncExternalStore } from "react";
import type { CorpoEnvio } from "./corpo";
import { enviarOrcamento, type ResultadoEnvio } from "./enviar";

export type EstadoEnvio =
  | { tipo: "enviando"; corpo: CorpoEnvio; tentativa: number }
  | { tipo: "concluido"; corpo: CorpoEnvio; resultado: Extract<ResultadoEnvio, { tipo: "ok" }> }
  | { tipo: "erro"; corpo: CorpoEnvio; erro: Extract<ResultadoEnvio, { tipo: "erro" }> };

type Enviar = typeof enviarOrcamento;

const envios = new Map<string, EstadoEnvio>();
const ouvintes = new Set<() => void>();
const ultimaTentativa = new Map<string, number>();

function publicar(id: string, estado: EstadoEnvio) {
  envios.set(id, estado);
  ouvintes.forEach((o) => o());
}

/** Começa (ou refaz) o envio. O mesmo corpo com o mesmo orcamento_id é seguro: o servidor recupera sem duplicar. */
export async function iniciarEnvio(corpo: CorpoEnvio, enviar: Enviar = enviarOrcamento): Promise<void> {
  const id = corpo.orcamento_id;
  const atual = envios.get(id);
  if (atual?.tipo === "enviando") return; // já há um POST aberto para este orçamento: não dispara outro
  const tentativaAnterior = ultimaTentativa.get(id) ?? 0;
  ultimaTentativa.set(id, tentativaAnterior + 1);
  publicar(id, { tipo: "enviando", corpo, tentativa: tentativaAnterior + 1 });
  const r = await enviar(corpo);
  publicar(id, r.tipo === "ok" ? { tipo: "concluido", corpo, resultado: r } : { tipo: "erro", corpo, erro: r });
}

/** Tenta de novo o mesmo pedido (botão "Reenviar"). */
export function reenviar(id: string, enviar: Enviar = enviarOrcamento): Promise<void> | undefined {
  const atual = envios.get(id);
  if (!atual || atual.tipo === "enviando") return undefined;
  return iniciarEnvio(atual.corpo, enviar);
}

export function estadoDoEnvio(id: string): EstadoEnvio | undefined {
  return envios.get(id);
}

export function limparEnvio(id: string) {
  envios.delete(id);
  ouvintes.forEach((o) => o());
}

/** Só para testes. */
export function reiniciarEnvios() {
  envios.clear();
  ultimaTentativa.clear();
}

function assinar(o: () => void) {
  ouvintes.add(o);
  return () => ouvintes.delete(o);
}

export function useEnvio(id: string | null): EstadoEnvio | undefined {
  return useSyncExternalStore(
    assinar,
    () => (id ? envios.get(id) : undefined),
    () => undefined,
  );
}
