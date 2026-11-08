import { beforeEach, describe, expect, it } from "vitest";
import type { Linha } from "../lista";
import { estadoDoEnvio, iniciarEnvio, reenviar, reiniciarEnvios } from "./armazem";
import { conteudoDoEnvio, montarCorpo, type CorpoEnvio } from "./corpo";
import { enviarOrcamento, mensagemDoDetalhe, type ResultadoEnvio } from "./enviar";
import { lerRascunho, salvarRascunho } from "./rascunho";

const ID = "11111111-1111-4111-8111-111111111111";
const obra = { nome: "Reforma Apto", cep: "51020000", orcamentoCliente: 20000.5 };

const linhas: Linha[] = [
  { id: "a1", descricao: "Tinta acrílica Suvinil 18L", quantidade: "180", unidade: "m2", categoria: "Pintura", linhaOrigem: 2 },
  { id: "a2", descricao: "tinta branca", quantidade: "2,5", unidade: "un", categoria: "" },
  {
    id: "c1", descricao: "Argamassa colante AC-III 20 kg", quantidade: "15", unidade: "un", categoria: "Revestimentos",
    sugerida: { sugestaoId: "s1", regra: "porcelanato", motivo: "Faltam argamassa e rejunte.", origemLinhas: [2], estimativaConsumo: true },
  },
];

describe("montarCorpo", () => {
  it("monta o contrato do servidor: quantidade número, campos exatos, linha do arquivo ou posição", () => {
    const c = montarCorpo({ orcamentoId: ID, obra, linhas, modo: "csv" })!;
    expect(c.orcamento_id).toBe(ID);
    expect(c.obra).toEqual({ nome: "Reforma Apto", cep: "51020000", orcamento_cliente: 20000.5 });
    expect(c.itens.map((i) => [i.id, i.linha, i.quantidade, i.unidade, i.origem_item])).toEqual([
      ["a1", 2, 180, "m2", "arquivo"],
      ["a2", 2, 2.5, "un", "manual"], // posição 2 (1-based) por não vir de arquivo
      ["c1", 3, 15, "un", "manual"],
    ]);
    expect(typeof c.itens[1].quantidade).toBe("number");
    expect(c.itens[0].categoria).toBe("Pintura");
    expect(c.itens[1].categoria).toBeNull();
    expect(c.origem).toEqual({ tipo: "misto", modo: "csv" });
  });

  it("complemento aceito leva regra, motivo, linhas de origem, aceito e estimativa de CONSUMO", () => {
    const c = montarCorpo({ orcamentoId: ID, obra, linhas, modo: "manual" })!;
    expect(c.itens[2]).toMatchObject({
      sugerido: true, aceito: true, sugestao_aceita_id: "s1", sugestao_regra: "porcelanato",
      sugestao_motivo: "Faltam argamassa e rejunte.", origem_linhas: [2], estimativa_consumo: true,
    });
    expect(c.itens[0]).not.toHaveProperty("sugerido");
    expect(c.itens[0]).not.toHaveProperty("estimativa"); // a estimativa de PREÇO é da B
  });

  it("lista com erro não gera corpo", () => {
    expect(montarCorpo({ orcamentoId: ID, obra, linhas: [{ ...linhas[0], quantidade: "abc" }], modo: "manual" })).toBeNull();
  });

  it("o conteúdo ignora o código: mesmo pedido, mesmo conteúdo", () => {
    const a = montarCorpo({ orcamentoId: ID, obra, linhas, modo: "csv" })!;
    const b = montarCorpo({ orcamentoId: "22222222-2222-4222-8222-222222222222", obra, linhas, modo: "csv" })!;
    expect(conteudoDoEnvio(a)).toBe(conteudoDoEnvio(b));
    const mudou = montarCorpo({ orcamentoId: ID, obra, linhas: [{ ...linhas[0], quantidade: "181" }], modo: "csv" })!;
    expect(conteudoDoEnvio(mudou)).not.toBe(conteudoDoEnvio(a));
    const demo = montarCorpo({ orcamentoId: ID, obra, linhas, modo: "csv", demo: true })!;
    expect(demo.origem.demo).toBe(true);
    expect(conteudoDoEnvio(demo)).not.toBe(conteudoDoEnvio(a));
  });
});

const corpo = montarCorpo({ orcamentoId: ID, obra, linhas, modo: "csv" })!;
const resp = (status: number, json: unknown): typeof fetch =>
  (async () => new Response(JSON.stringify(json), { status, headers: { "Content-Type": "application/json" } })) as typeof fetch;

describe("enviarOrcamento: cada resposta vira uma orientação", () => {
  it("sucesso", async () => {
    const r = await enviarOrcamento(corpo, {
      fetchImpl: resp(200, { orcamento_id: ID, resultado: "criado", itens: 3, pesquisa: { status: "concluida" } }),
    });
    expect(r).toMatchObject({ tipo: "ok", orcamentoId: ID, resultado: "criado" });
  });

  it("reenvio equivalente (existente) também é sucesso", async () => {
    const r = await enviarOrcamento(corpo, { fetchImpl: resp(200, { orcamento_id: ID, resultado: "existente" }) });
    expect(r).toMatchObject({ tipo: "ok", resultado: "existente" });
  });

  it("422: volta e corrige, mostra o campo que o servidor apontou", async () => {
    const r = await enviarOrcamento(corpo, {
      fetchImpl: resp(422, { detail: [{ loc: ["body", "itens", 0, "unidade"], msg: "Input should be 'm'" }] }),
    });
    expect(r).toMatchObject({ tipo: "erro", motivo: "validacao", recuperavel: false });
    expect(r.tipo === "erro" && r.mensagem).toMatch(/itens › 0 › unidade/);
  });

  it("409: conteúdo mudou com o mesmo código", async () => {
    const r = await enviarOrcamento(corpo, { fetchImpl: resp(409, { detail: { orcamento_id: ID } }) });
    expect(r).toMatchObject({ tipo: "erro", motivo: "conflito", recuperavel: false });
  });

  it("502 com recuperavel: reenviar o mesmo pedido", async () => {
    const r = await enviarOrcamento(corpo, {
      fetchImpl: resp(502, { detail: { mensagem: "O orçamento foi salvo, mas a pesquisa falhou.", orcamento_id: ID, recuperavel: true } }),
    });
    expect(r).toMatchObject({ tipo: "erro", motivo: "servidor", recuperavel: true });
    expect(r.tipo === "erro" && r.mensagem).toMatch(/salvo.*Reenvie/);
  });

  it("503: servidor sem banco", async () => {
    const r = await enviarOrcamento(corpo, { fetchImpl: resp(503, { detail: "Supabase não configurado" }) });
    expect(r).toMatchObject({ tipo: "erro", motivo: "config", recuperavel: false });
  });

  it("perda da resposta (rede): reenviar é seguro", async () => {
    const r = await enviarOrcamento(corpo, { fetchImpl: (async () => { throw new TypeError("Failed to fetch"); }) as typeof fetch });
    expect(r).toMatchObject({ tipo: "erro", motivo: "rede", recuperavel: true });
  });

  it("resposta 200 sem corpo esperado não é tratada como sucesso", async () => {
    const r = await enviarOrcamento(corpo, { fetchImpl: resp(200, { ok: true }) });
    expect(r).toMatchObject({ tipo: "erro", recuperavel: true });
  });

  it("manda POST /orcamentos com o corpo em JSON", async () => {
    let visto: { url: string; init?: RequestInit } | null = null;
    await enviarOrcamento(corpo, {
      apiUrl: "http://api.teste",
      fetchImpl: (async (url: string, init?: RequestInit) => {
        visto = { url, init };
        return new Response(JSON.stringify({ orcamento_id: ID, resultado: "criado" }), { status: 200 });
      }) as unknown as typeof fetch,
    });
    expect(visto!.url).toBe("http://api.teste/orcamentos");
    expect(visto!.init?.method).toBe("POST");
    expect(JSON.parse(visto!.init?.body as string).itens).toHaveLength(3);
  });

  it("mensagemDoDetalhe aceita texto, objeto, lista e vazio", () => {
    expect(mensagemDoDetalhe("oi", "x")).toBe("oi");
    expect(mensagemDoDetalhe({ mensagem: "m" }, "x")).toBe("m");
    expect(mensagemDoDetalhe([], "padrão")).toBe("padrão");
    expect(mensagemDoDetalhe(null, "padrão")).toBe("padrão");
  });
});

describe("armazém de envios (a tela navega enquanto o POST segue aberto)", () => {
  beforeEach(() => reiniciarEnvios());

  const ok: ResultadoEnvio = { tipo: "ok", orcamentoId: ID, resultado: "criado", pesquisa: {} };

  it("fica 'enviando' enquanto o POST não volta e depois 'concluido'", async () => {
    let terminar: (r: ResultadoEnvio) => void = () => {};
    const p = iniciarEnvio(corpo, () => new Promise<ResultadoEnvio>((res) => (terminar = res)));
    expect(estadoDoEnvio(ID)?.tipo).toBe("enviando");
    terminar(ok);
    await p;
    expect(estadoDoEnvio(ID)?.tipo).toBe("concluido");
  });

  it("clique repetido não dispara um segundo POST enquanto há um aberto", async () => {
    let chamadas = 0;
    let terminar: (r: ResultadoEnvio) => void = () => {};
    const enviar = () => { chamadas++; return new Promise<ResultadoEnvio>((res) => (terminar = res)); };
    const p1 = iniciarEnvio(corpo, enviar);
    void iniciarEnvio(corpo, enviar);
    void iniciarEnvio(corpo, enviar);
    expect(chamadas).toBe(1);
    terminar(ok);
    await p1;
  });

  it("erro guarda o corpo e 'reenviar' refaz o MESMO pedido (mesmo código e conteúdo)", async () => {
    const corpos: CorpoEnvio[] = [];
    const falha: ResultadoEnvio = { tipo: "erro", motivo: "rede", recuperavel: true, mensagem: "perdeu" };
    await iniciarEnvio(corpo, async (c) => { corpos.push(c); return falha; });
    expect(estadoDoEnvio(ID)?.tipo).toBe("erro");
    await reenviar(ID, async (c) => { corpos.push(c); return ok; });
    expect(estadoDoEnvio(ID)?.tipo).toBe("concluido");
    expect(corpos).toHaveLength(2);
    expect(corpos[1]).toEqual(corpos[0]);
    const e = estadoDoEnvio(ID);
    expect(e && "tentativa" in e ? e.tentativa : 2).toBeGreaterThanOrEqual(1);
  });

  it("não reenvia o que está em andamento nem o que não existe", () => {
    expect(reenviar("nao-existe")).toBeUndefined();
  });
});

describe("rascunho (Voltar e corrigir)", () => {
  const guardado: Record<string, string> = {};
  const storage = {
    setItem: (k: string, v: string) => { guardado[k] = v; },
    getItem: (k: string) => guardado[k] ?? null,
  };
  const r = { obra, orcamentoId: ID, modo: "csv", linhas, ultimoEnvio: { orcamentoId: ID, conteudo: "x" } };

  it("guarda e devolve a lista como estava", () => {
    expect(salvarRascunho(r, storage)).toBe(true);
    const lido = lerRascunho(ID, storage);
    expect(lido?.linhas).toEqual(linhas);
    expect(lido?.obra).toEqual(obra);
    expect(lido?.ultimoEnvio).toEqual({ orcamentoId: ID, conteudo: "x" });
  });

  it("outro código, JSON quebrado e falta de storage dão null, sem lançar", () => {
    expect(lerRascunho("outro-id", storage)).toBeNull();
    expect(lerRascunho(ID, { getItem: () => "{quebrado" })).toBeNull();
    expect(lerRascunho(ID, null)).toBeNull();
    expect(salvarRascunho(r, null)).toBe(false);
    expect(salvarRascunho(r, { setItem: () => { throw new Error("cheio"); } })).toBe(false);
  });
});
