// Regras puras da lista de resultado (fatia B): ordem dos itens, progresso e a chamada de repesquisa.
// Sem React aqui: é o que os testes (resultado.test.ts) exercitam.

import { normalizarApiUrl } from "@/lib/apiUrl";
import type { ItemOrcamento, Objetivo, StatusItem } from "./tipos";

// Pendentes juntos no fim, com a pergunta do agente (skills/04-ui-design.md, seção 3.3).
// Não encontrados logo antes deles: também pedem uma ação do arquiteto ("Pesquisar de novo").
const ORDEM: Record<StatusItem, number> = {
  buscando: 0, definido: 0, nao_encontrado: 1, erro: 1, pendente_especificacao: 2,
};

/** Ordem estável: dentro do mesmo grupo, mantém a ordem em que os itens chegaram (a da lista do arquiteto). */
export function ordenarItens<T extends Pick<ItemOrcamento, "status">>(itens: T[]): T[] {
  return itens
    .map((item, i) => ({ item, i }))
    .sort((a, b) => ORDEM[a.item.status] - ORDEM[b.item.status] || a.i - b.i)
    .map(({ item }) => item);
}

export interface Progresso {
  prontos: number;
  total: number;
  pendentes: number;
  naoEncontrados: number;
  concluido: boolean;
}

export function progresso(itens: Pick<ItemOrcamento, "status">[]): Progresso {
  const prontos = itens.filter((i) => i.status !== "buscando").length;
  return {
    prontos,
    total: itens.length,
    pendentes: itens.filter((i) => i.status === "pendente_especificacao").length,
    naoEncontrados: itens.filter((i) => i.status === "nao_encontrado" || i.status === "erro").length,
    concluido: itens.length > 0 && prontos === itens.length,
  };
}

/** Frase do topo da lista, lida também por leitor de tela (aria-live). */
export function fraseProgresso(p: Progresso): string {
  if (p.total === 0) return "Nenhum item enviado para a IA ainda.";
  if (!p.concluido) return `${p.prontos} de ${p.total} itens pesquisados`;
  const partes = [`Pesquisa concluída: ${p.total} ${p.total === 1 ? "item" : "itens"}`];
  if (p.pendentes) partes.push(`${p.pendentes} ${p.pendentes === 1 ? "precisa" : "precisam"} da sua especificação`);
  if (p.naoEncontrados) partes.push(`${p.naoEncontrados} sem preço encontrado`);
  return partes.join(". ") + ".";
}

// ------------------------------------------------------------------ repesquisa (rota da fatia B)
export const MIN_ESPECIFICACAO = 3;   // igual ao backend (RepesquisarRequest.nova_descricao, min_length=3)

/** O que a rota devolve: ResultadoItem do backend (src/modelos.py), com `item_id` no lugar de `id`. */
/** O que a alternativa fez (só quando o pedido foi maior qualidade / menor preço / outra marca). */
export interface TrocaAlternativa {
  objetivo: string;
  trocou: boolean;
  agora: string | null;
  antes: { descricao: string; embalagem?: string | null; preco_emb_med?: number | null;
           preco_un_med?: number | null; unidade_preco?: string | null };
}

export type ResultadoApi = Omit<ItemOrcamento, "id" | "descricao" | "quantidade" | "unidade"> & {
  item_id: string;
  alternativa?: TrocaAlternativa;
};

export class ErroRepesquisa extends Error {}

// "Pesquisar de novo" escolhendo outro produto: o backend pede a sugestão à IA e confere o preço nas lojas.
// Tipo e rótulos ficam nos arquivos compartilhados com a prévia (tipos.ts, formato.ts).
export { OBJETIVOS } from "./formato";
export type { Objetivo } from "./tipos";

/** Segundo argumento de repesquisarItem: texto = resposta à pergunta; `{objetivo}` = alternativa;
 *  `{ aceitarMedia: true }` = "Usar a média mesmo assim" (o item pendente fica com a média dos parecidos). */
export type PedidoRepesquisa = string | { objetivo: Objetivo } | { aceitarMedia: true } | { voltarPara: string };

/**
 * POST {API}/orcamento-itens/{id}/repesquisar. Sem `pedido` = "Pesquisar de novo" (o mesmo produto); com texto =
 * "Responder"; com `{objetivo}` = pesquisar uma alternativa (o item só troca se ela for achada à venda e, no
 * "menor preço", sair mais barata; senão volta como estava, com o motivo); com `{aceitarMedia: true}` = "Usar a
 * média mesmo assim" (o item sai de pendente e fica como estimativa, sem marca).
 * O backend grava o item no Supabase (o Realtime atualiza a tela) e também devolve o resultado.
 * Pode levar até ~1 min: o agente refaz a busca quando faltam lojas.
 */
export async function repesquisarItem(
  itemId: string,
  pedido?: PedidoRepesquisa,
  apiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL,
  buscar: typeof fetch = fetch,
): Promise<ResultadoApi> {
  const base = normalizarApiUrl(apiUrl);
  if (!base) throw new ErroRepesquisa("Endereço da API não configurado (NEXT_PUBLIC_API_URL).");
  const texto = typeof pedido === "string" ? pedido.trim() : undefined;
  if (texto !== undefined && texto.length < MIN_ESPECIFICACAO) {
    throw new ErroRepesquisa("Escreva a especificação com pelo menos 3 letras (marca, linha ou medida).");
  }
  const corpo = texto ? { nova_descricao: texto }
    : typeof pedido === "object"
      ? ("aceitarMedia" in pedido ? { aceitar_media: true }
        : "voltarPara" in pedido ? { voltar_para: pedido.voltarPara }
        : { objetivo: pedido.objetivo })
    : null;
  let resposta: Response;
  try {
    resposta = await buscar(`${base}/orcamento-itens/${encodeURIComponent(itemId)}/repesquisar`, {
      method: "POST",
      headers: corpo ? { "Content-Type": "application/json" } : undefined,
      body: corpo ? JSON.stringify(corpo) : undefined,
      signal: AbortSignal.timeout(120_000),
    });
  } catch {
    throw new ErroRepesquisa("Não consegui falar com o servidor. Confira a conexão e tente de novo.");
  }
  if (resposta.status === 404) throw new ErroRepesquisa("Este item não existe mais no orçamento. Recarregue a página.");
  if (!resposta.ok) {
    // 503 da alternativa já vem com a frase para o arquiteto ("O item ficou como estava…").
    const detalhe = await resposta.json().then((j) => j?.detail, () => undefined);
    if (resposta.status === 503 && typeof detalhe === "string" && detalhe) throw new ErroRepesquisa(detalhe);
    throw new ErroRepesquisa(`A pesquisa falhou (erro ${resposta.status}). Tente de novo em instantes.`);
  }
  return (await resposta.json()) as ResultadoApi;
}

/** Junta o resultado da rota ao item da tela (o Realtime traz o mesmo dado logo depois). */
export function aplicarResultado(item: ItemOrcamento, r: ResultadoApi): ItemOrcamento {
  const { item_id: _ignorado, alternativa: _troca, ...campos } = r;
  return { ...item, ...campos };
}
