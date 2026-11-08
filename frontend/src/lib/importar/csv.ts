// Leitor de CSV da Fatia A (etapa 04). Segue docs/testes/casos-de-teste-importacao.md (D1–D7).
// Funções puras: recebem os bytes do arquivo e devolvem o contrato (Importacao) ou um erro.
// PapaParse lê os campos (aspas, aspas escapadas, quebra de linha dentro de campo); o separador,
// a codificação, o cabeçalho e os números brasileiros são decididos aqui, porque a detecção
// automática do PapaParse erra com tabulação e vírgula decimal.

import Papa from "papaparse";
import { lerLinhaLivre, lerListaTexto, numeroBr, unidadeLivre } from "./textoLivre";
import {
  LIMITE_BYTES,
  LIMITE_ITENS,
  LIMITE_TEXTO,
  type AvisoImportacao,
  type ErroImportacao,
  type ItemImportado,
  type ResultadoImportacao,
} from "./tipos";

// ------------------------------------------------------------------ utilitários

function erro(
  codigo: ErroImportacao["erro"]["codigo"],
  mensagem: string,
  extra: Partial<ErroImportacao["erro"]> = {},
): ErroImportacao {
  return { erro: { codigo, mensagem, ...extra } };
}

/** Minúsculas, sem acento nem pontuação: "Descrição" → "descricao". */
export function normalizarNome(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const ALIAS_UNIDADE: Record<string, string> = {
  m: "m", metro: "m", metros: "m", ml: "m", "m lin": "m", mt: "m", mts: "m",
  m2: "m2", "m 2": "m2", "m^2": "m2", metro2: "m2",
  m3: "m3", "m 3": "m3", "m^3": "m3",
  un: "un", und: "un", unid: "un", unidade: "un", unidades: "un", pc: "un", pcs: "un", "pç": "un", "pçs": "un",
  peca: "un", pecas: "un", "peça": "un", "peças": "un", cj: "un", jogo: "un", par: "un", pt: "un",
  kg: "kg", quilo: "kg", quilos: "kg", kgs: "kg",
  l: "l", lt: "l", lts: "l", litro: "l", litros: "l",
  cm: "cm", mm: "mm",
};

/** Grafia canônica da unidade; devolve null se não reconhecer. */
export function normalizarUnidade(bruto: string): string | null {
  const t = bruto
    .trim()
    .toLowerCase()
    .replace(/²/g, "2")
    .replace(/³/g, "3")
    .replace(/\.$/, "");
  if (t === "") return null;
  if (t === "ft-in") return "ft-in";
  return ALIAS_UNIDADE[t] ?? ALIAS_UNIDADE[t.replace(/\s+/g, "")] ?? null;
}

// ------------------------------------------------------------------ decodificação

type Decodificado = { texto: string; codificacao: string; avisoLinha: number | null };

function decodificar(bytes: Uint8Array): Decodificado {
  if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    return { texto: new TextDecoder("utf-8").decode(bytes.subarray(3)), codificacao: "utf-8", avisoLinha: null };
  }
  if (bytes[0] === 0xff && bytes[1] === 0xfe) {
    return { texto: new TextDecoder("utf-16le").decode(bytes.subarray(2)), codificacao: "utf-16le", avisoLinha: null };
  }
  if (bytes[0] === 0xfe && bytes[1] === 0xff) {
    return { texto: new TextDecoder("utf-16be").decode(bytes.subarray(2)), codificacao: "utf-16be", avisoLinha: null };
  }
  try {
    return { texto: new TextDecoder("utf-8", { fatal: true }).decode(bytes), codificacao: "utf-8", avisoLinha: null };
  } catch {
    // Não é UTF-8 limpo. Windows-1252 (Excel pt-BR) tem MUITOS bytes inválidos em UTF-8;
    // um UTF-8 com defeito pontual tem poucos, e o resto da acentuação está válido.
    const tolerante = new TextDecoder("utf-8").decode(bytes);
    const invalidos = (tolerante.match(/�/g) ?? []).length;
    const validos = (tolerante.match(/[^\x00-\x7f�]/g) ?? []).length;
    if (validos > 0 && invalidos <= validos) {
      const antes = tolerante.slice(0, tolerante.indexOf("�"));
      const linha = (antes.match(/\r\n|\r|\n/g) ?? []).length + 1;
      return { texto: tolerante, codificacao: "utf-8", avisoLinha: linha };
    }
    return { texto: new TextDecoder("windows-1252").decode(bytes), codificacao: "windows-1252", avisoLinha: null };
  }
}

function pareceBinario(bytes: Uint8Array): boolean {
  const b = bytes;
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return true; // PNG
  if (b[0] === 0x25 && b[1] === 0x50 && b[2] === 0x44 && b[3] === 0x46) return true; // %PDF
  if (b[0] === 0x50 && b[1] === 0x4b && (b[2] === 0x03 || b[2] === 0x05)) return true; // zip/xlsx
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return true; // JPEG
  if (b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46) return true; // GIF
  if (b[0] === 0xd0 && b[1] === 0xcf && b[2] === 0x11 && b[3] === 0xe0) return true; // .xls antigo
  const utf16 = (b[0] === 0xff && b[1] === 0xfe) || (b[0] === 0xfe && b[1] === 0xff);
  if (!utf16) {
    const n = Math.min(b.length, 4096);
    for (let i = 0; i < n; i++) if (b[i] === 0) return true;
  }
  return false;
}

// ------------------------------------------------------------------ leitura do texto

/** Célula com erro (Excel: #DIV/0!, #REF!, fórmula sem resultado). */
export type CelulaErro = { erroCelula: string };
/** CSV só tem texto; Excel traz número, texto ou erro. */
export type Celula = string | number | CelulaErro | null;

export type Registro = { linha: number; celulas: Celula[]; malformado: boolean };

const ehErroCelula = (c: Celula | undefined): c is CelulaErro => typeof c === "object" && c !== null && "erroCelula" in c;
/** Texto da célula para as regras de cabeçalho, categoria, unidade etc. */
const aTexto = (c: Celula | undefined): string => (c === null || c === undefined ? "" : ehErroCelula(c) ? c.erroCelula : String(c));

const SEPARADORES = [";", "\t", ",", "|"] as const;

function escolherSeparador(texto: string): string {
  const amostra = texto.split("\n").slice(0, 60).join("\n");
  let melhor = ",";
  let melhorPlacar = -1;
  for (const sep of SEPARADORES) {
    const r = Papa.parse<string[]>(amostra, { delimiter: sep, newline: "\n", skipEmptyLines: true });
    const contagens = new Map<number, number>();
    for (const linha of r.data) contagens.set(linha.length, (contagens.get(linha.length) ?? 0) + 1);
    let colunas = 0;
    let freq = 0;
    for (const [c, f] of contagens) if (c > 1 && (f > freq || (f === freq && c > colunas))) { colunas = c; freq = f; }
    const placar = freq * 1000 + colunas;
    if (colunas > 1 && placar > melhorPlacar) { melhor = sep; melhorPlacar = placar; }
  }
  return melhor;
}

function lerRegistros(texto: string, delimitador: string): Registro[] {
  const registros: Registro[] = [];
  let anterior = 0;
  let linha = 1;
  Papa.parse<string[]>(texto, {
    delimiter: delimitador,
    newline: "\n",
    quoteChar: '"',
    skipEmptyLines: false,
    step: (r) => {
      const inicio = linha;
      const cursor = r.meta.cursor;
      linha += (texto.slice(anterior, cursor).match(/\n/g) ?? []).length;
      anterior = cursor;
      registros.push({
        linha: inicio,
        celulas: r.data.map((c) => (typeof c === "string" ? c : String(c ?? ""))),
        malformado: r.errors.some((e) => e.code === "MissingQuotes"),
      });
    },
  });
  return registros;
}

// ------------------------------------------------------------------ colunas

type Papel = "categoria" | "descricao" | "quantidade" | "unidade" | "nivel";

const SINONIMOS: Record<Papel, string[]> = {
  descricao: [
    "descricao", "descricao do item", "descricao do material", "description", "produto", "material", "item",
    "nome", "especificacao", "familia e tipo", "family and type", "definition name", "nome da definicao", "material nome", "material name", "material de acabamento",
    // jeitos de quem monta a planilha à mão (teste "como leigo", 08/11)
    "o que", "oque", "materiais", "produtos", "insumo", "insumos", "discriminacao", "descricao dos materiais",
    "descricao dos servicos", "servico", "servicos", "especificacoes", "itens", "material servico",
  ],
  quantidade: ["quantidade", "qtd", "qtde", "quant", "qty", "quantity", "count", "contagem", "area", "material area", "length", "comprimento",
    "quantidades", "qte", "qtdade", "quantia", "qtd total", "quantidade total"],
  unidade: ["unidade", "unidade de medida", "un", "und", "unid", "unit", "units", "medida", "u m", "um", "un medida", "unid medida"],
  categoria: ["categoria", "category", "tag", "grupo", "classe"],
  nivel: ["nivel", "level", "pavimento", "andar", "ambiente", "room"],
};

function papelDe(nome: string): { papel: Papel; unidade: string | null } | null {
  const n = normalizarNome(nome);
  // "Área (m²)" → quantidade com unidade padrão m2
  const m = nome.match(/^(.*?)\s*[([]\s*([^)\]]+?)\s*[)\]]\s*$/);
  if (m) {
    const u = normalizarUnidade(m[2]);
    const base = normalizarNome(m[1]);
    if (u) {
      for (const papel of Object.keys(SINONIMOS) as Papel[]) {
        if (SINONIMOS[papel].includes(base)) return { papel, unidade: u };
      }
    }
  }
  for (const papel of Object.keys(SINONIMOS) as Papel[]) {
    if (SINONIMOS[papel].includes(n)) {
      // Coluna "Área" mede m2; "Count"/"Contagem" conta unidades — quando não há coluna de unidade.
      const padrao = papel === "quantidade" ? (n === "area" || n === "material area" ? "m2" : n === "count" || n === "contagem" ? "un" : null) : null;
      return { papel, unidade: padrao };
    }
  }
  return null;
}

type Coluna = {
  indice: number;
  nome: string; // nome único, como será chave de extras
  papel: Papel | null;
  unidadePadrao: string | null;
};

// ------------------------------------------------------------------ números

type Estilo = "br" | "en" | "desconhecido";

const RE_MILHAR_UNICO = /^\d{1,3}[.,]\d{3}$/;

function evidencia(s: string): "br" | "en" | null {
  const t = s.replace(/^-/, "");
  if (!/^\d[\d.,]*$/.test(t)) return null;
  const temP = t.includes(".");
  const temV = t.includes(",");
  if (temP && temV) return t.lastIndexOf(",") > t.lastIndexOf(".") ? "br" : "en";
  if (temV) {
    if (/^\d{1,3}(,\d{3}){2,}$/.test(t)) return "en"; // 1,234,567
    if (RE_MILHAR_UNICO.test(t)) return null; // 1,500: ambíguo
    return "br"; // 12,5
  }
  if (temP) {
    if (/^\d{1,3}(\.\d{3}){2,}$/.test(t)) return "br"; // 1.234.567
    if (RE_MILHAR_UNICO.test(t)) return null; // 1.234: ambíguo
    return "en"; // 12.5
  }
  return null;
}

function detectarEstilo(valores: string[]): Estilo {
  let br = 0;
  let en = 0;
  for (const v of valores) {
    const e = evidencia(v);
    if (e === "br") br++;
    else if (e === "en") en++;
  }
  if (br > en) return "br";
  if (en > br) return "en";
  return "desconhecido";
}

type NumeroLido = { tipo: "ok"; valor: number } | { tipo: "ambiguo" } | { tipo: "invalido" };

function lerNumero(bruto: string, estilo: Estilo): NumeroLido {
  const t0 = bruto.trim();
  const negativo = t0.startsWith("-");
  const t = negativo ? t0.slice(1).trim() : t0;
  if (!/^\d[\d.,]*$/.test(t)) return { tipo: "invalido" };
  const temP = t.includes(".");
  const temV = t.includes(",");
  let normal: string;
  if (temP && temV) {
    const dec = t.lastIndexOf(",") > t.lastIndexOf(".") ? "," : ".";
    const mil = dec === "," ? "." : ",";
    if (t.split(dec).length > 2) return { tipo: "invalido" };
    normal = t.split(mil).join("").replace(dec, ".");
  } else if (temV) {
    if (/^\d{1,3}(,\d{3}){2,}$/.test(t)) normal = t.replace(/,/g, "");
    else if (RE_MILHAR_UNICO.test(t)) {
      if (estilo === "br") normal = t.replace(",", ".");
      else if (estilo === "en") normal = t.replace(",", "");
      else return { tipo: "ambiguo" };
    } else if (t.split(",").length === 2) normal = t.replace(",", ".");
    else return { tipo: "invalido" };
  } else if (temP) {
    if (/^\d{1,3}(\.\d{3}){2,}$/.test(t)) normal = t.replace(/\./g, "");
    else if (RE_MILHAR_UNICO.test(t)) {
      if (estilo === "br") normal = t.replace(".", "");
      else if (estilo === "en") normal = t;
      else return { tipo: "ambiguo" };
    } else if (t.split(".").length === 2) normal = t;
    else return { tipo: "invalido" };
  } else {
    normal = t;
  }
  const n = Number(normal);
  if (!Number.isFinite(n)) return { tipo: "invalido" };
  return { tipo: "ok", valor: negativo ? -n : n };
}

/** "12,50 m²" → { numero: "12,50", unidade: "m²" }. */
function separarValorUnidade(s: string): { numero: string; unidade: string } | null {
  const m = s.match(/^(-?\s*\d[\d.,]*)\s*([^\d\s.,][^\d]*)$/);
  if (!m) return null;
  if (!normalizarUnidade(m[2])) return null;
  return { numero: m[1].replace(/\s+/g, ""), unidade: m[2].trim() };
}

function lerMoeda(s: string): number | null {
  const m = s.match(/^R\$\s*(\d[\d.,]*)$/i);
  if (!m) return null;
  const r = lerNumero(m[1], "br");
  return r.tipo === "ok" ? r.valor : null;
}

// ------------------------------------------------------------------ importação

/** 12' 6" · 12' · 6" (pés e polegadas do Revit em inglês). */
const ehImperial = (s: string): boolean =>
  /^\d+(?:\.\d+)?\s*'(?:\s*\d+(?:\.\d+)?\s*")?$|^\d+(?:\.\d+)?\s*"$/.test(s.trim());

/** Número de uma linha de total: "Total geral: 10" ou "Total geral<TAB>10 m²". null se não achar. */
function valorDoTotal(cel: string[]): number | null {
  const textos = [cel[0]?.split(":").slice(1).join(":") ?? "", ...cel.slice(1)];
  for (const t of textos) {
    const j = separarValorUnidade(t.trim());
    const bruto = j ? j.numero : t.trim();
    let n = lerNumero(bruto, "desconhecido");
    if (n.tipo === "ambiguo") n = lerNumero(bruto, "br");
    if (n.tipo === "ok") return n.valor;
  }
  return null;
}

const vazio = (c: string | undefined) => c === undefined || c.trim() === "";

export function importarCsv({
  nome,
  bytes,
  forcarDelimitador,
  formato = "csv",
}: {
  nome: string;
  bytes: Uint8Array;
  /** TXT tabulado do Revit: força tabulação (a detecção automática erra com "12,50 m²"). */
  forcarDelimitador?: string;
  formato?: "csv" | "txt";
}): ResultadoImportacao {
  if (bytes.length === 0) return erro("ARQUIVO_VAZIO", "O arquivo está vazio.");
  if (bytes.length > LIMITE_BYTES) {
    return erro("ARQUIVO_GRANDE_DEMAIS", `O arquivo passa do limite de ${LIMITE_BYTES / 1024 / 1024} MB. Divida a lista em partes.`);
  }
  if (pareceBinario(bytes)) {
    return erro("FORMATO_INVALIDO", "O arquivo não é um CSV válido. Exporte a lista como CSV e tente de novo.");
  }

  const dec = decodificar(bytes);
  const texto = dec.texto.replace(/\r\n?/g, "\n");
  if (texto.trim() === "") return erro("ARQUIVO_VAZIO", "O arquivo está vazio.");

  const delimitador = forcarDelimitador ?? escolherSeparador(texto);
  const registros = lerRegistros(texto, delimitador);

  const avisos: AvisoImportacao[] = [];
  if (dec.avisoLinha !== null) {
    avisos.push({
      linha: dec.avisoLinha,
      codigo: "CODIFICACAO_INVALIDA",
      mensagem: `A linha ${dec.avisoLinha} tem um caractere que não pôde ser lido e foi substituído.`,
    });
  }

  const ruim = registros.find((r) => r.malformado);
  if (ruim) {
    return erro("CSV_MALFORMADO", `Aspas não fechadas na linha ${ruim.linha}.`, { linha: ruim.linha });
  }

  return mapearRegistros({ registros, avisos, nome, formato, aba: null, delimitador, codificacao: dec.codificacao });
}

export type EntradaMapa = {
  registros: Registro[];
  avisos: AvisoImportacao[];
  nome: string;
  formato: "csv" | "txt" | "xlsx" | "xls" | "xlsm" | "pdf";
  aba: string | null;
  delimitador: string | null;
  codificacao: string | null;
};

/** Embalagem no plural (planilha feita à mão) → a grafia que a revisão E1 conhece, para ela propor "un" com 1 clique. */
const EMBALAGEM_SINGULAR: Record<string, string> = {
  sacos: "saco", latas: "lata", caixas: "caixa", barras: "barra", rolos: "rolo", pacotes: "pct", pacote: "pct",
  galao: "gl", galoes: "gl", scs: "sc", cxs: "cx",
};

/** Arquivo de uma coluna só (ou .txt que não é tabela): lista em texto livre, um item por linha. */
export function comoListaTexto(
  linhas: string[],
  linhaInicial: number,
  meta: { nome: string; formato: EntradaMapa["formato"]; aba: string | null; delimitador: string | null; codificacao: string | null; avisos: AvisoImportacao[] },
): ResultadoImportacao {
  // 1ª linha que é só o título da coluna ("Materiais", "Descrição", "Lista") não é material
  let inicio = 0;
  while (inicio < linhas.length && !linhas[inicio].trim()) inicio++;
  const titulo = normalizarNome(linhas[inicio] ?? "");
  const pulaTitulo = SINONIMOS.descricao.includes(titulo) || /^(lista( de (materiais|compras))?|materiais?)$/.test(titulo);
  const { itens, avisos } = lerListaTexto(pulaTitulo ? linhas.slice(inicio + 1) : linhas, linhaInicial + (pulaTitulo ? inicio + 1 : 0));
  if (itens.length === 0) {
    return erro("CABECALHO_NAO_ENCONTRADO", "Não achei materiais neste arquivo. Deixe um material por linha (ex.: \"10 sacos de cimento\") ou use uma planilha com colunas de descrição e quantidade.");
  }
  if (itens.length > LIMITE_ITENS) {
    return erro("ARQUIVO_GRANDE_DEMAIS", `A lista tem mais de ${LIMITE_ITENS.toLocaleString("pt-BR")} itens. Divida em partes.`);
  }
  const primeiro: AvisoImportacao = {
    linha: null,
    codigo: "LISTA_TEXTO",
    mensagem: "Li o arquivo como uma lista, um material por linha. Confira as quantidades e unidades na tabela.",
  };
  return {
    origem: {
      arquivo: meta.nome, formato: meta.formato, software: "desconhecido", aba: meta.aba, delimitador: meta.delimitador,
      codificacao: meta.codificacao, linhas_lidas: linhas.length, linhas_descartadas: linhas.length - itens.length,
    },
    itens,
    avisos: [...meta.avisos, primeiro, ...avisos],
  };
}

type RegistroTextoSimples = { linha: number; celulas: string[] };

/** Quantidade numa célula: "10", "2,5", "10 sacos", "30m²". */
function pareceQuantidade(c: string): boolean {
  const t = c.trim();
  if (numeroBr(t) !== null) return true;
  if (!/^\d/.test(t) || t.length > 20) return false;
  const r = lerLinhaLivre(`${t} x`); // "10 sacos x" → quantidade com embalagem/unidade
  return r !== null && r.quantidade !== null && (r.descricao === "x" || r.descricao.startsWith("x ("));
}
const pareceUnidade = (c: string): boolean => {
  const t = c.trim();
  return t !== "" && t.length <= 18 && !/\d{2,}/.test(t) && (unidadeLivre(t) !== null || /^(sc|sacos?|br|barras?|cx|caixas?|lt|latas?|gal[aã]o|rolos?|pct|pacotes?|kit|milheiros?|pe[cç]as?|folhas?)$/i.test(t));
};
const pareceTexto = (c: string): boolean => /[a-zà-ú]{2}/i.test(c) && !pareceUnidade(c) && numeroBr(c.trim()) === null;

/**
 * Planilha SEM cabeçalho: escolhe as colunas pelo conteúdo. Exige uma coluna de texto (o material) e uma de número
 * (a quantidade) na maioria das linhas; senão devolve null e o arquivo é recusado com orientação (TC-054 continua
 * recusado: "Foo;Bar;Baz" sobre "1;2;3" não tem coluna de texto).
 */
function deduzirColunas(linhas: RegistroTextoSimples[]): { desc: number; qtd: number; un: number | null; primeiraEhCabecalho: boolean } | null {
  if (linhas.length === 0) return null;
  const amostra = (linhas.length > 2 ? linhas.slice(1) : linhas).slice(0, 80);
  const largura = Math.max(...linhas.map((r) => r.celulas.length));
  const fracao = (j: number, teste: (c: string) => boolean) =>
    amostra.filter((r) => teste(r.celulas[j] ?? "")).length / amostra.length;
  const melhor = (teste: (c: string) => boolean, excluir: number[]) => {
    let idx = -1;
    let valor = 0;
    for (let j = 0; j < largura; j++) {
      if (excluir.includes(j)) continue;
      const f = fracao(j, teste);
      if (f > valor) { valor = f; idx = j; }
    }
    return valor >= 0.6 ? idx : -1;
  };
  // numeração da linha (1, 2, 3...) não é quantidade
  const sequencia = (j: number) => {
    // a numeração (1, 2, 3...) cobre o arquivo inteiro e começa em 1 (a 1ª linha pode ser cabeçalho)
    const v = linhas.map((r) => numeroBr((r.celulas[j] ?? "").trim()));
    const corpo = v[0] === null ? v.slice(1) : v;
    return corpo.length > 1 && corpo[0] === 1 && corpo.every((n, i) => n !== null && (i === 0 || n === (corpo[i - 1] as number) + 1));
  };
  const numeracoes = Array.from({ length: largura }, (_, j) => j).filter(sequencia);
  const qtd = melhor(pareceQuantidade, numeracoes);
  if (qtd < 0) return null;
  const desc = melhor(pareceTexto, [qtd, ...numeracoes]);
  if (desc < 0) return null;
  const un = melhor(pareceUnidade, [qtd, desc]);
  const primeira = linhas[0].celulas;
  const primeiraEhCabecalho = !pareceQuantidade(primeira[qtd] ?? "") && linhas.length > 1;
  return { desc, qtd, un: un >= 0 ? un : null, primeiraEhCabecalho };
}

/** Núcleo compartilhado por CSV e Excel: acha o cabeçalho, mapeia colunas, lê números e unidades, monta o contrato. */
export function mapearRegistros({ registros, avisos, nome, formato, aba, delimitador, codificacao }: EntradaMapa): ResultadoImportacao {
  type RegistroTexto = { linha: number; celulas: string[]; brutas: Celula[] };
  let naoVazios: RegistroTexto[] = registros
    .map((r) => ({ linha: r.linha, celulas: r.celulas.map(aTexto), brutas: r.celulas }))
    .filter((r) => r.celulas.some((c) => !vazio(c)));

  // Cabeçalho: primeira linha com pelo menos dois papéis reconhecidos.
  let idxCab = -1;
  for (let i = 0; i < Math.min(naoVazios.length, 60); i++) {
    const papeis = new Set(naoVazios[i].celulas.map((c) => papelDe(c)?.papel).filter(Boolean));
    if (papeis.size >= 2) { idxCab = i; break; }
  }
  // Mesclagem vertical (Excel) repete os nomes das colunas na linha de baixo: o cabeçalho de verdade é a linha de
  // baixo, e a de cima vira linha de grupo (ex.: "Dimensões" sobre Largura/Altura).
  const papeisDe = (r: { celulas: string[] }) => new Set(r.celulas.map((c) => papelDe(c)?.papel).filter(Boolean));
  while (
    idxCab >= 0 &&
    idxCab + 1 < naoVazios.length &&
    naoVazios[idxCab + 1].linha === naoVazios[idxCab].linha + 1 &&
    [...papeisDe(naoVazios[idxCab])].every((p) => papeisDe(naoVazios[idxCab + 1]).has(p))
  ) {
    idxCab++;
  }
  if (idxCab < 0) {
    // Quem monta a lista à mão nem sempre põe cabeçalho (teste "como leigo", 08/11). Antes de desistir:
    // (1) uma coluna só = lista em texto livre, um item por linha ("10 sacos de cimento");
    // (2) planilha sem cabeçalho = colunas deduzidas pelo conteúdo (texto = descrição, número = quantidade).
    const umaColuna = naoVazios.every((r) => r.celulas.filter((c) => !vazio(c)).length <= 1);
    if (umaColuna && naoVazios.some((r) => /[a-zà-ú]{2}/i.test(r.celulas.join(" ")))) {
      const linhasTexto = registros.map((r) => r.celulas.map(aTexto).filter((c) => !vazio(c)).join(delimitador ?? " "));
      return comoListaTexto(linhasTexto, registros[0]?.linha ?? 1, { nome, formato, aba, delimitador, codificacao, avisos });
    }
    const deduzido = deduzirColunas(naoVazios);
    if (deduzido) {
      const nomes = (n: number) => Array.from({ length: n }, (_, i) =>
        i === deduzido.desc ? "Descrição" : i === deduzido.qtd ? "Quantidade" : i === deduzido.un ? "Unidade" : `coluna_${i + 1}`);
      const largura = Math.max(...naoVazios.map((r) => r.celulas.length));
      if (deduzido.primeiraEhCabecalho) {
        naoVazios[0] = { ...naoVazios[0], celulas: nomes(largura) };
      } else {
        naoVazios = [{ linha: Math.max(0, naoVazios[0].linha - 1), celulas: nomes(largura), brutas: [] }, ...naoVazios];
      }
      const letra = (i: number | null) => (i === null ? "" : `coluna ${i + 1}`);
      avisos.push({
        linha: null,
        codigo: "SEM_CABECALHO",
        mensagem:
          `A lista não tem cabeçalho; entendi as colunas pelo conteúdo: descrição na ${letra(deduzido.desc)}, ` +
          `quantidade na ${letra(deduzido.qtd)}${deduzido.un !== null ? `, unidade na ${letra(deduzido.un)}` : ""}. Confira.`,
      });
      idxCab = 0;
    }
  }
  if (idxCab < 0) {
    const primeira = naoVazios[0];
    return erro(
      "CABECALHO_NAO_ENCONTRADO",
      "Não encontrei colunas de quantitativo. Deixe uma coluna com o nome do material e outra com a quantidade " +
        "(a unidade é opcional), ou cole a lista no Cadastro manual, um item por linha.",
      { colunas_encontradas: primeira ? primeira.celulas.map((c) => c.trim()).filter((c) => c !== "") : [] },
    );
  }
  const cab = naoVazios[idxCab];
  const antes = idxCab > 0 ? naoVazios[idxCab - 1] : null;
  const descartadasAntes = idxCab;

  // Cabeçalho em duas linhas: linha de grupo imediatamente acima ("Dimensões" sobre Largura/Altura).
  let nomesCab = cab.celulas.map((c) => c.trim());
  // Título (só a primeira coluna preenchida, como a 1ª linha das tabelas do Revit) NÃO é linha de grupo.
  if (antes && antes.linha === cab.linha - 1 && antes.celulas.some((c, i) => i > 0 && !vazio(c))) {
    let grupo = "";
    nomesCab = nomesCab.map((n, i) => {
      const g = (antes.celulas[i] ?? "").trim();
      if (g !== "") grupo = g;
      return grupo !== "" && n !== "" && !papelDe(n) ? `${grupo} / ${n}` : n;
    });
    avisos.push({
      linha: antes.linha,
      codigo: "CABECALHO_MULTILINHA",
      mensagem: "O cabeçalho ocupa duas linhas; os nomes foram combinados.",
    });
  }

  // Colunas: nomes únicos, papéis (o primeiro nome de cada papel vence).
  const colunas: Coluna[] = [];
  const vistos = new Map<string, number>();
  const papeisUsados = new Set<Papel>();
  const prioridade = (p: Papel, nomeCol: string) => SINONIMOS[p].indexOf(normalizarNome(nomeCol.replace(/\s*[([].*$/, "")));
  // escolhe, para cada papel, a coluna com o sinônimo de maior prioridade
  const melhorPorPapel = new Map<Papel, { indice: number; pri: number }>();
  // Coluna "Item" com a numeração (1, 2, 3) não é a descrição, mesmo sendo sinônimo dela: havia planilha com
  // "Item" e "O que" e a descrição virava "1", "2", "3" (teste "como leigo", 08/11).
  const dadosAbaixo = naoVazios.slice(idxCab + 1, idxCab + 81);
  const soNumeros = (i: number) => {
    const v = dadosAbaixo.map((r) => (r.celulas[i] ?? "").trim()).filter((c) => c !== "");
    return v.length > 0 && v.filter((c) => /^\d+([.,]\d+)?$/.test(c)).length / v.length >= 0.8;
  };
  nomesCab.forEach((n, i) => {
    const p = papelDe(n);
    if (!p) return;
    if (p.papel === "descricao" && soNumeros(i)) return;
    const pri = prioridade(p.papel, n);
    const atual = melhorPorPapel.get(p.papel);
    if (!atual || (pri >= 0 && pri < atual.pri)) melhorPorPapel.set(p.papel, { indice: i, pri: pri < 0 ? 999 : pri });
  });
  nomesCab.forEach((n, i) => {
    const todosVazios = naoVazios.slice(idxCab + 1).every((r) => vazio(r.celulas[i]));
    if (n === "" && todosVazios) return; // coluna vazia à direita
    let nomeUnico = n === "" ? `coluna_${i + 1}` : n;
    const chave = normalizarNome(nomeUnico);
    const vezes = (vistos.get(chave) ?? 0) + 1;
    vistos.set(chave, vezes);
    if (vezes > 1) {
      nomeUnico = `${n}_${vezes}`;
      avisos.push({ linha: cab.linha, codigo: "COLUNA_DUPLICADA", mensagem: `A coluna "${n}" aparece mais de uma vez; a repetição virou "${nomeUnico}".` });
    }
    const p = vezes === 1 ? papelDe(n) : null;
    let papel: Papel | null = null;
    let unidadePadrao: string | null = null;
    if (p && !papeisUsados.has(p.papel) && melhorPorPapel.get(p.papel)?.indice === i) {
      papel = p.papel;
      unidadePadrao = p.unidade;
      papeisUsados.add(p.papel);
    }
    colunas.push({ indice: i, nome: nomeUnico, papel, unidadePadrao });
  });

  const colDe = (p: Papel) => colunas.find((c) => c.papel === p);
  const cDesc = colDe("descricao");
  const cQtd = colDe("quantidade");
  const cUn = colDe("unidade");
  const cCat = colDe("categoria");
  const cNiv = colDe("nivel");

  const normaisCab = nomesCab.map(normalizarNome);
  const software =
    normaisCab.includes("entity type") || normaisCab.includes("definition name")
      ? "sketchup"
      : normaisCab.includes("family and type") || normaisCab.includes("familia e tipo") || normaisCab.some((n) => n.startsWith("material "))
        ? "revit"
        : "desconhecido";
  const iTipo = normaisCab.indexOf("entity type");

  // Estilo numérico do arquivo, olhando todas as quantidades.
  const dados = naoVazios.slice(idxCab + 1);
  const valoresQtd: string[] = [];
  if (cQtd) {
    for (const r of dados) {
      if (typeof r.brutas[cQtd.indice] === "number") continue; // número de verdade (Excel) não indica estilo
      const c = (r.celulas[cQtd.indice] ?? "").trim();
      const j = separarValorUnidade(c);
      valoresQtd.push(j ? j.numero : c);
    }
  }
  const estilo = detectarEstilo(valoresQtd);

  const itens: ItemImportado[] = [];
  let descartadas = descartadasAntes;
  let lidas = descartadasAntes;
  let nivelAtual: string | null = null; // grupo "Nível: Térreo" das tabelas do Revit agrupadas por nível
  let somaQuantidades = 0;
  const unidadesPorCategoria = new Map<string, Set<string>>();

  for (const r of dados) {
    lidas++;
    const cel = r.celulas.map((c) => c.trim());
    // Linha de grupo do Revit ("Nível: Térreo", uma célula só): vira o nível dos itens seguintes.
    const preenchidas = cel.filter((c) => c !== "");
    const grupo = preenchidas.length === 1 ? cel[0]?.match(/^(?:n[ií]vel|level|pavimento|andar|ambiente|room)\s*:\s*(.+)$/i) : null;
    if (grupo) {
      nivelAtual = grupo[1].trim();
      descartadas++;
      continue;
    }
    // Subtotal do Revit sem rótulo: só a quantidade preenchida (ex.: "<TAB><TAB>42,00 m²") fecha o grupo e não é item.
    // Só vale para tabelas do Revit (TXT ou cabeçalho do Revit): em CSV comum, uma linha só com quantidade é erro a mostrar.
    if (
      (formato === "txt" || software === "revit") &&
      cQtd &&
      (cel[cQtd.indice] ?? "") !== "" &&
      cel.every((c, i) => i === cQtd.indice || c === "")
    ) {
      descartadas++;
      continue;
    }
    // Totais: nunca são itens. O "Total geral" é conferido com a soma das quantidades lidas.
    if (/^(sub)?total( geral)?\b|^grand total\b/i.test(cel[0] ?? "")) {
      descartadas++;
      if (!/^subtotal/i.test(cel[0] ?? "")) {
        // Só a 1ª célula ("Total geral: 10") e a coluna de QUANTIDADE contam: o total em reais de uma coluna de preço
        // gerava "total divergente" falso numa planilha de orçamento comum (teste "como leigo", 08/11).
        const informado = valorDoTotal(cQtd ? cel.map((c, i) => (i === 0 || i === cQtd.indice ? c : "")) : cel);
        if (informado !== null && Math.abs(informado - somaQuantidades) > 0.01) {
          avisos.push({
            linha: r.linha,
            codigo: "TOTAL_DIVERGENTE",
            mensagem: `O total informado (${informado}) difere da soma das quantidades lidas (${Number(somaQuantidades.toFixed(4))}).`,
          });
        }
      }
      continue;
    }
    if (iTipo >= 0 && normalizarNome(cel[iTipo] ?? "") === "group") { descartadas++; continue; }

    if (cel.length < nomesCab.length && colunas.some((c) => c.indice >= cel.length)) {
      avisos.push({ linha: r.linha, codigo: "COLUNAS_FALTANTES", mensagem: `A linha ${r.linha} tem menos colunas que o cabeçalho.` });
    }
    const extras: Record<string, unknown> = {};
    const conhecidas = new Set(colunas.map((c) => c.indice));
    let temExtra = false;
    cel.forEach((v, i) => {
      if (!conhecidas.has(i) && i >= nomesCab.length && v !== "") {
        extras[`coluna_${i + 1}`] = v;
        temExtra = true;
      }
    });
    if (temExtra) {
      avisos.push({ linha: r.linha, codigo: "COLUNAS_EXTRAS", mensagem: `A linha ${r.linha} tem mais colunas que o cabeçalho; o excesso foi guardado.` });
    }

    const cortar = (v: string | undefined): string | null => {
      if (v === undefined) return null;
      if (v.length > LIMITE_TEXTO) {
        avisos.push({ linha: r.linha, codigo: "TEXTO_TRUNCADO", mensagem: `Texto muito longo na linha ${r.linha}; cortado em ${LIMITE_TEXTO} caracteres.` });
        return v.slice(0, LIMITE_TEXTO);
      }
      return v;
    };

    let descricao = cDesc ? cortar(cel[cDesc.indice]) : null;
    const categoria = cCat ? cortar(cel[cCat.indice]) : null;
    const nivelDaCelula = cNiv ? cortar(cel[cNiv.indice]) : null;
    const nivel = nivelDaCelula ? nivelDaCelula : (nivelAtual ?? nivelDaCelula);

    let unidade: string | null = cUn ? (cel[cUn.indice] ?? null) : null;
    if (unidade === "") unidade = null;
    let quantidade: number | null = null;
    let imperialNaQuantidade = false;
    if (cQtd) {
      const original = r.brutas[cQtd.indice];
      let bruto = cel[cQtd.indice];
      if (bruto === undefined) bruto = "";
      const junto = typeof original === "number" ? null : separarValorUnidade(bruto);
      if (junto) {
        bruto = junto.numero;
        if (!unidade) unidade = junto.unidade;
      }
      if (typeof original !== "number" && !ehErroCelula(original) && ehImperial(bruto)) {
        // 12' 6" (pés e polegadas): não converte; guarda o valor original e avisa.
        unidade = "ft-in";
        extras.valor_original = bruto;
        avisos.push({
          linha: r.linha,
          codigo: "UNIDADE_IMPERIAL",
          mensagem: `A medida "${bruto}" na linha ${r.linha} está em pés e polegadas e não foi convertida.`,
        });
        imperialNaQuantidade = true;
      } else if (ehErroCelula(original)) {
        avisos.push({ linha: r.linha, codigo: "ERRO_FORMULA", mensagem: `A quantidade da linha ${r.linha} é uma fórmula com erro (${original.erroCelula}).` });
      } else if (typeof original === "number") {
        if (Number.isFinite(original)) {
          quantidade = original;
          if (original < 0) avisos.push({ linha: r.linha, codigo: "VALOR_NEGATIVO", mensagem: `Quantidade negativa na linha ${r.linha}: ${original}.` });
        } else {
          avisos.push({ linha: r.linha, codigo: "VALOR_NAO_NUMERICO", mensagem: `A quantidade da linha ${r.linha} não é um número válido.` });
        }
      } else if (bruto === "") {
        avisos.push({ linha: r.linha, codigo: "QUANTIDADE_AUSENTE", mensagem: `A linha ${r.linha} está sem quantidade.` });
      } else {
        const n = lerNumero(bruto, estilo);
        if (n.tipo === "ok") {
          quantidade = n.valor;
          if (n.valor < 0) {
            avisos.push({ linha: r.linha, codigo: "VALOR_NEGATIVO", mensagem: `Quantidade negativa na linha ${r.linha}: ${bruto}.` });
          }
        } else if (n.tipo === "ambiguo") {
          avisos.push({ linha: r.linha, codigo: "NUMERO_AMBIGUO", mensagem: `O número "${bruto}" na linha ${r.linha} pode ser decimal ou milhar. Confira a quantidade.` });
        } else {
          // "10 sacos", "3 latas", "2 milheiros": quantidade com a embalagem na mesma célula (planilha feita à mão)
          const livre = /^\d/.test(bruto) ? lerLinhaLivre(`${bruto} x`) : null;
          // o "x" acrescentado tem que ser tudo o que sobrou: a célula inteira era quantidade + embalagem/unidade
          const consumiuTudo = livre !== null && (livre.descricao === "x" || livre.descricao.startsWith("x ("));
          if (livre && consumiuTudo && livre.quantidade !== null && (livre.embalagem || livre.milheiro || livre.unidade)) {
            quantidade = livre.quantidade;
            if (!unidade || livre.milheiro) unidade = livre.unidade;
            if (livre.embalagem && descricao) descricao = `${descricao} (${livre.embalagem})`;
            avisos.push({
              linha: r.linha,
              codigo: "EMBALAGEM_COMO_UNIDADE",
              mensagem: `Linha ${r.linha}: "${bruto}" virou ${livre.quantidade} ${livre.unidade}${livre.embalagem ? " (a embalagem foi para a descrição)" : ""}. Confira.`,
            });
          } else {
            avisos.push({ linha: r.linha, codigo: "VALOR_NAO_NUMERICO", mensagem: `A quantidade "${bruto}" na linha ${r.linha} não é um número.` });
          }
        }
      }
    }
    if (!unidade && cQtd?.unidadePadrao) unidade = cQtd.unidadePadrao;
    if (!unidade && software === "sketchup") unidade = "un";
    // "milheiro" na coluna de unidade: 2 milheiros = 2.000 unidades (a quantidade é convertida e avisada)
    if (unidade && /^(milheiro|milheiros|milh|mil)$/i.test(unidade.trim()) && quantidade !== null) {
      avisos.push({ linha: r.linha, codigo: "EMBALAGEM_COMO_UNIDADE", mensagem: `Linha ${r.linha}: ${quantidade} milheiro(s) = ${quantidade * 1000} unidades. Confira.` });
      quantidade *= 1000;
      unidade = "un";
    }
    // unidade por extenso ("metro quadrado", "quilos") também vale
    if (unidade) unidade = normalizarUnidade(unidade) ?? unidadeLivre(unidade) ?? EMBALAGEM_SINGULAR[normalizarNome(unidade)] ?? unidade.trim();
    if (quantidade !== null) somaQuantidades += quantidade;

    let imperial = false;
    for (const c of colunas) {
      if (c.papel) continue;
      const v = cel[c.indice];
      if (v === undefined) continue;
      const original = r.brutas[c.indice];
      if (typeof original === "number") {
        extras[c.nome] = original; // Excel: o valor bruto, não o texto formatado
        continue;
      }
      const moeda = lerMoeda(v);
      extras[c.nome] = moeda !== null ? moeda : (cortar(v) ?? v);
      if (/^\d+(\.\d+)?\s*["']$/.test(v)) imperial = true;
    }
    if (imperial && !imperialNaQuantidade) {
      avisos.push({ linha: r.linha, codigo: "UNIDADE_IMPERIAL", mensagem: `A linha ${r.linha} traz medidas em polegadas; elas não foram convertidas.` });
    }

    if (categoria && unidade) {
      const s = unidadesPorCategoria.get(categoria) ?? new Set<string>();
      if (["m", "cm", "mm"].includes(unidade)) s.add(unidade);
      unidadesPorCategoria.set(categoria, s);
    }

    itens.push({
      linha: r.linha,
      categoria,
      descricao,
      quantidade,
      unidade,
      nivel,
      extras,
    });
  }

  if (itens.length > LIMITE_ITENS) {
    return erro("ARQUIVO_GRANDE_DEMAIS", `A lista tem mais de ${LIMITE_ITENS.toLocaleString("pt-BR")} itens. Divida em partes.`);
  }

  if ([...unidadesPorCategoria.values()].some((s) => s.size > 1)) {
    avisos.push({ linha: null, codigo: "UNIDADES_MISTAS", mensagem: "Há medidas em unidades diferentes (m, cm, mm) na mesma categoria; nada foi convertido." });
  }
  if (itens.length === 0) {
    avisos.push({ linha: null, codigo: "SEM_DADOS", mensagem: "O arquivo tem cabeçalho, mas nenhuma linha de dados." });
  }

  return {
    origem: {
      arquivo: nome,
      formato,
      software,
      aba,
      delimitador,
      codificacao,
      linhas_lidas: lidas,
      linhas_descartadas: descartadas,
    },
    itens,
    avisos,
  };
}