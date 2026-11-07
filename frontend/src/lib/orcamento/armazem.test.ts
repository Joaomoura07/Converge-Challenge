import { describe, expect, it } from "vitest";
import {
  aplicarEvento,
  concluirLeitura,
  estadoVazio,
  iniciarLeitura,
  itensOrdenados,
  type Evento,
} from "./armazem";
import type { ItemLinha, Orcamento } from "./tipos";

const t = (n: number) => new Date(Date.UTC(2026, 10, 7, 12, 0, n)).toISOString();

const item = (id: string, linha: number, n: number, extra: Partial<ItemLinha> = {}): ItemLinha => ({
  id, orcamento_id: "o1", linha, descricao: `item ${id}`, status: "buscando", atualizado_em: t(n), ...extra,
});

const orc = (n: number, extra: Partial<Orcamento> = {}): Orcamento => ({
  id: "o1", nome: "Obra", cep: "51020000", orcamento_cliente: 1000, status_pesquisa: "pendente",
  pesquisa_iniciada_em: null, pesquisa_concluida_em: null, pesquisa_erro: null, qtd_itens: 2, custo_usd: null,
  tempo_ms: null, trace_url: null, logistica: null, viabilidade: null, ganho: null,
  created_at: t(0), atualizado_em: t(n), ...extra,
});

const upd = (linha: ItemLinha): Evento => ({ tabela: "orcamento_itens", tipo: "UPDATE", linha });

describe("eventos repetidos e fora de ordem", () => {
  it("o mesmo evento duas vezes não muda o estado (mesma referência)", () => {
    const a = aplicarEvento(estadoVazio(), upd(item("a", 1, 5)));
    const b = aplicarEvento(a, upd(item("a", 1, 5)));
    expect(b).toBe(a);
    expect(Object.keys(b.itens)).toEqual(["a"]);
  });

  it("evento atrasado (mais velho) não desfaz um dado novo", () => {
    let e = aplicarEvento(estadoVazio(), upd(item("a", 1, 9, { status: "definido" })));
    e = aplicarEvento(e, upd(item("a", 1, 3, { status: "buscando" })));
    expect(e.itens.a.status).toBe("definido");
  });

  it("evento mais novo substitui", () => {
    let e = aplicarEvento(estadoVazio(), upd(item("a", 1, 3)));
    e = aplicarEvento(e, upd(item("a", 1, 9, { status: "definido" })));
    expect(e.itens.a.status).toBe("definido");
  });

  it("orçamento: evento mais novo vence e repetido não muda", () => {
    const a = aplicarEvento(estadoVazio(), { tabela: "orcamentos", tipo: "INSERT", linha: orc(2) });
    const b = aplicarEvento(a, { tabela: "orcamentos", tipo: "UPDATE", linha: orc(2) });
    expect(b).toBe(a);
    const c = aplicarEvento(b, { tabela: "orcamentos", tipo: "UPDATE", linha: orc(8, { status_pesquisa: "concluida" }) });
    expect(c.orcamento?.status_pesquisa).toBe("concluida");
    const d = aplicarEvento(c, { tabela: "orcamentos", tipo: "UPDATE", linha: orc(4, { status_pesquisa: "pesquisando" }) });
    expect(d.orcamento?.status_pesquisa).toBe("concluida");
  });

  it("DELETE remove e deixa lápide: leitura antiga não ressuscita a linha", () => {
    let e = iniciarLeitura(aplicarEvento(estadoVazio(), upd(item("a", 1, 3))));
    e = aplicarEvento(e, { tabela: "orcamento_itens", tipo: "DELETE", id: "a" });
    e = concluirLeitura(e, null, [item("a", 1, 3)]); // o SELECT foi feito antes da exclusão
    expect(e.itens.a).toBeUndefined();
  });
});

describe("leitura (inicial ou depois de reconectar)", () => {
  it("evento que chegou durante a leitura é preservado mesmo com a leitura mais velha", () => {
    let e = iniciarLeitura(estadoVazio());
    e = aplicarEvento(e, upd(item("a", 1, 9, { status: "definido" })));
    e = concluirLeitura(e, orc(1), [item("a", 1, 2, { status: "buscando" }), item("b", 2, 2)]);
    expect(e.itens.a.status).toBe("definido");
    expect(Object.keys(e.itens).sort()).toEqual(["a", "b"]);
    expect(e.carregado).toBe(true);
  });

  it("item novo que só o evento trouxe (INSERT depois do SELECT) permanece", () => {
    let e = iniciarLeitura(estadoVazio());
    e = aplicarEvento(e, upd(item("novo", 3, 5)));
    e = concluirLeitura(e, orc(1), [item("a", 1, 2)]);
    expect(Object.keys(e.itens).sort()).toEqual(["a", "novo"]);
  });

  it("depois de reconectar, linha ausente da leitura e sem evento é removida", () => {
    let e = concluirLeitura(iniciarLeitura(estadoVazio()), orc(1), [item("a", 1, 2), item("b", 2, 2)]);
    e = concluirLeitura(iniciarLeitura(e), orc(1), [item("a", 1, 2)]);
    expect(Object.keys(e.itens)).toEqual(["a"]);
  });

  it("leitura mais nova que o local substitui; local mais novo é mantido", () => {
    let e = concluirLeitura(iniciarLeitura(estadoVazio()), orc(1), [item("a", 1, 5, { status: "definido" }), item("b", 2, 5)]);
    e = concluirLeitura(iniciarLeitura(e), orc(1), [item("a", 1, 2, { status: "buscando" }), item("b", 2, 9, { status: "erro" })]);
    expect(e.itens.a.status).toBe("definido");
    expect(e.itens.b.status).toBe("erro");
  });

  it("orçamento ainda inexistente: segue aguardando (null) mas carregado", () => {
    const e = concluirLeitura(iniciarLeitura(estadoVazio()), null, []);
    expect(e.orcamento).toBeNull();
    expect(e.carregado).toBe(true);
  });

  it("o evento do orçamento que chegou durante a leitura vale mais que uma leitura velha", () => {
    let e = iniciarLeitura(estadoVazio());
    e = aplicarEvento(e, { tabela: "orcamentos", tipo: "UPDATE", linha: orc(9, { status_pesquisa: "concluida" }) });
    e = concluirLeitura(e, orc(2, { status_pesquisa: "pesquisando" }), []);
    expect(e.orcamento?.status_pesquisa).toBe("concluida");
  });
});

describe("ordem", () => {
  it("itens saem na ordem da lista (linha), com desempate determinístico", () => {
    let e = estadoVazio();
    for (const i of [item("c", 3, 1), item("a", 1, 1), item("b", 2, 1), item("d", 2, 1)]) e = aplicarEvento(e, upd(i));
    expect(itensOrdenados(e).map((i) => i.id)).toEqual(["a", "b", "d", "c"]);
  });
});
