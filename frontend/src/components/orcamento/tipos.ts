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
  /** Preço e embalagem como estão no anúncio (o que a pessoa vê ao clicar). Ausentes em itens antigos. */
  preco_anunciado?: number | null;
  embalagem_anunciada?: string | null;
  /** Rede com loja física no estado da obra. */
  perto_da_obra?: boolean;
  /** Loja da região da obra (Google Maps pelo CEP): distância de carro aproximada e endereço. */
  distancia_km?: number | null;
  endereco?: string | null;
}

export interface Validacao {
  status: "confirmado" | "divergente_leve" | "divergente" | "sem_dados";
  fonte?: string;
  mediana?: number | null;
  diferenca_pct?: number | null;
  n?: number;
}

export interface PesquisaDetalhes {
    tokens_entrada: number;
    tokens_saida: number;
    chamadas: number;
    custo_usd: number;
    consumo_incompleto: boolean;
    limite_atingido: boolean;
    paginas_lidas: number;
    orientacao?: string;
}

export interface ItemOrcamento {
  pesquisa_detalhes?: PesquisaDetalhes | null;
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
  /** Conferência do preço numa 2ª fonte (Google Shopping): só informa, nunca troca o preço. */
  validacao?: Validacao | null;
}

/** "Pesquisar de novo" buscando outro produto (POST /orcamento-itens/{id}/repesquisar com {objetivo}). */
export type Objetivo = "qualidade" | "preco" | "semelhante";
