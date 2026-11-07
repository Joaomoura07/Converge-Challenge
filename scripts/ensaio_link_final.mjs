#!/usr/bin/env node
// Ensaio do LINK FINAL (etapa 14). Node 18+, sem dependências.
//
//   node scripts/ensaio_link_final.mjs --api https://converge-challenge.vercel.app --site https://SEU-SITE.vercel.app \
//        --supabase-url https://XXXX.supabase.co --anon-key eyJ...            # só leitura
//   ...  --enviar                                                              # + UM orçamento real (grava no Supabase, usa LLM/Tavily)
//
// Sem --enviar o script só LÊ: rotas da API, páginas do site e a política de acesso (RLS) com a chave PÚBLICA (anon).
// Com --enviar ele faz um POST /orcamentos de 6 itens do exemplo 1 (cache aquecido) com o nome "TESTE ETAPA 14 (pode apagar)",
// mede a duração da requisição (a função da Vercel precisa aguentar ≥ 60 s) e confere o resultado pela chave anon.
// NUNCA use a chave de serviço aqui: ela ignora a RLS e não prova nada.

import { randomUUID } from "node:crypto";

const arg = (nome) => {
  const i = process.argv.indexOf(`--${nome}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
};
const api = (arg("api") ?? "").replace(/\/+$/, "");
const site = (arg("site") ?? "").replace(/\/+$/, "");
const supa = (arg("supabase-url") ?? "").replace(/\/+$/, "");
const anon = arg("anon-key") ?? "";
const enviar = process.argv.includes("--enviar");

let ok = 0;
let falha = 0;
const conferir = (rotulo, bom, detalhe = "") => {
  console.log(`${bom ? "OK   " : "FALHA"} ${rotulo}${detalhe ? ` (${detalhe})` : ""}`);
  bom ? ok++ : falha++;
};
const pular = (rotulo, motivo) => console.log(`PULOU ${rotulo} (${motivo})`);
const get = async (url, init) => {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(30_000), ...init });
    return { status: r.status, tipo: r.headers.get("content-type") ?? "", texto: await r.text() };
  } catch (e) {
    return { status: 0, tipo: "", texto: String(e) };
  }
};

console.log("== 1. API publicada ==");
if (!api) pular("API", "informe --api");
else {
  const h = await get(`${api}/health`);
  conferir("GET /health", h.status === 200 && /"status":"ok"/.test(h.texto), `HTTP ${h.status}`);
  if (h.status === 200) {
    const j = JSON.parse(h.texto);
    conferir("LLM, Supabase e Langfuse ligados", j.llm && j.supabase && j.langfuse, JSON.stringify({ llm: j.llm, supabase: j.supabase, langfuse: j.langfuse }));
  }
  const o = await get(`${api}/openapi.json`);
  const rotas = o.status === 200 ? Object.keys(JSON.parse(o.texto).paths) : [];
  for (const r of ["/orcamentos", "/revisao/sugestoes/completo", "/orcamentos/{orcamento_id}/resultado", "/orcamentos/{orcamento_id}/exportar.xlsx", "/orcamento-itens/{item_id}/repesquisar"]) {
    conferir(`rota ${r}`, rotas.includes(r));
  }
  const ruim = await get(`${api}/orcamentos`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  conferir("POST /orcamentos com corpo vazio recusa (422, nada gravado)", ruim.status === 422, `HTTP ${ruim.status}`);
}

console.log("\n== 2. Site publicado ==");
if (!site) pular("site", "informe --site (o front ainda precisa ser publicado: ver docs/ENTREGA-FATIA-A.md)");
else {
  for (const caminho of ["/", "/nova", "/exemplos/apto-boa-viagem.csv"]) {
    const r = await get(`${site}${caminho}`);
    conferir(`GET ${caminho}`, r.status === 200, `HTTP ${r.status} ${r.tipo.split(";")[0]}`);
  }
  const nova = await get(`${site}/nova`);
  conferir("a página /nova é o caderno (Nova obra)", /Nova obra|Caderno|Orça/i.test(nova.texto));
}

console.log("\n== 3. RLS com a chave PÚBLICA (anon) ==");
if (!supa || !anon) pular("RLS", "informe --supabase-url e --anon-key (a chave pública do projeto, nunca a de serviço)");
else {
  const h = { apikey: anon, Authorization: `Bearer ${anon}` };
  const j = { ...h, "Content-Type": "application/json" };
  for (const t of ["orcamentos", "orcamento_itens"]) {
    const r = await get(`${supa}/rest/v1/${t}?select=id&limit=1`, { headers: h });
    conferir(`anon LÊ ${t} (leitura pública da demo)`, r.status === 200, `HTTP ${r.status}`);
  }
  for (const t of ["cache_precos", "fornecedores"]) {
    const r = await get(`${supa}/rest/v1/${t}?select=*&limit=1`, { headers: h });
    conferir(`anon NÃO lê ${t}`, r.status === 401 || r.status === 403 || (r.status === 200 && r.texto.trim() === "[]"), `HTTP ${r.status}`);
  }
  const ins = await get(`${supa}/rest/v1/orcamentos`, { method: "POST", headers: { ...j, Prefer: "return=minimal" }, body: JSON.stringify({ id: randomUUID(), nome: "x", cep: "51020000", orcamento_cliente: 1, hash_conteudo: "x", qtd_itens: 1 }) });
  conferir("anon NÃO grava em orcamentos", ins.status === 401 || ins.status === 403, `HTTP ${ins.status}`);
  const upd = await get(`${supa}/rest/v1/orcamentos?id=neq.00000000-0000-0000-0000-000000000000`, { method: "PATCH", headers: { ...j, Prefer: "return=minimal" }, body: JSON.stringify({ nome: "hack" }) });
  conferir("anon NÃO atualiza orcamentos", upd.status === 401 || upd.status === 403 || upd.status === 404, `HTTP ${upd.status}`);
  for (const f of ["criar_orcamento", "reservar_pesquisa", "gravar_resultado_item", "finalizar_pesquisa"]) {
    const r = await get(`${supa}/rest/v1/rpc/${f}`, { method: "POST", headers: j, body: "{}" });
    conferir(`anon NÃO executa ${f}`, r.status === 401 || r.status === 403 || r.status === 404, `HTTP ${r.status}`);
  }
}

if (enviar) {
  console.log("\n== 4. UM orçamento real pelo link (grava no Supabase, usa LLM e Tavily) ==");
  if (!api) pular("envio", "informe --api");
  else {
    // 6 itens do exemplo 1 (apto Boa Viagem); com o cache aquecido a pesquisa é rápida.
    const base = [
      ["Selador Coral", "m2", 180, "Pintura"], ["Massa corrida Suvinil", "m2", 180, "Pintura"], ["Suvinil T. Seda branco neve", "m2", 180, "Pintura"],
      ["Porcelanato Portobello cimento 90x90", "m2", 48, "Revestimentos"], ["Rejunte Quartzolit", "kg", 20, "Revestimentos"], ["tinta vermelha", "un", 2, "Pintura"],
    ];
    const id = randomUUID();
    const corpo = {
      orcamento_id: id,
      obra: { nome: "TESTE ETAPA 14 (pode apagar)", cep: "51020000", orcamento_cliente: 20000 },
      origem: { tipo: "manual", modo: "manual" },
      itens: base.map(([descricao, unidade, quantidade, categoria], n) => ({ id: randomUUID(), linha: n + 1, categoria, descricao, quantidade, unidade, origem_item: "manual" })),
    };
    console.log(`orcamento_id ${id}`);
    const t0 = Date.now();
    const r = await get(`${api}/orcamentos`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    const seg = (Date.now() - t0) / 1000;
    console.log(`POST /orcamentos: HTTP ${r.status} em ${seg.toFixed(1)} s`);
    conferir("o POST terminou com 200", r.status === 200, r.status === 200 ? "" : r.texto.slice(0, 200));
    conferir("a requisição durou menos que a função da Vercel (meta: aguentar ≥ 60 s; limite do time: 300 s)", seg < 300, `${seg.toFixed(1)} s`);
    if (r.status === 200 && supa && anon) {
      const h = { apikey: anon, Authorization: `Bearer ${anon}` };
      const o = JSON.parse((await get(`${supa}/rest/v1/orcamentos?id=eq.${id}&select=*`, { headers: h })).texto)[0];
      const itens = JSON.parse((await get(`${supa}/rest/v1/orcamento_itens?orcamento_id=eq.${id}&select=status,preco_emb_med,fontes,pergunta`, { headers: h })).texto);
      conferir("orçamento concluído", o?.status_pesquisa === "concluida", o?.status_pesquisa);
      conferir("itens com preço têm fonte (nunca preço sem fonte)", itens.filter((i) => i.preco_emb_med != null).every((i) => (i.fontes ?? []).length > 0));
      conferir("há pelo menos um item pedindo especificação (a pergunta)", itens.some((i) => i.status === "pendente_especificacao" && i.pergunta));
      conferir("a C gravou logística, viabilidade e ganho", Boolean(o?.logistica && o?.viabilidade && o?.ganho));
      console.log(`tempo de pesquisa gravado: ${o?.tempo_ms ?? "n/d"} ms · custo US$ ${o?.custo_usd ?? "n/d"}`);
      const x = await get(`${api}/orcamentos/${id}/exportar.xlsx`);
      conferir("Excel de exportação (C)", x.status === 200 && /spreadsheetml/.test(x.tipo), `HTTP ${x.status}`);
    }
  }
}

console.log(`\nResumo: ${ok} ok, ${falha} falha(s)`);
process.exit(falha ? 1 : 0);
