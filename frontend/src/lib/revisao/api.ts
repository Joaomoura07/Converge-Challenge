// Chamada ao backend da revisão. O caminho da URL fica numa constante só: quando o João remover o handler dele de
// POST /revisao/sugestoes e a A assumir esse caminho (PROPOSTA), basta trocar CAMINHO_SUGESTOES.

import type { DadosRevisao, ItemParaRevisao } from "./tipos";

export const CAMINHO_SUGESTOES = "/revisao/sugestoes/completo";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const PRAZO_MS = 20_000;

export class ErroSugestoes extends Error {
  constructor(mensagem: string) {
    super(mensagem);
    this.name = "ErroSugestoes";
  }
}

function dadosValidos(x: unknown): x is DadosRevisao {
  if (typeof x !== "object" || x === null) return false;
  const d = x as Record<string, unknown>;
  return (
    typeof d.revisao_id === "string" &&
    Array.isArray(d.erros) &&
    Array.isArray(d.complementos) &&
    typeof d.complementos_disponiveis === "boolean"
  );
}

type Opcoes = { signal?: AbortSignal; fetchImpl?: typeof fetch; apiUrl?: string };

/**
 * Pede erros E1 e complementos E2 para a lista. `redigir: false` evita o LLM a cada edição (custo e latência):
 * a tela mostra o texto fixo calculado pelas regras.
 */
export async function buscarSugestoes(itens: ItemParaRevisao[], opcoes: Opcoes = {}): Promise<DadosRevisao> {
  const { signal, fetchImpl = fetch, apiUrl = API_URL } = opcoes;
  const prazo = new AbortController();
  const timer = setTimeout(() => prazo.abort(), PRAZO_MS);
  const aoCancelar = () => prazo.abort();
  signal?.addEventListener("abort", aoCancelar);
  try {
    const resposta = await fetchImpl(`${apiUrl}${CAMINHO_SUGESTOES}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itens, redigir: false }),
      signal: prazo.signal,
    });
    if (!resposta.ok) throw new ErroSugestoes(`O servidor respondeu ${resposta.status}.`);
    const corpo: unknown = await resposta.json();
    if (!dadosValidos(corpo)) throw new ErroSugestoes("Resposta inesperada do servidor.");
    return corpo;
  } catch (e) {
    if (signal?.aborted) throw e; // cancelamento pedido por quem chamou: o revisor ignora
    if (e instanceof ErroSugestoes) throw e;
    if (prazo.signal.aborted) throw new ErroSugestoes("O servidor demorou demais para responder.");
    throw new ErroSugestoes("Não foi possível falar com o servidor.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", aoCancelar);
  }
}
