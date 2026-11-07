// Leitor de Excel da Fatia A (etapa 09): .xlsx, .xls e .xlsm com SheetJS 0.20.3 (CDN oficial, versão fixa).
// Funções puras: recebem os bytes e devolvem o MESMO contrato do CSV (Importacao) ou um erro. O mapeamento de
// colunas, números e unidades é o núcleo compartilhado de csv.ts (`mapearRegistros`).
//
// Cuidados (docs/testes/casos-de-teste-importacao.md, bloco H, e tests/importacao/README.md):
//  - macro de .xlsm nunca é executada (o SheetJS só lê dados);
//  - aba oculta é ignorada por padrão; a primeira aba visível COM dados é a escolhida, e a pessoa pode trocar;
//  - células mescladas são preenchidas pelo valor da célula de origem;
//  - fórmula usa o valor salvo no arquivo; erro (#DIV/0!, #REF!) e fórmula sem resultado viram aviso ERRO_FORMULA;
//  - número vira número (o valor bruto, não o texto formatado); número escrito como texto passa pelo leitor de números;
//  - arquivo com senha, corrompido, .ods e "bomba de descompressão" são recusados com mensagem que diz o que fazer.

import * as XLSX from "xlsx";
import { importarCsv, mapearRegistros, type Celula, type Registro } from "./csv";
import {
  LIMITE_BYTES,
  type AvisoImportacao,
  type ErroImportacao,
  type Importacao,
  type ResultadoImportacao,
} from "./tipos";

/** Limite do conteúdo descompactado de um .xlsx (bloqueia "bomba de descompressão": TC-092 expande para 200 MB). */
export const LIMITE_DESCOMPACTADO = 128 * 1024 * 1024;
const MAX_ENTRADAS_ZIP = 5000;
const MAX_CELULAS = 2_000_000;

export type AbaInfo = { nome: string; oculta: boolean; temDados: boolean };
export type ImportacaoExcel = Importacao & { abas: AbaInfo[] };

const erro = (
  codigo: ErroImportacao["erro"]["codigo"],
  mensagem: string,
  extra: Partial<ErroImportacao["erro"]> = {},
): ErroImportacao => ({ erro: { codigo, mensagem, ...extra } });

const extensao = (nome: string): string => (nome.toLowerCase().match(/\.([a-z0-9]+)$/)?.[1] ?? "");

const e32 = (b: Uint8Array, p: number): number => (b[p] | (b[p + 1] << 8) | (b[p + 2] << 16) | (b[p + 3] << 24)) >>> 0;
const e16 = (b: Uint8Array, p: number): number => b[p] | (b[p + 1] << 8);

/** Soma o tamanho descompactado lendo só o diretório central do zip (não descompacta nada). null = zip ilegível. */
export function tamanhoDescompactado(bytes: Uint8Array): { total: number; entradas: number } | null {
  let fim = bytes.length - 22;
  const limite = Math.max(0, bytes.length - 22 - 65535);
  while (fim >= limite && e32(bytes, fim) !== 0x06054b50) fim--;
  if (fim < limite) return null;
  const entradas = e16(bytes, fim + 10);
  let p = e32(bytes, fim + 16);
  let total = 0;
  for (let i = 0; i < entradas; i++) {
    if (p + 46 > bytes.length || e32(bytes, p) !== 0x02014b50) return null;
    total += e32(bytes, p + 24);
    p += 46 + e16(bytes, p + 28) + e16(bytes, p + 30) + e16(bytes, p + 32);
  }
  return { total, entradas };
}

const pareceZip = (b: Uint8Array) => b[0] === 0x50 && b[1] === 0x4b && (b[2] === 0x03 || b[2] === 0x05);
const pareceOle = (b: Uint8Array) => b[0] === 0xd0 && b[1] === 0xcf && b[2] === 0x11 && b[3] === 0xe0;

function valorDaCelula(c: XLSX.CellObject | undefined): Celula {
  if (!c) return null;
  if (c.t === "e") {
    const nome = (XLSX.SSF as unknown as { BAD_ERROR?: Record<number, string> }).BAD_ERROR?.[c.v as number];
    return { erroCelula: String(c.w ?? nome ?? "#ERRO") };
  }
  // Fórmula sem resultado utilizável (o arquivo não guardou o valor calculado).
  if (c.f && (c.v === undefined || c.v === null || c.v === "")) return { erroCelula: "fórmula sem resultado" };
  if (c.v === undefined || c.v === null) return null;
  if (c.t === "n") return typeof c.v === "number" ? c.v : Number(c.v);
  if (c.t === "b") return c.v ? "VERDADEIRO" : "FALSO"; // booleano não é quantidade: cai em VALOR_NAO_NUMERICO
  if (c.t === "d") return String(c.w ?? c.v);
  return String(c.v);
}

type Grade = Map<number, Map<number, Celula>>;

/** Lê só as células que existem (não percorre o intervalo declarado: TC-083 formata até a linha 1.048.576). */
function lerGrade(ws: XLSX.WorkSheet): Grade | "grande" {
  const grade: Grade = new Map();
  let contagem = 0;
  for (const chave of Object.keys(ws)) {
    if (chave.startsWith("!")) continue;
    if (++contagem > MAX_CELULAS) return "grande";
    const { r, c } = XLSX.utils.decode_cell(chave);
    const v = valorDaCelula(ws[chave] as XLSX.CellObject);
    if (v === null || v === "") continue;
    let linha = grade.get(r);
    if (!linha) grade.set(r, (linha = new Map()));
    linha.set(c, v);
  }
  // Mescladas: o valor da célula de origem vale para toda a área coberta.
  for (const m of (ws["!merges"] ?? []) as XLSX.Range[]) {
    const origem = grade.get(m.s.r)?.get(m.s.c);
    if (origem === undefined) continue;
    for (let r = m.s.r; r <= m.e.r; r++) {
      for (let c = m.s.c; c <= m.e.c; c++) {
        if (r === m.s.r && c === m.s.c) continue;
        let linha = grade.get(r);
        if (!linha) grade.set(r, (linha = new Map()));
        if (!linha.has(c)) linha.set(c, origem);
      }
    }
  }
  return grade;
}

function gradeParaRegistros(grade: Grade): Registro[] {
  const linhas = [...grade.keys()].sort((a, b) => a - b);
  return linhas.map((r) => {
    const celulas = grade.get(r)!;
    const ultima = Math.max(...celulas.keys());
    return {
      linha: r + 1, // número da linha na planilha (a primeira é 1)
      celulas: Array.from({ length: ultima + 1 }, (_, c) => celulas.get(c) ?? null),
      malformado: false,
    };
  });
}

function infoDasAbas(wb: XLSX.WorkBook): AbaInfo[] {
  return wb.SheetNames.map((nome, i) => {
    const ws = wb.Sheets[nome];
    const oculta = Boolean(wb.Workbook?.Sheets?.[i]?.Hidden);
    const temDados = Object.keys(ws ?? {}).some((k) => !k.startsWith("!") && valorDaCelula(ws[k] as XLSX.CellObject) !== null);
    return { nome, oculta, temDados };
  });
}

/** Primeira aba visível com dados; se só houver ocultas com dados, nenhuma (a pessoa escolhe). */
export function abaPadrao(abas: AbaInfo[]): string | null {
  return abas.find((a) => !a.oculta && a.temDados)?.nome ?? null;
}

export function importarExcel({ nome, bytes, aba }: { nome: string; bytes: Uint8Array; aba?: string | null }): ResultadoImportacao | ImportacaoExcel {
  const ext = extensao(nome);
  if (ext === "ods") return erro("FORMATO_NAO_SUPORTADO", "Formato .ods não suportado. Salve como .xlsx ou .csv.");
  if (!["xlsx", "xls", "xlsm"].includes(ext)) {
    return erro("FORMATO_NAO_SUPORTADO", `Formato .${ext || "desconhecido"} não suportado. Use .xlsx, .xls ou .csv.`);
  }
  if (bytes.length === 0) return erro("ARQUIVO_VAZIO", "O arquivo está vazio.");
  if (bytes.length > LIMITE_BYTES) {
    return erro("ARQUIVO_GRANDE_DEMAIS", `O arquivo passa do limite de ${LIMITE_BYTES / 1024 / 1024} MB. Divida a lista em partes.`);
  }

  if (!pareceZip(bytes) && !pareceOle(bytes)) {
    // Arquivo de texto com extensão de planilha (TC-007): lê como CSV e avisa. Binário qualquer é recusado.
    const r = importarCsv({ nome, bytes });
    if ("erro" in r) {
      return r.erro.codigo === "FORMATO_INVALIDO"
        ? erro("FORMATO_INVALIDO", "O arquivo não é uma planilha válida. Exporte a lista como .xlsx ou .csv.")
        : r;
    }
    const aviso: AvisoImportacao = {
      linha: null,
      codigo: "EXTENSAO_INCORRETA",
      mensagem: `O arquivo .${ext} é na verdade um CSV; foi lido como CSV.`,
    };
    return { ...r, avisos: [aviso, ...r.avisos] };
  }

  if (pareceZip(bytes)) {
    const t = tamanhoDescompactado(bytes);
    if (!t) return erro("ARQUIVO_CORROMPIDO", "Não foi possível ler a planilha.");
    if (t.total > LIMITE_DESCOMPACTADO || t.entradas > MAX_ENTRADAS_ZIP) {
      return erro("ARQUIVO_GRANDE_DEMAIS", "Conteúdo descompactado acima do limite.");
    }
  }

  let wb: XLSX.WorkBook;
  try {
    // cellFormula: precisamos saber se uma fórmula ficou sem valor. Nada é executado: só dados são lidos.
    wb = XLSX.read(bytes, { type: "array", cellFormula: true, cellNF: false, cellHTML: false, cellStyles: false, cellDates: false });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (/password|encrypt/i.test(msg)) return erro("ARQUIVO_PROTEGIDO", "Remova a senha do arquivo e exporte de novo.");
    return erro("ARQUIVO_CORROMPIDO", "Não foi possível ler a planilha.");
  }

  const abas = infoDasAbas(wb);
  if (abas.length === 0) return erro("ARQUIVO_VAZIO", "A planilha não tem abas.");
  const escolhida = aba && wb.SheetNames.includes(aba) ? aba : abaPadrao(abas);
  if (!escolhida) {
    return erro(
      abas.some((a) => a.temDados) ? "FORMATO_INVALIDO" : "ARQUIVO_VAZIO",
      abas.some((a) => a.temDados)
        ? "Só há dados em abas ocultas. Mostre a aba no Excel ou escolha outra."
        : "A planilha está vazia.",
    );
  }

  const grade = lerGrade(wb.Sheets[escolhida]);
  if (grade === "grande") return erro("ARQUIVO_GRANDE_DEMAIS", "A planilha tem células demais. Divida a lista em partes.");

  const r = mapearRegistros({
    registros: gradeParaRegistros(grade),
    avisos: [],
    nome,
    formato: ext as "xlsx" | "xls" | "xlsm",
    aba: escolhida,
    delimitador: null,
    codificacao: null,
  });
  if ("erro" in r) return r;
  return { ...r, abas };
}
