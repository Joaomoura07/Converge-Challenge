import { afterEach, describe, expect, it, vi } from "vitest";
import { itensOrdenados } from "./armazem";
import type { CanalMinimo, Carga, ClienteMinimo, StatusCanal } from "./conexao";
import { acompanhar, ESPERA_REALTIME_MS, type Painel } from "./controlador";
import type { ItemLinha, Orcamento } from "./tipos";

const ID = "11111111-1111-4111-8111-111111111111";
const t = (n: number) => new Date(Date.UTC(2026, 10, 7, 12, 0, n)).toISOString();
const item = (id: string, linha: number, n: number, extra: Partial<ItemLinha> = {}): ItemLinha => ({
  id, orcamento_id: ID, linha, descricao: `item ${id}`, status: "buscando", atualizado_em: t(n), ...extra,
});
const orc = (n: number, extra: Partial<Orcamento> = {}): Orcamento => ({
  id: ID, nome: "Obra", cep: "51020000", orcamento_cliente: 1000, status_pesquisa: "pendente",
  pesquisa_iniciada_em: null, pesquisa_concluida_em: null, pesquisa_erro: null, qtd_itens: 2, custo_usd: null,
  tempo_ms: null, trace_url: null, logistica: null, viabilidade: null, ganho: null,
  created_at: t(0), atualizado_em: t(n), ...extra,
});

/** Cliente de mentira: eventos e status controlados pelo teste, leituras que o teste resolve quando quiser. */
function criarFalso() {
  const filtros: Record<string, unknown>[] = [];
  const ouvintes: Record<string, (p: Carga) => void> = {};
  let aoStatus: (s: StatusCanal) => void = () => {};
  const removidos: CanalMinimo[] = [];
  let nomeCanal = "";

  const canal: CanalMinimo = {
    on(_tipo, filtro, cb) {
      filtros.push(filtro);
      ouvintes[String(filtro.table)] = cb;
      return canal;
    },
    subscribe(cb) {
      aoStatus = cb;
      return canal;
    },
  };
  // Cada leitura = um par de SELECTs (orcamentos + orcamento_itens). O teste resolve o par de uma vez.
  const cliente: ClienteMinimo = {
    channel(nome) {
      nomeCanal = nome;
      return canal;
    },
    removeChannel(c) {
      removidos.push(c);
    },
    from(tabela) {
      return {
        select: () => ({
          eq: () => ({
            maybeSingle: () => pendente(tabela),
            order: () => pendente(tabela),
          }),
        }),
      };
    },
  };
  const esperasO: ((v: { data: unknown; error: unknown }) => void)[] = [];
  const esperasI: ((v: { data: unknown; error: unknown }) => void)[] = [];
  function pendente(tabela: string): PromiseLike<{ data: unknown; error: unknown }> {
    return new Promise((res) => (tabela === "orcamentos" ? esperasO : esperasI).push(res));
  }
  // Associa o n-ésimo par de SELECTs a uma "leitura" que o teste controla.
  const leiturasControle = {
    get total() {
      return Math.min(esperasO.length, esperasI.length);
    },
    resolver(n: number, orcamento: Orcamento | null, itens: ItemLinha[]) {
      esperasO[n]({ data: orcamento, error: null });
      esperasI[n]({ data: itens, error: null });
    },
    falhar(n: number) {
      esperasO[n]({ data: null, error: new Error("rede") });
      esperasI[n]({ data: null, error: new Error("rede") });
    },
  };

  return {
    cliente,
    filtros,
    removidos,
    get nomeCanal() {
      return nomeCanal;
    },
    status: (s: StatusCanal) => aoStatus(s),
    evento: (tabela: "orcamentos" | "orcamento_itens", p: Carga) => ouvintes[tabela](p),
    leituras: leiturasControle,
  };
}

const carga = (eventType: Carga["eventType"], nova: unknown, antiga: unknown = {}): Carga => ({
  eventType, new: nova as Record<string, unknown>, old: antiga as Record<string, unknown>,
});
const tick = () => new Promise((r) => setTimeout(r, 0));

function iniciar() {
  const falso = criarFalso();
  const painéis: Painel[] = [];
  const c = acompanhar(falso.cliente, ID, (p) => painéis.push(p));
  const ultimo = () => painéis[painéis.length - 1];
  return { falso, c, painéis, ultimo };
}

describe("assinatura", () => {
  it("assina as duas tabelas, filtradas pelo orçamento", () => {
    const { falso } = iniciar();
    expect(falso.nomeCanal).toBe(`orcamento:${ID}`);
    expect(falso.filtros).toEqual([
      { event: "*", schema: "public", table: "orcamento_itens", filter: `orcamento_id=eq.${ID}` },
      { event: "*", schema: "public", table: "orcamentos", filter: `id=eq.${ID}` },
    ]);
  });

  it("o ID é conhecido antes do POST: orçamento inexistente na leitura = aguardando, sem erro", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.resolver(0, null, []);
    await tick();
    expect(ultimo().conexao).toBe("ao-vivo");
    expect(ultimo().estado.carregado).toBe(true);
    expect(ultimo().estado.orcamento).toBeNull();
    expect(ultimo().erro).toBeNull();
    // o POST grava: o INSERT chega pelo Realtime
    falso.evento("orcamentos", carga("INSERT", orc(3)));
    falso.evento("orcamento_itens", carga("INSERT", item("a", 1, 3)));
    expect(ultimo().estado.orcamento?.id).toBe(ID);
    expect(itensOrdenados(ultimo().estado).map((i) => i.id)).toEqual(["a"]);
  });
});

describe("carga inicial e atualização durante a conexão", () => {
  it("lê depois de assinar e preserva o evento que chegou antes da leitura terminar", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");                       // dispara a leitura
    expect(falso.leituras.total).toBe(1);
    // chega um UPDATE enquanto o SELECT ainda está em voo
    falso.evento("orcamento_itens", carga("UPDATE", item("a", 1, 9, { status: "definido", preco_emb_med: 50 })));
    falso.leituras.resolver(0, orc(1), [item("a", 1, 2), item("b", 2, 2)]);   // leitura mais velha
    await tick();
    const itens = itensOrdenados(ultimo().estado);
    expect(itens.map((i) => i.id)).toEqual(["a", "b"]);
    expect(itens[0].status).toBe("definido");        // o evento mais novo não foi pisado pela leitura
  });

  it("eventos repetidos não duplicam nem mudam o estado", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.resolver(0, orc(1), [item("a", 1, 2)]);
    await tick();
    for (let i = 0; i < 3; i++) falso.evento("orcamento_itens", carga("UPDATE", item("a", 1, 5, { status: "definido" })));
    expect(itensOrdenados(ultimo().estado)).toHaveLength(1);
    expect(ultimo().estado.itens.a.status).toBe("definido");
  });

  it("leitura vazia (RLS bloqueando ou orçamento sem itens) não é erro", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.resolver(0, null, []);
    await tick();
    expect(ultimo().erro).toBeNull();
    expect(ultimo().estado.carregado).toBe(true);
  });
});

describe("reconexão", () => {
  it("queda marca reconectando; ao voltar lê de novo e reconcilia o que mudou durante a queda", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.resolver(0, orc(1), [item("a", 1, 2), item("b", 2, 2)]);
    await tick();
    falso.status("CLOSED");
    expect(ultimo().conexao).toBe("reconectando");
    falso.status("SUBSCRIBED");
    expect(falso.leituras.total).toBe(2);
    // durante a queda: b ficou pronto e entrou um item novo; a foi excluído
    falso.leituras.resolver(1, orc(8, { status_pesquisa: "concluida" }), [
      item("b", 2, 8, { status: "definido" }), item("c", 3, 8),
    ]);
    await tick();
    expect(ultimo().conexao).toBe("ao-vivo");
    expect(itensOrdenados(ultimo().estado).map((i) => i.id)).toEqual(["b", "c"]);
    expect(ultimo().estado.itens.b.status).toBe("definido");
    expect(ultimo().estado.orcamento?.status_pesquisa).toBe("concluida");
  });

  it("leitura obsoleta (uma mais nova já começou) é descartada", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");               // leitura 0
    falso.status("CLOSED");
    falso.status("SUBSCRIBED");               // leitura 1 (mais nova)
    falso.leituras.resolver(1, orc(9), [item("novo", 1, 9)]);
    await tick();
    falso.leituras.resolver(0, orc(1), [item("velho", 1, 1)]);   // a primeira só chega agora
    await tick();
    expect(itensOrdenados(ultimo().estado).map((i) => i.id)).toEqual(["novo"]);
  });
});

describe("falha de leitura e recuperação", () => {
  it("erro de rede mostra mensagem e recarregar recupera", async () => {
    const { falso, c, ultimo } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.falhar(0);
    await tick();
    expect(ultimo().conexao).toBe("erro-leitura");
    expect(ultimo().erro).toMatch(/Não consegui ler/);
    c.recarregar();
    falso.leituras.resolver(1, orc(2), [item("a", 1, 2)]);
    await tick();
    expect(ultimo().conexao).toBe("ao-vivo");
    expect(ultimo().erro).toBeNull();
    expect(itensOrdenados(ultimo().estado)).toHaveLength(1);
  });
});

describe("limpeza ao desmontar", () => {
  it("parar remove a assinatura e ignora eventos e leituras que chegarem depois", async () => {
    const { falso, c, painéis } = iniciar();
    falso.status("SUBSCRIBED");
    c.parar();
    expect(falso.removidos).toHaveLength(1);
    const antes = painéis.length;
    falso.evento("orcamento_itens", carga("INSERT", item("a", 1, 5)));
    falso.leituras.resolver(0, orc(1), [item("x", 1, 1)]);
    falso.status("CLOSED");
    await tick();
    expect(painéis.length).toBe(antes);   // nada mais é emitido depois de parar
  });
});

describe("eventos de outro orçamento", () => {
  it("DELETE de linha de outro orçamento é ignorado", async () => {
    const { falso, ultimo } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.resolver(0, orc(1), [item("a", 1, 2)]);
    await tick();
    falso.evento("orcamento_itens", carga("DELETE", {}, { id: "a", orcamento_id: "outro" }));
    expect(ultimo().estado.itens.a).toBeDefined();
    falso.evento("orcamento_itens", carga("DELETE", {}, { id: "a", orcamento_id: ID }));
    expect(ultimo().estado.itens.a).toBeUndefined();
  });
});


describe("Realtime que não conecta", () => {
  afterEach(() => vi.useRealTimers());

  it("depois da espera lê pelo REST e mostra os itens, marcando que está reconectando", async () => {
    vi.useFakeTimers();
    const { falso, ultimo } = iniciar();
    expect(falso.leituras.total).toBe(0);
    await vi.advanceTimersByTimeAsync(ESPERA_REALTIME_MS + 10);
    expect(ultimo().conexao).toBe("reconectando");
    expect(falso.leituras.total).toBe(1);
    falso.leituras.resolver(0, orc(1), [item("a", 1, 2)]);
    await vi.advanceTimersByTimeAsync(1);
    expect(ultimo().estado.carregado).toBe(true);
    expect(ultimo().conexao).toBe("reconectando");   // continua tentando o Realtime
    expect(itensOrdenados(ultimo().estado)).toHaveLength(1);
  });

  it("se o Realtime conecta antes, não faz a leitura de reserva", async () => {
    vi.useFakeTimers();
    const { falso } = iniciar();
    falso.status("SUBSCRIBED");
    falso.leituras.resolver(0, orc(1), []);
    await vi.advanceTimersByTimeAsync(ESPERA_REALTIME_MS + 10);
    expect(falso.leituras.total).toBe(1);
  });

  it("parar cancela a leitura de reserva", async () => {
    vi.useFakeTimers();
    const { falso, c } = iniciar();
    c.parar();
    await vi.advanceTimersByTimeAsync(ESPERA_REALTIME_MS + 10);
    expect(falso.leituras.total).toBe(0);
  });
});
