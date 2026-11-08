import { describe, expect, it } from "vitest";
import {
  ErroRepesquisa, OBJETIVOS, aplicarResultado, fraseProgresso, ordenarItens, progresso, repesquisarItem,
} from "./resultado";
import type { ItemOrcamento, StatusItem } from "./tipos";

const item = (id: string, status: StatusItem): ItemOrcamento => ({ id, descricao: `item ${id}`, status });

describe("ordem da lista", () => {
  it("achados em cima, buscando no meio, erros embaixo junto dos pendentes (verificação), sem embaralhar o resto", () => {
    const lista = [item("1", "pendente_especificacao"), item("2", "definido"), item("3", "nao_encontrado"),
                   item("4", "buscando"), item("5", "definido"), item("6", "erro"), item("7", "buscando")];
    expect(ordenarItens(lista).map((i) => i.id)).toEqual(["2", "5", "4", "7", "3", "6", "1"]);
  });

  it("à medida que chegam, o item achado sobe para cima dos que ainda buscam", () => {
    const antes = [item("1", "buscando"), item("2", "buscando"), item("3", "buscando")];
    const depois = [item("1", "buscando"), item("2", "buscando"), item("3", "definido")];
    expect(ordenarItens(antes).map((i) => i.id)).toEqual(["1", "2", "3"]);
    expect(ordenarItens(depois).map((i) => i.id)).toEqual(["3", "1", "2"]);
  });
});

describe("progresso", () => {
  it("conta o que já saiu de 'buscando'", () => {
    const p = progresso([item("1", "definido"), item("2", "buscando"), item("3", "pendente_especificacao")]);
    expect(p).toMatchObject({ prontos: 2, total: 3, pendentes: 1, concluido: false });
    expect(fraseProgresso(p)).toBe("2 de 3 itens pesquisados");
  });

  it("no fim diz o que ainda depende do arquiteto", () => {
    const p = progresso([item("1", "definido"), item("2", "pendente_especificacao"), item("3", "nao_encontrado")]);
    expect(fraseProgresso(p)).toBe(
      "Pesquisa concluída: 3 itens. 1 precisa da sua especificação. 1 sem preço encontrado.");
  });

  it("lista vazia não diz 'concluída'", () => {
    expect(fraseProgresso(progresso([]))).toBe("Nenhum item enviado para a IA ainda.");
  });
});

describe("repesquisarItem (rota POST /orcamento-itens/{id}/repesquisar)", () => {
  const ok = (corpo: unknown) => async () => new Response(JSON.stringify(corpo), { status: 200 });

  it("'Pesquisar de novo' vai sem corpo; 'Responder' leva nova_descricao", async () => {
    const chamadas: [string, RequestInit | undefined][] = [];
    const buscar = (async (url: string, init?: RequestInit) => {
      chamadas.push([url, init]);
      return new Response(JSON.stringify({ item_id: "a b", status: "definido" }), { status: 200 });
    }) as typeof fetch;
    await repesquisarItem("a b", undefined, "http://api/", buscar);
    await repesquisarItem("a b", "  Suvinil Fosco Completo 3,6 L ", "http://api", buscar);
    expect(chamadas[0][0]).toBe("http://api/orcamento-itens/a%20b/repesquisar");
    expect(chamadas[0][1]?.body).toBeUndefined();
    expect(JSON.parse(String(chamadas[1][1]?.body))).toEqual({ nova_descricao: "Suvinil Fosco Completo 3,6 L" });
  });

  it("alternativa leva só o objetivo (a descrição do arquiteto não vai)", async () => {
    const corpos: unknown[] = [];
    const buscar = (async (_url: string, init?: RequestInit) => {
      corpos.push(JSON.parse(String(init?.body)));
      expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
      return new Response(JSON.stringify({ item_id: "a", status: "definido" }), { status: 200 });
    }) as typeof fetch;
    for (const { objetivo } of OBJETIVOS) await repesquisarItem("a", { objetivo }, "http://api", buscar);
    expect(corpos).toEqual([{ objetivo: "qualidade" }, { objetivo: "preco" }, { objetivo: "semelhante" }]);
  });

  it("'Usar a média mesmo assim' leva só aceitar_media", async () => {
    const corpos: unknown[] = [];
    const buscar = (async (_url: string, init?: RequestInit) => {
      corpos.push(JSON.parse(String(init?.body)));
      expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
      return new Response(JSON.stringify({ item_id: "a", status: "definido" }), { status: 200 });
    }) as typeof fetch;
    await repesquisarItem("a", { aceitarMedia: true }, "http://api", buscar);
    expect(corpos).toEqual([{ aceitar_media: true }]);
  });

  it("'Voltar para o anterior' leva o produto de antes e a troca não vira campo do item", async () => {
    const corpos: unknown[] = [];
    const buscar = (async (_url: string, init?: RequestInit) => {
      corpos.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify({ item_id: "a", status: "definido",
        alternativa: { objetivo: "preco", trocou: true, agora: "Tinta Coral 18 L", antes: { descricao: "Tinta Suvinil 18 L" } } }),
        { status: 200 });
    }) as typeof fetch;
    const r = await repesquisarItem("a", { voltarPara: "Tinta Suvinil 18 L" }, "http://api", buscar);
    expect(corpos).toEqual([{ voltar_para: "Tinta Suvinil 18 L" }]);
    expect(r.alternativa?.antes.descricao).toBe("Tinta Suvinil 18 L");
    const item = aplicarResultado({ id: "a", descricao: "x", quantidade: 1, unidade: "un", status: "buscando" }, r);
    expect("alternativa" in item).toBe(false);
  });

  it("503 da alternativa mostra a frase do servidor; sem frase, o texto padrão", async () => {
    const detalhe = "Não consegui sugerir uma alternativa para este item agora. O item ficou como estava.";
    const com = (async () => new Response(JSON.stringify({ detail: detalhe }), { status: 503 })) as typeof fetch;
    await expect(repesquisarItem("x", { objetivo: "preco" }, "http://api", com)).rejects.toThrow(detalhe);
    const naoJson = (async () => new Response("Bad gateway", { status: 503 })) as typeof fetch;
    await expect(repesquisarItem("x", { objetivo: "preco" }, "http://api", naoJson)).rejects.toThrow(/erro 503/);
  });

  it("explica cada falha em português", async () => {
    const status = (s: number) => (async () => new Response("{}", { status: s })) as typeof fetch;
    await expect(repesquisarItem("x", undefined, "http://api", status(404))).rejects.toThrow(/não existe mais/);
    await expect(repesquisarItem("x", undefined, "http://api", status(503))).rejects.toThrow(/erro 503/);
    const semRede = (async () => { throw new TypeError("fetch failed"); }) as typeof fetch;
    await expect(repesquisarItem("x", undefined, "http://api", semRede)).rejects.toThrow(/conexão/);
    await expect(repesquisarItem("x", "ab", "http://api", ok({}) as typeof fetch)).rejects.toBeInstanceOf(ErroRepesquisa);
    await expect(repesquisarItem("x", undefined, "", ok({}) as typeof fetch)).rejects.toThrow(/NEXT_PUBLIC_API_URL/);
  });

  it("o resultado entra no item sem trocar o id", () => {
    const r = aplicarResultado(item("7", "buscando"), { item_id: "7", status: "definido", preco_emb_med: 10 } as never);
    expect(r).toMatchObject({ id: "7", status: "definido", preco_emb_med: 10, descricao: "item 7" });
    expect("item_id" in r).toBe(false);
  });
});
