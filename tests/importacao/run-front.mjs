#!/usr/bin/env node
// Executor dos casos de importação contra o PARSER DO FRONT (PapaParse/SheetJS).
//
//   node tests/importacao/run-front.mjs --parser caminho/para/importar.mjs
//   node tests/importacao/run-front.mjs --parser ... --prio P0          # só P0
//   node tests/importacao/run-front.mjs --parser ... --caso TC-012      # um caso
//   node tests/importacao/run-front.mjs --parser ... --bloco F          # um bloco
//   node tests/importacao/run-front.mjs --self-test                     # testa o próprio executor
//
// O módulo do parser deve exportar:
//   export async function importar({ nome, bytes })  // bytes: Uint8Array
//     -> objeto no contrato (origem/itens/avisos) ou { erro: { codigo, ... } }
// Ele precisa rodar em Node (SheetJS e PapaParse funcionam em Node).
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const AQUI = dirname(fileURLToPath(import.meta.url));
const FIX = join(AQUI, 'fixtures');
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
const selfTest = args.includes('--self-test');
const quebrado = args.includes('--self-test-quebrado'); // prova que o comparador detecta erros

if (!existsSync(join(FIX, 'manifest.json'))) {
  console.error('Fixtures não encontradas. Rode: python tests/importacao/gerar_fixtures.py');
  process.exit(2);
}
const manifest = JSON.parse(readFileSync(join(FIX, 'manifest.json'), 'utf8'));
const lerEsperado = (rel) => JSON.parse(readFileSync(join(FIX, rel), 'utf8'));

let importar;
if (selfTest || quebrado) {
  const porEntrada = new Map();
  for (const c of manifest.casos) for (const v of c.variantes) if (v.esperado) porEntrada.set(v.entrada.split('/').pop(), v.esperado);
  importar = async ({ nome }) => {
    let esp = structuredClone(lerEsperado(porEntrada.get(nome)));
    if (esp.resumo) {   // monta itens coerentes com o resumo (total, soma, primeiro, último)
      const { total_itens: n, soma_quantidade: s, primeiro: p, ultimo: u } = esp.resumo;
      const meio = (s - p.quantidade - u.quantidade) / (n - 2);
      esp = { origem: { formato: esp.resumo.formato }, avisos: [],
        itens: [p, ...Array.from({ length: n - 2 }, (_, i) => ({ ...p, linha: p.linha + 1 + i, quantidade: meio })), u] };
    }
    if (quebrado && esp.itens?.length) esp.itens[0].quantidade = (esp.itens[0].quantidade ?? 0) + 1;
    return esp;
  };
} else {
  const p = opt('--parser');
  if (!p) { console.error('Informe --parser <arquivo .mjs> ou use --self-test'); process.exit(2); }
  ({ importar } = await import(pathToFileURL(resolve(p)).href));
  if (typeof importar !== 'function') { console.error(`${p} não exporta "importar"`); process.exit(2); }
}

// ---------------------------------------------------------------- comparação
const ALIAS = { 'utf8': 'utf-8', 'utf-8-sig': 'utf-8', 'cp1252': 'windows-1252', 'latin1': 'windows-1252',
  'iso-8859-1': 'windows-1252', 'utf-16': 'utf-16le', 'utf-16-le': 'utf-16le' };
const normEnc = (e) => { const x = String(e).toLowerCase(); return ALIAS[x] ?? x; };
const ordena = (v) => Array.isArray(v) ? v.map(ordena)
  : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, ordena(v[k])])) : v;
const igualNum = (a, b) => (a === null || b === null || a === undefined || b === undefined) ? a == b : Math.abs(a - b) < 1e-9;
const igualProf = (a, b) => {
  if (typeof a === 'number' && typeof b === 'number') return igualNum(a, b);
  return JSON.stringify(ordena(a)) === JSON.stringify(ordena(b));
};

function comparaItem(e, o, i) {
  const d = [];
  for (const k of ['linha', 'categoria', 'descricao', 'unidade', 'nivel'])
    if ((e[k] ?? null) !== (o?.[k] ?? null)) d.push(`itens[${i}].${k}: esperado ${JSON.stringify(e[k])}, veio ${JSON.stringify(o?.[k])}`);
  if (!igualNum(e.quantidade ?? null, o?.quantidade ?? null)) d.push(`itens[${i}].quantidade: esperado ${e.quantidade}, veio ${o?.quantidade}`);
  const ex = e.extras ?? {}, ox = o?.extras ?? {};
  for (const k of new Set([...Object.keys(ex), ...Object.keys(ox)]))
    if (!igualProf(ex[k], ox[k])) d.push(`itens[${i}].extras["${k}"]: esperado ${JSON.stringify(ex[k])}, veio ${JSON.stringify(ox[k])}`);
  return d;
}

export function compara(esp, obt) {
  if (!obt || typeof obt !== 'object') return ['o parser não devolveu um objeto'];
  if (esp.erro) {
    if (!obt.erro) return [`esperava erro ${esp.erro.codigo}, veio sucesso com ${obt.itens?.length ?? '?'} itens`];
    const d = [];
    if (obt.erro.codigo !== esp.erro.codigo) d.push(`erro.codigo: esperado ${esp.erro.codigo}, veio ${obt.erro.codigo}`);
    if (esp.erro.linha != null && obt.erro.linha !== esp.erro.linha) d.push(`erro.linha: esperado ${esp.erro.linha}, veio ${obt.erro.linha}`);
    return d;
  }
  if (obt.erro) return [`erro inesperado: ${obt.erro.codigo} (${obt.erro.mensagem ?? ''})`];
  if (esp.resumo) {
    const r = esp.resumo, d = [], it = obt.itens ?? [];
    if (it.length !== r.total_itens) d.push(`total de itens: esperado ${r.total_itens}, veio ${it.length}`);
    const soma = it.reduce((s, x) => s + (x.quantidade ?? 0), 0);
    if (Math.abs(soma - r.soma_quantidade) > 0.01) d.push(`soma das quantidades: esperado ${r.soma_quantidade}, veio ${soma.toFixed(4)}`);
    d.push(...comparaItem(r.primeiro, it[0], 0), ...comparaItem(r.ultimo, it.at(-1), it.length - 1));
    if (r.formato && obt.origem?.formato !== r.formato) d.push(`origem.formato: esperado ${r.formato}, veio ${obt.origem?.formato}`);
    return d;
  }
  const d = [], eo = esp.origem, oo = obt.origem ?? {};
  if (eo.formato !== oo.formato) d.push(`origem.formato: esperado ${eo.formato}, veio ${oo.formato}`);
  if (eo.software !== 'desconhecido' && eo.software !== oo.software) d.push(`origem.software: esperado ${eo.software}, veio ${oo.software}`);
  if (eo.aba && eo.aba !== oo.aba) d.push(`origem.aba: esperado ${eo.aba}, veio ${oo.aba}`);
  if (eo.delimitador && eo.delimitador !== oo.delimitador) d.push(`origem.delimitador: esperado ${JSON.stringify(eo.delimitador)}, veio ${JSON.stringify(oo.delimitador)}`);
  if (eo.codificacao && normEnc(eo.codificacao) !== normEnc(oo.codificacao)) d.push(`origem.codificacao: esperado ${eo.codificacao}, veio ${oo.codificacao}`);
  const ei = esp.itens, oi = obt.itens ?? [];
  if (ei.length !== oi.length) d.push(`quantidade de itens: esperado ${ei.length}, veio ${oi.length}`);
  ei.forEach((e, i) => d.push(...comparaItem(e, oi[i], i)));
  const chave = (a) => `${a.codigo}@${a.linha ?? '-'}`;
  const ea = (esp.avisos ?? []).map(chave).sort(), oa = (obt.avisos ?? []).map(chave).sort();
  if (JSON.stringify(ea) !== JSON.stringify(oa)) d.push(`avisos: esperado [${ea}], veio [${oa}]`);
  return d;
}

// ------------------------------------------------------------------- execução
const filtroPrio = opt('--prio'), filtroCaso = opt('--caso'), filtroBloco = opt('--bloco');
const casos = manifest.casos.filter((c) => (!filtroPrio || c.prioridade === filtroPrio)
  && (!filtroCaso || c.id === filtroCaso) && (!filtroBloco || c.bloco === filtroBloco));

const res = { ok: 0, falha: 0, pulado: 0, manual: 0 }, falhasPorPrio = {};
const LIMITE_DIFS = 6;
for (const c of casos) {
  if (c.tipo === 'api') { res.pulado++; continue; }                      // -> pytest
  if (c.tipo === 'manual') { res.manual++; console.log(`·  ${c.id} [manual] ${c.variantes[0].nota}`); continue; }
  for (const v of c.variantes) {
    const rotulo = c.variantes.length > 1 ? `${c.id} (${v.entrada.split('/').pop()})` : c.id;
    const caminho = join(FIX, v.entrada);
    if (!existsSync(caminho)) { res.pulado++; console.log(`-  ${rotulo} pulado: gere com --grandes`); continue; }
    const bytes = new Uint8Array(readFileSync(caminho));
    const nome = v.entrada.split('/').pop();
    let difs;
    try {
      if (c.tipo === 'determinismo') {
        const saidas = [];
        for (let k = 0; k < 3; k++) saidas.push(JSON.stringify(ordena(await importar({ nome, bytes: bytes.slice() }))));
        difs = saidas.every((s) => s === saidas[0]) ? [] : ['as 3 execuções devolveram JSON diferentes'];
        if (!difs.length) difs = compara(lerEsperado('TC-001.esperado.json'), JSON.parse(saidas[0]));
      } else {
        const t0 = performance.now();
        const obt = await importar({ nome, bytes });
        const ms = performance.now() - t0;
        difs = compara(lerEsperado(v.esperado), obt);
        if (!difs.length && (c.id === 'TC-066' && ms > 3000 || c.id === 'TC-084' && ms > 5000))
          difs = [`lento: ${ms.toFixed(0)} ms`];
      }
    } catch (e) {
      difs = [`exceção: ${e?.message ?? e}`];
    }
    if (!difs.length) { res.ok++; console.log(`✔  ${rotulo}`); continue; }
    res.falha++;
    falhasPorPrio[c.prioridade] = (falhasPorPrio[c.prioridade] ?? 0) + 1;
    console.log(`✘  ${rotulo} [${c.prioridade}] ${c.titulo}`);
    difs.slice(0, LIMITE_DIFS).forEach((x) => console.log(`     - ${x}`));
    if (difs.length > LIMITE_DIFS) console.log(`     … e mais ${difs.length - LIMITE_DIFS}`);
  }
}
console.log(`\n${res.ok} ok · ${res.falha} falhas ${JSON.stringify(falhasPorPrio)} · ${res.pulado} pulados (API/grandes) · ${res.manual} manuais`);
process.exit(res.falha ? 1 : 0);
