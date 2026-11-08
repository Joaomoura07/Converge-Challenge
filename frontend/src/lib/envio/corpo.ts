// Corpo do POST /orcamentos ("Enviar para a IA"). Espelha src/rotas_orcamentos.py (OrcamentoIn): o servidor é estrito,
// então só vão os campos do contrato (nada de campo extra) e a quantidade vai como NÚMERO, nunca como texto.

import { itensValidados, type Linha } from "../lista";
import type { Obra } from "@/components/NovaObra";

export type ItemEnvio = {
  id: string;
  linha: number;
  categoria: string | null;
  descricao: string;
  quantidade: number;
  unidade: string;
  origem_item: "arquivo" | "manual";
  descricao_original?: string;
  nivel?: string | null;
  extras?: Record<string, unknown>;
  // complemento da C já decidido pelo arquiteto (só aceitos chegam aqui)
  sugerido?: boolean;
  sugestao_aceita_id?: string;
  sugestao_regra?: string;
  sugestao_motivo?: string;
  origem_linhas?: number[];
  aceito?: boolean;
  estimativa_consumo?: boolean;
};

export type CorpoEnvio = {
  orcamento_id: string;
  obra: { nome: string; cep: string; orcamento_cliente: number };
  origem: { tipo: "arquivo" | "manual" | "misto"; modo: string };
  itens: ItemEnvio[];
};

/** Monta o corpo a partir da lista da tela. Devolve null se ainda houver erro na lista (o botão já fica bloqueado). */
export function montarCorpo(args: { orcamentoId: string; obra: Obra; linhas: Linha[]; modo: string }): CorpoEnvio | null {
  const { orcamentoId, obra, linhas, modo } = args;
  const limpos = itensValidados(linhas);
  if (!limpos) return null;
  const itens: ItemEnvio[] = limpos.map((v, i) => {
    const l = linhas[i];
    const item: ItemEnvio = {
      id: v.id,
      // a mesma numeração que o revisor E1/E2 usa: linha do arquivo, senão a posição (1-based)
      linha: l.linhaOrigem ?? i + 1,
      categoria: v.categoria,
      descricao: v.descricao,
      quantidade: v.quantidade,
      unidade: v.unidade,
      origem_item: l.linhaOrigem !== undefined ? "arquivo" : "manual",
      ...(l.descricaoOriginal !== undefined ? { descricao_original: l.descricaoOriginal } : {}),
      ...(l.nivel !== undefined ? { nivel: l.nivel } : {}),
      ...(l.extras !== undefined ? { extras: l.extras } : {}),
    };
    if (l.sugerida) {
      item.sugerido = true;
      item.sugestao_aceita_id = l.sugerida.sugestaoId;
      item.sugestao_regra = l.sugerida.regra;
      item.sugestao_motivo = l.sugerida.motivo;
      item.origem_linhas = l.sugerida.origemLinhas;
      item.aceito = true; // uma linha de complemento só existe na lista depois do clique em Aceitar
      item.estimativa_consumo = l.sugerida.estimativaConsumo;
    }
    return item;
  });
  const deArquivo = itens.filter((i) => i.origem_item === "arquivo").length;
  return {
    orcamento_id: orcamentoId,
    obra: { nome: obra.nome, cep: obra.cep, orcamento_cliente: obra.orcamentoCliente },
    origem: { tipo: deArquivo === 0 ? "manual" : deArquivo === itens.length ? "arquivo" : "misto", modo },
    itens,
  };
}

/** Conteúdo que identifica o envio (obra + itens, sem o orcamento_id): decide se um reenvio é o MESMO pedido. */
export function conteudoDoEnvio(c: CorpoEnvio): string {
  return JSON.stringify({ obra: c.obra, itens: c.itens });
}
