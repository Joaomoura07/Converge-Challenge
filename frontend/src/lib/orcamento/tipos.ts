// Linhas de `orcamentos` e `orcamento_itens` como o site as recebe do Supabase (leitura anon + Realtime).
// Colunas de CONTRATOS-B-C.md e sql/002_orcamentos.sql. Os itens reaproveitam o tipo da B (ItemOrcamento).

import type { ItemOrcamento } from "@/components/orcamento/tipos";

export type StatusPesquisa = "pendente" | "pesquisando" | "concluida" | "falhou";

/** Resultado da C (E7, E8, E10). Null até a C calcular: a tela mostra "calculando". Detalhe em PARA-SAMUEL-2.md. */
export type Logistica = {
  estrategia?: string;
  frete_total?: number;
  total_produtos?: number;
  total?: number;
  economia_estimada?: number;
  itens_sem_loja?: number[];
  /** `itens` são POSIÇÕES na lista de itens ordenada por `linha` (não são ids). */
  lojas?: { id: string; nome: string; itens: number[]; subtotal: number; frete: number }[];
};

export type Viabilidade = {
  orcamento_cliente?: number;
  total_min?: number;
  total_med?: number;
  total_max?: number;
  cabe?: boolean;
  cabe_no_minimo?: boolean;
  diferenca?: number;
  /** false = há itens sem preço e o total é só um piso: a tela não pode afirmar "cabe" sem avisar. */
  completo?: boolean;
  resumo?: string;
  itens_sem_preco?: number[];
  sugestoes?: { tipo: string; texto: string; economia?: number }[];
};

export type Ganho = { resumo?: string; reducao_pct?: number };

export type Orcamento = {
  id: string;
  nome: string;
  cep: string;
  orcamento_cliente: number;
  status_pesquisa: StatusPesquisa;
  pesquisa_iniciada_em: string | null;
  pesquisa_concluida_em: string | null;
  pesquisa_erro: string | null;
  qtd_itens: number;
  custo_usd: number | null;
  tempo_ms: number | null;
  trace_url: string | null;
  logistica: Logistica | null;
  viabilidade: Viabilidade | null;
  ganho: Ganho | null;
  created_at: string;
  atualizado_em: string;
};

/** Linha de orcamento_itens: tudo o que a B mostra + os campos que a A grava. */
export type ItemLinha = ItemOrcamento & {
  orcamento_id: string;
  linha: number;
  categoria?: string | null;
  classificacao?: "definido" | "pendente";
  sugerido?: boolean;
  aceito?: boolean | null;
  atualizado_em: string;
};
