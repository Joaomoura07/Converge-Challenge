// Utilitários dos testes de fixtures de tests/importacao (comparação igual à de tests/importacao/run-front.mjs).
import { readFileSync } from "node:fs";
import { join } from "node:path";

export const FIX = join(__dirname, "../../../../tests/importacao/fixtures");

export type Variante = { entrada: string; esperado: string | null };
export type Caso = { id: string; titulo: string; prioridade: string; tipo: string; variantes: Variante[] };

export const manifest = JSON.parse(readFileSync(join(FIX, "manifest.json"), "utf8")) as { casos: Caso[] };

const ALIAS: Record<string, string> = { utf8: "utf-8", "utf-8-sig": "utf-8", cp1252: "windows-1252", latin1: "windows-1252", "iso-8859-1": "windows-1252" };
const normEnc = (e: string) => ALIAS[e.toLowerCase()] ?? e.toLowerCase();
const igualNum = (a: number | null | undefined, b: number | null | undefined) =>
  a == null || b == null ? a == b : Math.abs(a - b) < 1e-9;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

export function ordenar(v: Json): Json {
  if (Array.isArray(v)) return v.map(ordenar);
  if (v && typeof v === "object") return Object.fromEntries(Object.keys(v).sort().map((k) => [k, ordenar(v[k])]));
  return v;
}

function compararItem(e: Json, o: Json, i: number): string[] {
  const d: string[] = [];
  for (const k of ["linha", "categoria", "descricao", "unidade", "nivel"]) {
    if ((e[k] ?? null) !== (o?.[k] ?? null)) d.push(`itens[${i}].${k}: esperado ${JSON.stringify(e[k])}, veio ${JSON.stringify(o?.[k])}`);
  }
  if (!igualNum(e.quantidade, o?.quantidade)) d.push(`itens[${i}].quantidade: esperado ${e.quantidade}, veio ${o?.quantidade}`);
  const ex = e.extras ?? {};
  const ox = o?.extras ?? {};
  for (const k of new Set([...Object.keys(ex), ...Object.keys(ox)])) {
    const a = ex[k];
    const b = ox[k];
    const igual = typeof a === "number" && typeof b === "number" ? igualNum(a, b) : JSON.stringify(ordenar(a)) === JSON.stringify(ordenar(b));
    if (!igual) d.push(`itens[${i}].extras[${k}]: esperado ${JSON.stringify(a)}, veio ${JSON.stringify(b)}`);
  }
  return d;
}

export function comparar(esp: Json, obt: Json): string[] {
  if (esp.erro) {
    if (!obt.erro) return [`esperava erro ${esp.erro.codigo}, veio sucesso com ${obt.itens?.length} itens`];
    const d: string[] = [];
    if (obt.erro.codigo !== esp.erro.codigo) d.push(`erro.codigo: esperado ${esp.erro.codigo}, veio ${obt.erro.codigo}`);
    if (esp.erro.linha != null && obt.erro.linha !== esp.erro.linha) d.push(`erro.linha: esperado ${esp.erro.linha}, veio ${obt.erro.linha}`);
    if (esp.erro.colunas_encontradas && JSON.stringify(esp.erro.colunas_encontradas) !== JSON.stringify(obt.erro.colunas_encontradas)) {
      d.push(`colunas_encontradas: esperado ${esp.erro.colunas_encontradas}, veio ${obt.erro.colunas_encontradas}`);
    }
    return d;
  }
  if (obt.erro) return [`erro inesperado: ${obt.erro.codigo} (${obt.erro.mensagem})`];
  const d: string[] = [];
  const eo = esp.origem;
  const oo = obt.origem ?? {};
  if (eo.formato !== oo.formato) d.push(`origem.formato: esperado ${eo.formato}, veio ${oo.formato}`);
  if (eo.software !== "desconhecido" && eo.software !== oo.software) d.push(`origem.software: esperado ${eo.software}, veio ${oo.software}`);
  if (eo.delimitador && eo.delimitador !== oo.delimitador) d.push(`origem.delimitador: esperado ${JSON.stringify(eo.delimitador)}, veio ${JSON.stringify(oo.delimitador)}`);
  if (eo.codificacao && normEnc(eo.codificacao) !== normEnc(oo.codificacao)) d.push(`origem.codificacao: esperado ${eo.codificacao}, veio ${oo.codificacao}`);
  const ei: Json[] = esp.itens;
  const oi: Json[] = obt.itens ?? [];
  if (ei.length !== oi.length) d.push(`quantidade de itens: esperado ${ei.length}, veio ${oi.length}`);
  ei.forEach((e, i) => d.push(...compararItem(e, oi[i], i)));
  const chave = (a: Json) => `${a.codigo}@${a.linha ?? "-"}`;
  const ea = (esp.avisos ?? []).map(chave).sort();
  const oa = (obt.avisos ?? []).map(chave).sort();
  if (JSON.stringify(ea) !== JSON.stringify(oa)) d.push(`avisos: esperado [${ea}], veio [${oa}]`);
  return d;
}

