// Contrato JSON da importação (tests/importacao/contrato.py e docs/testes/casos-de-teste-importacao.md).
// Todo leitor (CSV agora; Excel, Revit e PDF nas próximas etapas) devolve este formato.

export type UnidadeContrato = "m" | "m2" | "m3" | "un" | "kg" | "l" | "cm" | "mm" | "ft-in";

export type CodigoErro =
  | "ARQUIVO_VAZIO"
  | "FORMATO_INVALIDO"
  | "FORMATO_NAO_SUPORTADO"
  | "ARQUIVO_PROTEGIDO"
  | "ARQUIVO_CORROMPIDO"
  | "ARQUIVO_GRANDE_DEMAIS"
  | "CSV_MALFORMADO"
  | "CABECALHO_NAO_ENCONTRADO"
  | "PDF_SEM_TEXTO";

export type CodigoAviso =
  | "SEM_DADOS"
  | "COLUNAS_EXTRAS"
  | "COLUNAS_FALTANTES"
  | "COLUNA_DUPLICADA"
  | "QUANTIDADE_AUSENTE"
  | "VALOR_NAO_NUMERICO"
  | "VALOR_NEGATIVO"
  | "NUMERO_AMBIGUO"
  | "UNIDADES_MISTAS"
  | "UNIDADE_IMPERIAL"
  | "ERRO_FORMULA"
  | "TOTAL_DIVERGENTE"
  | "CODIFICACAO_INVALIDA"
  | "TEXTO_TRUNCADO"
  | "EXTENSAO_INCORRETA"
  | "CABECALHO_MULTILINHA"
  | "EMBALAGEM_COMO_UNIDADE"
  | "EXTRACAO_AMBIGUA";

export type ItemImportado = {
  /** Linha do arquivo original (1 = primeira linha). */
  linha: number;
  categoria: string | null;
  descricao: string | null;
  quantidade: number | null;
  unidade: UnidadeContrato | string | null;
  nivel: string | null;
  extras: Record<string, unknown>;
};

export type AvisoImportacao = {
  linha: number | null;
  codigo: CodigoAviso;
  mensagem: string;
};

export type OrigemImportacao = {
  arquivo: string;
  formato: "csv" | "xlsx" | "xls" | "xlsm" | "txt" | "pdf";
  software: "revit" | "sketchup" | "desconhecido";
  aba: string | null;
  delimitador: string | null;
  codificacao: string | null;
  linhas_lidas: number;
  linhas_descartadas: number;
};

export type Importacao = {
  origem: OrigemImportacao;
  itens: ItemImportado[];
  avisos: AvisoImportacao[];
};

export type ErroImportacao = {
  erro: {
    codigo: CodigoErro;
    mensagem: string;
    linha?: number | null;
    colunas_encontradas?: string[] | null;
  };
};

export type ResultadoImportacao = Importacao | ErroImportacao;

export function ehErro(r: ResultadoImportacao): r is ErroImportacao {
  return "erro" in r;
}

export const LIMITE_BYTES = 20 * 1024 * 1024; // decisão D6
export const LIMITE_ITENS = 100_000;
/** Itens por ORÇAMENTO enviado (igual a LIMITE_ITENS de src/rotas_orcamentos.py). O leitor aceita até 100.000 (LIMITE_ITENS)
 *  (TC-084, 50 mil linhas), mas a lista da tela e o envio param aqui, para a tela não travar e o servidor não recusar. */
export const LIMITE_ITENS_ORCAMENTO = 5000;
export const LIMITE_TEXTO = 2000;
