// Contrato de POST /revisao/sugestoes/completo (src/rotas_revisao.py). Só propostas: nada vale sem o clique.

export type RegraErro = "unidade" | "quantidade" | "duplicado" | "colunas_trocadas";

export type AlteracaoSugerida = {
  item_id: string | null;
  linha: number;
  campo: "quantidade" | "unidade";
  de: string;
  para: string;
};

export type ItemRef = { item_id: string | null; linha: number };

export type CorrecaoSugerida = {
  acao: "alterar" | "remover" | "mesclar";
  alteracoes: AlteracaoSugerida[];
  remover: ItemRef[];
};

export type ErroRevisao = {
  id: string;
  regra: RegraErro;
  linhas: number[];
  item_ids: (string | null)[];
  campo: string;
  valor_atual: unknown;
  correcao: CorrecaoSugerida | null; // null = sem proposta segura; o arquiteto corrige à mão
  motivo: string;
  fatos: Record<string, unknown>;
  texto: string;
  redacao: "fixa" | "llm";
};

export type ComplementoSugerido = {
  id: string;
  regra: string;
  descricao: string;
  quantidade: number;
  unidade: string;
  categoria: string;
  motivo: string;
  origem_linhas: number[];
  origem_item_ids: string[];
  /** estimativa de CONSUMO da C; diferente da estimativa de PREÇO da B */
  estimativa_consumo: boolean;
};

export type DadosRevisao = {
  revisao_id: string;
  erros: ErroRevisao[];
  complementos: ComplementoSugerido[];
  complementos_disponiveis: boolean;
  complementos_erro: string | null;
};

/** Item enviado ao revisor: a mesma forma de Linha, com a linha da lista já resolvida. */
export type ItemParaRevisao = {
  id: string;
  descricao: string;
  quantidade: string;
  unidade: string;
  categoria: string;
  linhaOrigem: number;
};
