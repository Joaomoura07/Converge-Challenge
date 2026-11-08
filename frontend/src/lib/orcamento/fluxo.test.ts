// Etapa 12 (lado da tela): as linhas EXATAS que o banco guarda depois de A, B e C rodarem (fixture gerada pelo teste
// de backend tests/test_fluxo_a_b_c.py) atravessam o useOrcamento e chegam às regras da B (lista ao vivo) e da C
// (subtotal, veredito, posições da logística, Excel) sem divergência entre o que o servidor calculou e o que a tela mostra.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { foraDoSubtotal, itensParaTela, linhasDocumento, subtotal, urlExportar, veredito } from "@/components/resultado/resultado";
import { ordenarItens, progresso } from "@/components/orcamento/resultado";
import type { CanalMinimo, Carga, ClienteMinimo } from "./conexao";
import { acompanhar, type Painel } from "./controlador";
import type { ItemLinha, Orcamento } from "./tipos";

const fixture = JSON.parse(readFileSync(join(__dirname, "fixtures/fluxo-a-b-c.json"), "utf8")) as {
  orcamento: Orcamento;
  itens: ItemLinha[];
};
const ID = fixture.orcamento.id;

/** Supabase de mentira que devolve a fixture e deixa o teste empurrar eventos do Realtime. */
function clienteComFixture() {
  let aoStatus: (s: string) => void = () => {};
  const ouvintes: Record<string, (p: Carga) => void> = {};
  const canal: CanalMinimo = {
    on(_t, filtro, cb) {
      ouvintes[String(filtro.table)] = cb;
      return canal;
    },
    subscribe(cb) {
      aoStatus = cb;
      return canal;
    },
  };
  const cliente: ClienteMinimo = {
    channel: () => canal,
    removeChannel: () => undefined,
    from: (tabela) => ({
      select: () => ({
        eq: () => ({
          maybeSingle: async () => ({ data: tabela === "orcamentos" ? fixture.orcamento : null, error: null }),
          order: async () => ({ data: tabela === "orcamento_itens" ? fixture.itens : [], error: null }),
        }),
      }),
    }),
  };
  return { cliente, conectar: () => aoStatus("SUBSCRIBED"), evento: (tabela: string, p: Carga) => ouvintes[tabela](p) };
}

async function carregar() {
  const falso = clienteComFixture();
  let ultimo: Painel | null = null;
  const c = acompanhar(falso.cliente, ID, (p) => (ultimo = p));
  falso.conectar();
  await new Promise((r) => setTimeout(r, 0));
  const painel = ultimo as Painel | null;
  if (!painel) throw new Error("sem painel");
  return { painel, c, falso };
}

describe("o resultado do fluxo A→B→C chega íntegro à tela", () => {
  it("a fixture é do fluxo real: A classificou, B pesquisou com fonte, C calculou", () => {
    const o = fixture.orcamento;
    expect(o.status_pesquisa).toBe("concluida");
    expect(o.logistica && o.viabilidade && o.ganho).toBeTruthy();
    for (const i of fixture.itens) if (i.preco_emb_med != null) expect(i.fontes?.length).toBeGreaterThan(0);
  });

  it("useOrcamento entrega os itens na ordem da lista e o orçamento com logistica, viabilidade e ganho", async () => {
    const { painel } = await carregar();
    expect(painel.conexao).toBe("ao-vivo");
    expect(painel.estado.orcamento?.id).toBe(ID);
    const linhas = Object.values(painel.estado.itens).sort((a, b) => a.linha - b.linha);
    expect(linhas.map((i) => i.linha)).toEqual([2, 3, 4, 5, 6]);
    expect(painel.estado.orcamento?.logistica).not.toBeNull();
  });

  it("B (lista ao vivo): preço com fonte, pergunta ao arquiteto e não encontrado vão para o fim", async () => {
    const { painel } = await carregar();
    const itens = Object.values(painel.estado.itens).sort((a, b) => a.linha - b.linha);
    const p = progresso(itens);
    expect(p).toMatchObject({ total: 5, pendentes: 1, naoEncontrados: 1, concluido: true });
    const ordem = ordenarItens(itens).map((i) => i.status);
    expect(ordem).toEqual(["definido", "definido", "definido", "nao_encontrado", "pendente_especificacao"]);
    const pendente = itens.find((i) => i.status === "pendente_especificacao")!;
    expect(pendente.pergunta).toBeTruthy(); // vira o campo "Responder" do ItemRow
    const comPreco = itens.find((i) => i.status === "definido")!;
    expect(comPreco.fontes?.[0]).toMatchObject({ dominio: expect.any(String), url: expect.stringMatching(/^https:\/\//) });
  });

  it("C (tela) e C (servidor) concordam: o subtotal da tela é o total_med que o servidor gravou", async () => {
    const { painel } = await carregar();
    const itens = Object.values(painel.estado.itens).sort((a, b) => a.linha - b.linha);
    const o = painel.estado.orcamento!;
    expect(subtotal(linhasDocumento(itens))).toBeCloseTo(o.viabilidade!.total_med!, 2);
    expect(subtotal(linhasDocumento(itens))).toBeCloseTo(o.logistica!.total!, 2);
    // o que está fora do subtotal na tela é o que o servidor chama de "sem preço"
    expect(foraDoSubtotal(itens).total).toBe(o.viabilidade!.itens_sem_preco!.length);
  });

  it("o complemento aceito entra na conta, tem a regra e a estimativa de consumo", async () => {
    const { painel } = await carregar();
    const itens = Object.values(painel.estado.itens);
    const comp = itens.find((i) => i.sugerido)!;
    expect(comp).toMatchObject({ aceito: true, estimativa: false });
    expect(linhasDocumento(itens).map((l) => l.id)).toContain(comp.id);
    // um complemento SEM aceite não conta (a C do servidor também o ignora)
    const semAceite = { ...comp, id: "x", aceito: null } as ItemLinha;
    expect(linhasDocumento([...itens, semAceite]).map((l) => l.id)).not.toContain("x");
  });

  it("com itens sem preço que já cabem, mostra 'Dentro do orçamento' mas avisa quantos ficaram fora da conta", async () => {
    const { painel } = await carregar();
    const v = painel.estado.orcamento!.viabilidade!;
    expect(v.completo).toBe(false);
    expect(v.cabe).toBe(true);
    expect(veredito(v)).toMatchObject({ tom: "sim", titulo: "Dentro do orçamento", nota: "Até agora: 2 itens sem preço ficaram fora da conta." });
  });

  it("as posições da logística apontam para a lista ordenada por linha (a ordem do useOrcamento)", async () => {
    const { painel } = await carregar();
    const ordenados = Object.values(painel.estado.itens).sort((a, b) => a.linha - b.linha);
    const lojas = painel.estado.orcamento!.logistica!.lojas!;
    const itensDaLoja = (nome: string) => lojas.find((l) => l.nome === nome)!.itens.map((p) => ordenados[p].descricao);
    expect(itensDaLoja("Leroy Merlin").some((d) => /Toque de Seda/.test(d))).toBe(true);
    expect(itensDaLoja("Leroy Merlin").some((d) => /Argamassa/.test(d))).toBe(true);
    expect(itensDaLoja("C&C").some((d) => /Massa corrida/.test(d))).toBe(true);
    expect(lojas.every((l) => l.frete === 0)).toBe(true); // frete em pausa
  });

  it("a tela de estimativa só mostra número onde há preço (sem preço nunca vira R$)", async () => {
    const { painel } = await carregar();
    const tela = itensParaTela(Object.values(painel.estado.itens).sort((a, b) => a.linha - b.linha));
    for (const t of tela) {
      if (t.situacao === "precificado") expect(t.total).not.toBeNull();
      else expect(t.total).toBeNull();
    }
    expect(tela.filter((t) => t.situacao === "pendente")).toHaveLength(1);
    expect(tela.find((t) => t.situacao === "pendente")!.aviso).toMatch(/\?/); // a pergunta ao arquiteto
  });

  it("o botão Exportar aponta para a rota da C com o código do orçamento", () => {
    expect(urlExportar(ID, "http://api.teste/")).toBe(`http://api.teste/orcamentos/${ID}/exportar.xlsx`);
    expect(urlExportar(ID, "")).toBeNull();
  });

  it("repesquisar_item (B) muda um item pelo Realtime e a tela recalcula o subtotal", async () => {
    const { falso, painel } = await carregar();
    const antes = subtotal(linhasDocumento(Object.values(painel.estado.itens)));
    const pendente = fixture.itens.find((i) => i.status === "pendente_especificacao")!;
    // o que a B grava depois de "Responder": o mesmo item, agora definido com preço e fonte
    const novo = {
      ...pendente, status: "definido", pergunta: null, produto_normalizado: "Coral Rende Muito Branco 18L", embalagem: "lata 18 L",
      qtd_embalagens: 1, preco_emb_min: 270, preco_emb_med: 289.9, preco_emb_max: 310, confianca: "alta",
      fontes: [{ loja: "C&C", dominio: "cec.com.br", url: "https://www.cec.com.br/p/2", preco_embalagem: 289.9 }],
      atualizado_em: new Date(Date.parse(pendente.atualizado_em) + 60_000).toISOString(),
    };
    let ultimo: Painel | null = null;
    const c2 = acompanhar(falso.cliente, ID, (p) => (ultimo = p));
    falso.conectar();
    await new Promise((r) => setTimeout(r, 0));
    falso.evento("orcamento_itens", { eventType: "UPDATE", new: novo as unknown as Record<string, unknown>, old: {} });
    const itens = Object.values((ultimo as unknown as Painel).estado.itens);
    expect(subtotal(linhasDocumento(itens))).toBeCloseTo(antes + 289.9, 2);
    expect(progresso(itens).pendentes).toBe(0);
    c2.parar();
  });
});
