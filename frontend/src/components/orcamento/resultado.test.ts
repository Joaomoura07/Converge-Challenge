import { describe, expect, it } from "vitest";
import {
  ErroRepesquisa, aplicarResultado, fraseProgresso, ordenarItens, progresso, repesquisarItem,
} from "./resultado";
import type { ItemOrcamento, StatusItem } from "./tipos";

const item = (id: string, status: StatusItem): ItemOrcamento => ({ id, descricao: `item ${id}`, status });

describe("ordem da lista", () => {
  it("pendentes ficam juntos no fim e não encontrados logo antes, sem embaralhar o resto", () => {
    const lista = [item("1", "pendente_especificacao"), item("2", "definido"), item("3", "nao_encontrado"),
                   item("4", "buscando"), item("5", "definido"), item("6", "erro")];
    expect(ordenarItens(lista).map((i) => i.id)).toEqual(["2", "4", "5", "3", "6", "1"]);
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
