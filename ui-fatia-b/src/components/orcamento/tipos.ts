// Linha de `orcamento_itens` como o site recebe do Supabase (Realtime).
// Espelha ResultadoItem em src/modelos.py (contrato da fatia B) + as colunas que a fatia A grava.

export type StatusItem = "buscando" | "definido" | "pendente_especificacao" | "nao_encontrado" | "erro";
export type Confianca = "alta" | "media" | "baixa";

export interface Fonte {
  loja: string;
  dominio: string;
  url: string;
  preco_embalagem: number;
  embalagem?: string | null;
}

export interface ItemOrcamento {
  id: string;
  descricao: string;
  quantidade?: number | null;
  unidade?: string | null;
  status: StatusItem;
  produto_normalizado?: string | null;
  imagem_url?: string | null;
  embalagem?: string | null;
  qtd_embalagens?: number | null;
  preco_emb_min?: number | null;
  preco_emb_med?: number | null;
  preco_emb_max?: number | null;
  preco_un_min?: number | null;
  preco_un_med?: number | null;
  preco_un_max?: number | null;
  unidade_preco?: string | null;
  confianca?: Confianca | null;
  estimativa?: boolean;
  fontes?: Fonte[];
  premissa?: string | null;
  pergunta?: string | null;
  motivo?: string | null;
  preco_data?: string | null;
  iteracoes?: number;
}
