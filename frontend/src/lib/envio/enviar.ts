// POST /orcamentos: grava e PESQUISA na mesma requisição (pode levar minutos). Traduz cada resposta em um resultado
// que a tela sabe explicar e dizer o que fazer: reenviar o mesmo pedido, voltar e corrigir, ou configurar.

import { API_URL } from "../revisao/api";
import { caminhoSimulavel } from "../simulacao";
import type { CorpoEnvio } from "./corpo";

export const CAMINHO_ORCAMENTOS = "/orcamentos";

export type ResultadoEnvio =
  | { tipo: "ok"; orcamentoId: string; resultado: "criado" | "existente"; pesquisa: unknown }
  | {
      tipo: "erro";
      /** validacao: corrigir a lista · conflito: conteúdo mudou com o mesmo código · servidor: reenviar ·
       *  rede: a resposta se perdeu, o orçamento pode ter sido salvo · config: servidor sem banco */
      motivo: "validacao" | "conflito" | "servidor" | "rede" | "config";
      mensagem: string;
      /** reenviar o MESMO pedido é seguro e útil */
      recuperavel: boolean;
    };

type Opcoes = { fetchImpl?: typeof fetch; apiUrl?: string; signal?: AbortSignal };

/** Texto legível do `detail` do FastAPI (string, objeto com `mensagem` ou lista de erros do Pydantic). */
export function mensagemDoDetalhe(detail: unknown, padrao: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const d = detail[0] as { msg?: string; loc?: unknown[] };
    const onde = Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body").join(" › ") : "";
    return [onde, d.msg].filter(Boolean).join(": ") || padrao;
  }
  if (detail && typeof detail === "object" && typeof (detail as { mensagem?: unknown }).mensagem === "string") {
    return (detail as { mensagem: string }).mensagem;
  }
  return padrao;
}

export async function enviarOrcamento(corpo: CorpoEnvio, opcoes: Opcoes = {}): Promise<ResultadoEnvio> {
  const { fetchImpl = fetch, apiUrl = API_URL, signal } = opcoes;
  let resposta: Response;
  try {
    resposta = await fetchImpl(`${apiUrl}${caminhoSimulavel(CAMINHO_ORCAMENTOS)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
      signal,
    });
  } catch {
    // Sem resposta: o servidor pode ter gravado e pesquisado mesmo assim. O reenvio do mesmo pedido recupera.
    return {
      tipo: "erro",
      motivo: "rede",
      recuperavel: true,
      mensagem: "A resposta do servidor se perdeu. O orçamento pode ter sido salvo: reenvie o mesmo pedido, sem duplicar nada.",
    };
  }

  let json: unknown = null;
  try {
    json = await resposta.json();
  } catch {
    json = null;
  }
  const detail = (json as { detail?: unknown } | null)?.detail;

  if (resposta.ok) {
    const j = json as { orcamento_id?: string; resultado?: string; pesquisa?: unknown } | null;
    if (!j || typeof j.orcamento_id !== "string") {
      return { tipo: "erro", motivo: "servidor", recuperavel: true, mensagem: "O servidor respondeu de um jeito inesperado. Reenvie o mesmo pedido." };
    }
    return { tipo: "ok", orcamentoId: j.orcamento_id, resultado: j.resultado === "existente" ? "existente" : "criado", pesquisa: j.pesquisa };
  }

  if (resposta.status === 422) {
    return {
      tipo: "erro",
      motivo: "validacao",
      recuperavel: false,
      mensagem: `O servidor recusou a lista: ${mensagemDoDetalhe(detail, "dados inválidos")}. Volte, corrija e envie de novo.`,
    };
  }
  if (resposta.status === 409) {
    return {
      tipo: "erro",
      motivo: "conflito",
      recuperavel: false,
      mensagem: "Este orçamento já foi enviado com outro conteúdo. Volte e envie de novo: a lista ganha um novo código.",
    };
  }
  if (resposta.status === 503) {
    return {
      tipo: "erro",
      motivo: "config",
      recuperavel: false,
      mensagem: "O servidor ainda não está ligado ao banco de dados. Avise quem cuida do ambiente.",
    };
  }
  const recuperavel = Boolean((detail as { recuperavel?: unknown } | null)?.recuperavel) || resposta.status >= 500;
  return {
    tipo: "erro",
    motivo: "servidor",
    recuperavel,
    mensagem: mensagemDoDetalhe(detail, `O servidor respondeu ${resposta.status}.`) + (recuperavel ? " Reenvie o mesmo pedido." : ""),
  };
}
